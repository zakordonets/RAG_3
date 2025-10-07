"""
Единый entrypoint для всех источников данных через DAG
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.adapters.docusaurus import DocusaurusAdapter
from ingestion.adapters.website import WebsiteAdapter
from ingestion.normalizers.base import Parser, BaseNormalizer
from ingestion.normalizers.docusaurus import DocusaurusNormalizer, URLMapper
from ingestion.normalizers.html import HtmlNormalizer, ContentExtractor
from ingestion.pipeline.chunker import UnifiedChunkerStep
from ingestion.pipeline.embedder import Embedder
from ingestion.pipeline.indexers.qdrant_writer import QdrantWriter
from ingestion.pipeline.dag import PipelineDAG
from ingestion.state.state_manager import get_state_manager
from app.config.app_config import CONFIG


def _clear_qdrant_collection(collection_name: str) -> None:
    """Полностью очищает коллекцию Qdrant."""
    try:
        from qdrant_client import QdrantClient
        from app.config.app_config import CONFIG

        client = QdrantClient(
            url=CONFIG.qdrant_url,
            api_key=CONFIG.qdrant_api_key or None
        )

        # Проверяем, существует ли коллекция
        try:
            collection_info = client.get_collection(collection_name)
            logger.info(f"📊 Коллекция {collection_name} содержит {collection_info.points_count} точек")
        except Exception:
            logger.info(f"📊 Коллекция {collection_name} не существует, создаем новую")
            return

        # Удаляем все точки из коллекции
        from qdrant_client.models import Filter
        client.delete(
            collection_name=collection_name,
            points_selector=Filter()  # Пустой фильтр удаляет все точки
        )

        logger.success(f"✅ Коллекция {collection_name} полностью очищена")

    except Exception as e:
        logger.error(f"❌ Ошибка при очистке коллекции {collection_name}: {e}")
        raise


def create_docusaurus_dag(config: Dict[str, Any]) -> PipelineDAG:
    """Создает DAG для Docusaurus источников."""
    steps = [
        Parser(),
        DocusaurusNormalizer(site_base_url=config.get("site_base_url", "https://docs-chatcenter.edna.ru")),
        URLMapper(
            site_base_url=config.get("site_base_url", "https://docs-chatcenter.edna.ru"),
            site_docs_prefix=config.get("site_docs_prefix", "/docs")
        ),
        UnifiedChunkerStep(
            max_tokens=config.get("chunk_max_tokens", 600),
            min_tokens=config.get("chunk_min_tokens", 350),
            overlap_base=config.get("chunk_overlap_base", 100),
            oversize_block_policy=config.get("chunk_oversize_block_policy", "split"),
            oversize_block_limit=config.get("chunk_oversize_block_limit", 1200)
        ),
        Embedder(batch_size=config.get("batch_size", 16)),
        QdrantWriter(collection_name=config.get("collection_name", CONFIG.qdrant_collection))
    ]

    return PipelineDAG(steps)


def create_website_dag(config: Dict[str, Any]) -> PipelineDAG:
    """Создает DAG для веб-сайтов."""
    steps = [
        Parser(),
        HtmlNormalizer(),
        ContentExtractor(),
        BaseNormalizer(),
        UnifiedChunkerStep(
            max_tokens=config.get("chunk_max_tokens", 600),
            min_tokens=config.get("chunk_min_tokens", 350),
            overlap_base=config.get("chunk_overlap_base", 100),
            oversize_block_policy=config.get("chunk_oversize_block_policy", "split"),
            oversize_block_limit=config.get("chunk_oversize_block_limit", 1200)
        ),
        Embedder(batch_size=config.get("batch_size", 16)),
        QdrantWriter(collection_name=config.get("collection_name", CONFIG.qdrant_collection))
    ]

    return PipelineDAG(steps)


def run_unified_indexing(
    source_type: str,
    config: Dict[str, Any],
    reindex_mode: str = "changed",
    clear_collection: bool = False
) -> Dict[str, Any]:
    """
    Запускает унифицированную индексацию для любого источника.

    Args:
        source_type: Тип источника ("docusaurus", "website")
        config: Конфигурация источника
        reindex_mode: Режим переиндексации ("full", "changed")
        clear_collection: Полная очистка коллекции перед индексацией

    Returns:
        Результат индексации
    """
    logger.info(f"🚀 Запуск унифицированной индексации для источника: {source_type}")

    # Полная очистка коллекции, если запрошено
    if clear_collection:
        logger.warning("🗑️ Полная очистка коллекции перед индексацией")
        _clear_qdrant_collection(config.get("collection_name", CONFIG.qdrant_collection))

    try:
        # Создаем адаптер источника
        if source_type == "docusaurus":
            adapter = DocusaurusAdapter(
                docs_root=config["docs_root"],
                site_base_url=config.get("site_base_url", "https://docs-chatcenter.edna.ru"),
                site_docs_prefix=config.get("site_docs_prefix", "/docs")
            )
            dag = create_docusaurus_dag(config)

        elif source_type == "website":
            adapter = WebsiteAdapter(
                seed_urls=config["seed_urls"],
                base_url=config.get("base_url"),
                render_js=config.get("render_js", False),
                max_pages=config.get("max_pages")
            )
            dag = create_website_dag(config)

        else:
            raise ValueError(f"Неподдерживаемый тип источника: {source_type}")

        # Убеждаемся, что коллекция существует и создаем индексы
        writer = dag.steps[-1]  # Последний шаг - QdrantWriter
        if isinstance(writer, QdrantWriter):
            logger.info("📋 Проверка и создание коллекции...")
            writer.ensure_collection()

        # Запускаем DAG
        logger.info(f"🔄 Запуск DAG с {len(dag.steps)} шагами:")
        for step in dag.steps:
            logger.info(f"  - {step.get_step_name()}")

        # Получаем документы от адаптера
        logger.info("📥 Получение документов от адаптера...")
        documents = adapter.iter_documents()

        # Запускаем обработку через DAG
        logger.info("🔄 Запуск обработки через DAG...")
        stats = dag.run(documents)

        # Сохраняем состояние
        with get_state_manager() as state_manager:
            logger.info("💾 Сохранение состояния индексации...")

        # Логируем финальную статистику
        logger.success(f"🎉 Индексация {source_type} завершена успешно!")
        if isinstance(stats, dict):
            logger.info(f"📊 Финальная статистика:")
            logger.info(f"  📄 Всего чанков: {stats.get('total_chunks', 'N/A')}")
            logger.info(f"  ✅ Обработано: {stats.get('processed_chunks', 'N/A')}")
            logger.info(f"  ❌ Ошибок: {stats.get('failed_chunks', 'N/A')}")
            logger.info(f"  🔢 Батчей: {stats.get('batches_processed', 'N/A')}")
            logger.info(f"  🎯 Нулевых векторов: {stats.get('zero_dense_vectors', 'N/A')}")
            logger.info(f"  💾 Последний upsert: {stats.get('last_upsert_points', 'N/A')} точек")

        return {
            "success": True,
            "source_type": source_type,
            "stats": stats,
            "message": f"Индексация {source_type} завершена успешно"
        }

    except Exception as e:
        logger.error(f"❌ Ошибка индексации {source_type}: {e}")
        return {
            "success": False,
            "source_type": source_type,
            "error": str(e),
            "message": f"Индексация {source_type} завершилась с ошибкой"
        }


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(
        description="Единый пайплайн индексации для всех источников данных"
    )

    parser.add_argument(
        "--source",
        choices=["docusaurus", "website"],
        required=True,
        help="Тип источника данных"
    )

    parser.add_argument(
        "--docs-root",
        help="Корневая директория с документацией (для docusaurus)"
    )

    parser.add_argument(
        "--site-base-url",
        default="https://docs-chatcenter.edna.ru",
        help="Базовый URL сайта"
    )

    parser.add_argument(
        "--site-docs-prefix",
        default="/docs",
        help="Префикс для документации в URL"
    )

    parser.add_argument(
        "--seed-urls",
        nargs="+",
        help="Начальные URL для обхода (для website)"
    )

    parser.add_argument(
        "--collection-name",
        default=CONFIG.qdrant_collection,
        help="Имя коллекции в Qdrant"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Размер батча для обработки"
    )

    parser.add_argument(
        "--chunk-max-tokens",
        type=int,
        default=600,
        help="Максимальное количество токенов в чанке"
    )

    parser.add_argument(
        "--chunk-overlap-tokens",
        type=int,
        default=120,
        help="Перекрытие между чанками в токенах"
    )

    parser.add_argument(
        "--reindex-mode",
        choices=["full", "changed"],
        default="changed",
        help="Режим переиндексации"
    )

    parser.add_argument(
        "--clear-collection",
        action="store_true",
        help="Полная очистка коллекции перед индексацией (удаляет все существующие данные)"
    )

    parser.add_argument(
        "--render-js",
        action="store_true",
        help="Использовать Playwright для рендеринга JS (для website)"
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        help="Максимальное количество страниц для обработки"
    )

    args = parser.parse_args()

    # Формируем конфигурацию
    config = {
        "site_base_url": args.site_base_url,
        "site_docs_prefix": args.site_docs_prefix,
        "collection_name": args.collection_name,
        "batch_size": args.batch_size,
        "chunk_max_tokens": args.chunk_max_tokens,
        "chunk_overlap_tokens": args.chunk_overlap_tokens,
        "reindex_mode": args.reindex_mode
    }

    # Добавляем специфичные для источника параметры
    if args.source == "docusaurus":
        if not args.docs_root:
            logger.error("Для docusaurus источника требуется --docs-root")
            sys.exit(1)
        config["docs_root"] = args.docs_root

    elif args.source == "website":
        if not args.seed_urls:
            logger.error("Для website источника требуется --seed-urls")
            sys.exit(1)
        config["seed_urls"] = args.seed_urls
        config["render_js"] = args.render_js
        if args.max_pages:
            config["max_pages"] = args.max_pages

    # Запускаем индексацию
    result = run_unified_indexing(args.source, config, args.reindex_mode, args.clear_collection)

    if result["success"]:
        logger.success("🎉 Индексация завершена успешно!")
        logger.info(f"📊 Статистика: {result['stats']}")
        sys.exit(0)
    else:
        logger.error(f"❌ Индексация завершилась с ошибкой: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
