"""
Единый entrypoint для всех источников данных через DAG
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List
from copy import deepcopy
import yaml
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
from ingestion.metadata.docusaurus import DocusaurusMetadataMapper


def _deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Рекурсивно объединяет словари, не модифицируя оригиналы."""
    merged = deepcopy(base) if base else {}
    for key, value in (override or {}).items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _build_docusaurus_metadata_mapper(meta_cfg: Optional[Dict[str, Any]]) -> Optional[DocusaurusMetadataMapper]:
    """Создает маппер тематик Docusaurus из конфигурации."""
    if not meta_cfg:
        return None
    domain = meta_cfg.get("domain")
    if not domain:
        logger.warning("Пропускаем metadata маппер без domain")
        return None
    return DocusaurusMetadataMapper(
        domain=domain,
        section_by_dir=meta_cfg.get("section_by_dir", {}) or {},
        role_by_section=meta_cfg.get("role_by_section", {}) or {},
        platform_by_dir=meta_cfg.get("platform_by_dir", {}) or {},
        page_type_by_dir=meta_cfg.get("page_type_by_dir", {}) or {},
        fixed_section=meta_cfg.get("fixed_section"),
        fixed_role=meta_cfg.get("fixed_role"),
        fixed_platform=meta_cfg.get("fixed_platform"),
        default_section=meta_cfg.get("default_section"),
        default_role=meta_cfg.get("default_role"),
        default_platform=meta_cfg.get("default_platform"),
    )


def load_sources_from_config(config_path: str, profile: Optional[str] = None) -> List[Dict[str, Any]]:
    """Загружает и нормализует источники из YAML-конфигурации."""
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")

    try:
        raw_data = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Ошибка парсинга конфигурации {config_path}: {exc}") from exc

    data = deepcopy(raw_data)
    if profile:
        profiles = raw_data.get("profiles", {})
        if profile not in profiles:
            raise ValueError(f"Профиль '{profile}' не найден в {config_path}")
        profile_section = profiles[profile]
        if "global" in profile_section:
            data["global"] = _deep_merge_dicts(
                data.get("global", {}),
                profile_section["global"]
            )
        if "sources" in profile_section:
            data.setdefault("sources", {})
            for name, overrides in profile_section["sources"].items():
                data["sources"][name] = _deep_merge_dicts(
                    data["sources"].get(name, {}),
                    overrides
                )

    global_cfg = data.get("global", {})
    global_indexing = global_cfg.get("indexing", {}) or {}
    global_qdrant = global_cfg.get("qdrant", {}) or {}

    sources_cfg = data.get("sources", {}) or {}
    normalized_sources: List[Dict[str, Any]] = []

    for source_name, source_cfg in sources_cfg.items():
        if not isinstance(source_cfg, dict):
            continue
        if not source_cfg.get("enabled", True):
            continue

        source_type = source_cfg.get("type", "docusaurus")
        if source_type not in {"docusaurus", "website"}:
            logger.warning("Пропускаем источник {} с неподдерживаемым типом {}", source_name, source_type)
            continue

        if source_type == "docusaurus":
            docs_root = source_cfg.get("docs_root")
            if not docs_root:
                raise ValueError(f"Источник '{source_name}' не содержит docs_root")
            routing_cfg = source_cfg.get("routing", {}) or {}
            chunk_cfg = source_cfg.get("chunk", {}) or {}
            source_indexing = source_cfg.get("indexing", {}) or {}

            run_config: Dict[str, Any] = {
                "docs_root": docs_root,
                "site_base_url": source_cfg.get("site_base_url", "https://docs-chatcenter.edna.ru"),
                "site_docs_prefix": source_cfg.get("site_docs_prefix", "/docs"),
                "collection_name": source_cfg.get("collection_name", global_qdrant.get("collection", CONFIG.qdrant_collection)),
                "batch_size": source_cfg.get("batch_size", global_indexing.get("batch_size", 16)),
                "chunk_max_tokens": chunk_cfg.get("max_tokens", 600),
                "chunk_min_tokens": chunk_cfg.get("min_tokens", 350),
                "chunk_overlap_base": chunk_cfg.get("overlap_base", 100),
                "chunk_oversize_block_policy": chunk_cfg.get("oversize_block_policy", "split"),
                "chunk_oversize_block_limit": chunk_cfg.get("oversize_block_limit", 1200),
                "drop_prefix_all_levels": routing_cfg.get("drop_numeric_prefix_in_first_level", True),
                "top_level_meta": source_cfg.get("top_level_meta"),
                "max_pages": source_cfg.get("max_pages"),
                "metadata": source_cfg.get("metadata"),
            }

            normalized_sources.append({
                "name": source_name,
                "source_type": source_type,
                "config": run_config,
                "reindex_mode": source_indexing.get("reindex_mode", global_indexing.get("reindex_mode", "changed"))
            })

        elif source_type == "website":
            seed_urls = source_cfg.get("seed_urls")
            if not seed_urls:
                raise ValueError(f"Источник '{source_name}' (website) не содержит seed_urls")
            run_config = {
                "seed_urls": seed_urls,
                "base_url": source_cfg.get("base_url"),
                "render_js": source_cfg.get("render_js", False),
                "max_pages": source_cfg.get("max_pages"),
                "collection_name": source_cfg.get("collection_name", global_qdrant.get("collection", CONFIG.qdrant_collection)),
                "batch_size": source_cfg.get("batch_size", global_indexing.get("batch_size", 16)),
                "chunk_max_tokens": source_cfg.get("chunk_max_tokens", 600),
                "chunk_min_tokens": source_cfg.get("chunk_min_tokens", 350),
                "chunk_overlap_base": source_cfg.get("chunk_overlap_base", 100),
            }
            normalized_sources.append({
                "name": source_name,
                "source_type": source_type,
                "config": run_config,
                "reindex_mode": global_indexing.get("reindex_mode", "changed")
            })

    return normalized_sources


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
            metadata_mapper = _build_docusaurus_metadata_mapper(config.get("metadata"))
            adapter = DocusaurusAdapter(
                docs_root=config["docs_root"],
                site_base_url=config.get("site_base_url", "https://docs-chatcenter.edna.ru"),
                site_docs_prefix=config.get("site_docs_prefix", "/docs"),
                drop_prefix_all_levels=config.get("drop_prefix_all_levels", True),
                max_pages=config.get("max_pages"),
                top_level_meta=config.get("top_level_meta"),
                metadata_mapper=metadata_mapper,
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

        # Получаем статистику от QdrantWriter
        writer_stats = {}
        if isinstance(writer, QdrantWriter):
            writer_stats = writer.stats

        # Логируем финальную статистику
        logger.success(f"🎉 Индексация {source_type} завершена успешно!")
        logger.info(f"📊 Финальная статистика:")
        logger.info(f"  📄 Документов обработано: {stats.get('processed_docs', 0)}/{stats.get('total_docs', 0)}")
        logger.info(f"  ❌ Ошибок документов: {stats.get('failed_docs', 0)}")
        logger.info(f"  📦 Всего чанков: {writer_stats.get('total_chunks', 'N/A')}")
        logger.info(f"  ✅ Чанков обработано: {writer_stats.get('processed_chunks', 'N/A')}")
        logger.info(f"  ❌ Чанков с ошибками: {writer_stats.get('failed_chunks', 'N/A')}")
        logger.info(f"  🔢 Батчей обработано: {writer_stats.get('batches_processed', 'N/A')}")
        logger.info(f"  🎯 Нулевых векторов: {writer_stats.get('zero_dense_vectors', 'N/A')}")
        logger.info(f"  💾 Последний upsert: {writer_stats.get('last_upsert_points', 'N/A')} точек")
        logger.info(f"  ⏱️  Время выполнения: {stats.get('total_time', 0):.2f}s")

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
        required=False,
        help="Тип источника данных"
    )

    parser.add_argument(
        "--config",
        help="Путь к YAML конфигурации (для запуска нескольких источников)"
    )

    parser.add_argument(
        "--profile",
        help="Имя профиля из конфигурации (development/production/etc)"
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
        default=CONFIG.chunk_max_tokens,
        help="Максимальное количество токенов в чанке"
    )

    parser.add_argument(
        "--chunk-min-tokens",
        type=int,
        default=CONFIG.chunk_min_tokens,
        help="Минимальное количество токенов в чанке"
    )

    parser.add_argument(
        "--chunk-overlap-base",
        type=int,
        default=100,
        help="Базовое перекрытие между чанками в токенах"
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

    if args.config:
        try:
            sources_to_run = load_sources_from_config(args.config, args.profile)
        except Exception as exc:
            logger.error(f"Не удалось загрузить конфигурацию {args.config}: {exc}")
            sys.exit(1)

        if not sources_to_run:
            logger.warning("В конфигурации нет включенных источников")
            sys.exit(0)

        total_sources = len(sources_to_run)
        for idx, source in enumerate(sources_to_run, start=1):
            logger.info(
                "▶️ Источник {} ({}) [{}/{}]",
                source["name"],
                source["source_type"],
                idx,
                total_sources
            )
            result = run_unified_indexing(
                source["source_type"],
                source["config"],
                source.get("reindex_mode", args.reindex_mode),
                clear_collection=args.clear_collection and idx == 1
            )
            if not result["success"]:
                logger.error(
                    "❌ Источник {} завершился ошибкой: {}",
                    source["name"],
                    result.get("error", "unknown")
                )
                sys.exit(1)
        logger.success("🎉 Все источники из конфигурации успешно обработаны")
        sys.exit(0)

    if not args.source:
        parser.error("--source обязательно, если не указан --config")

    # Формируем конфигурацию
    config = {
        "site_base_url": args.site_base_url,
        "site_docs_prefix": args.site_docs_prefix,
        "collection_name": args.collection_name,
        "batch_size": args.batch_size,
        "chunk_max_tokens": args.chunk_max_tokens,
        "chunk_min_tokens": args.chunk_min_tokens,
        "chunk_overlap_base": args.chunk_overlap_base,
        "reindex_mode": args.reindex_mode
    }

    # Добавляем специфичные для источника параметры
    if args.source == "docusaurus":
        if not args.docs_root:
            logger.error("Для docusaurus источника требуется --docs-root")
            sys.exit(1)
        config["docs_root"] = args.docs_root
        if args.max_pages:
            config["max_pages"] = args.max_pages

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
