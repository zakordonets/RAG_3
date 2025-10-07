#!/usr/bin/env python3
"""
CLI для запуска индексации Docusaurus документации
"""

from __future__ import annotations
import argparse
import sys
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import CONFIG
from ingestion.crawlers.docusaurus_fs_crawler import crawl_docs
from ingestion.processors.docusaurus_markdown_processor import process_markdown
from ingestion.indexer import upsert_chunks, create_payload_indexes
from app.services.core.embeddings import embed_batch_optimized


def load_config(config_path: str) -> Dict[str, Any]:
    """Загружает конфигурацию из YAML файла."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"Загружена конфигурация из: {config_path}")
        return config
    except Exception as e:
        raise ValueError(f"Ошибка загрузки конфигурации: {e}")


def merge_config_with_args(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """Объединяет конфигурацию из файла с аргументами командной строки."""
    # Начинаем с конфигурации по умолчанию
    merged = {
        "docs_root": "C:\\CC_RAG\\docs",
        "site_base_url": "https://docs-chatcenter.edna.ru",
        "site_docs_prefix": "/docs",
        "collection_name": "docs_chatcenter",
        "category_filter": None,
        "reindex_mode": "changed",
        "batch_size": 16
    }

    # Применяем конфигурацию из файла
    if "sources" in config and "docusaurus" in config["sources"]:
        docusaurus_config = config["sources"]["docusaurus"]

        # Проверяем, что источник включен
        if not docusaurus_config.get("enabled", True):
            logger.warning("Источник docusaurus отключен в конфигурации")

        merged.update({
            "docs_root": docusaurus_config.get("docs_root", merged["docs_root"]),
            "site_base_url": docusaurus_config.get("site_base_url", merged["site_base_url"]),
            "site_docs_prefix": docusaurus_config.get("site_docs_prefix", merged["site_docs_prefix"]),
        })

        # Настройки чанкинга
        if "chunk" in docusaurus_config:
            chunk_config = docusaurus_config["chunk"]
            merged["chunk_max_tokens"] = chunk_config.get("max_tokens", 600)
            merged["chunk_overlap_tokens"] = chunk_config.get("overlap_tokens", 120)

        # Настройки очистки
        if "cleaning" in docusaurus_config:
            cleaning_config = docusaurus_config["cleaning"]
            merged["cleaning"] = {
                "remove_html_comments": cleaning_config.get("remove_html_comments", True),
                "strip_imports": cleaning_config.get("strip_imports", True),
                "strip_custom_components": cleaning_config.get("strip_custom_components", True),
                "strip_admonitions": cleaning_config.get("strip_admonitions", True),
            }

        # Настройки маршрутизации
        if "routing" in docusaurus_config:
            routing_config = docusaurus_config["routing"]
            merged["routing"] = {
                "drop_numeric_prefix_in_first_level": routing_config.get("drop_numeric_prefix_in_first_level", True),
                "add_trailing_slash": routing_config.get("add_trailing_slash", False),
            }

        # Настройки индексации
        if "indexing" in docusaurus_config:
            indexing_config = docusaurus_config["indexing"]
            merged["indexing"] = {
                "upsert": indexing_config.get("upsert", True),
                "delete_missing": indexing_config.get("delete_missing", False),
            }

    if "global" in config:
        global_config = config["global"]
        if "qdrant" in global_config:
            merged["collection_name"] = global_config["qdrant"].get("collection", merged["collection_name"])
        if "indexing" in global_config:
            merged["batch_size"] = global_config["indexing"].get("batch_size", merged["batch_size"])
            merged["reindex_mode"] = global_config["indexing"].get("reindex_mode", merged["reindex_mode"])

    # Применяем аргументы командной строки (имеют приоритет)
    if args.docs_root:
        merged["docs_root"] = args.docs_root
    if args.site_base_url:
        merged["site_base_url"] = args.site_base_url
    if args.site_docs_prefix:
        merged["site_docs_prefix"] = args.site_docs_prefix
    if args.collection:
        merged["collection_name"] = args.collection
    if args.category_filter:
        merged["category_filter"] = args.category_filter
    if args.reindex:
        merged["reindex_mode"] = args.reindex
    if args.batch_size:
        merged["batch_size"] = args.batch_size

    return merged


def _merge_profile_config(base_config: Dict[str, Any], profile_config: Dict[str, Any]) -> Dict[str, Any]:
    """Объединяет базовую конфигурацию с профилем."""
    import copy
    merged = copy.deepcopy(base_config)

    # Рекурсивно объединяем конфигурации
    def deep_merge(base: Dict, override: Dict) -> Dict:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    return deep_merge(merged, profile_config)


def run_docusaurus_indexing(
    docs_root: str,
    site_base_url: str = "https://docs-chatcenter.edna.ru",
    site_docs_prefix: str = "/docs",
    collection_name: str = "docs_chatcenter",
    category_filter: Optional[str] = None,
    reindex_mode: str = "changed",
    batch_size: int = 16,
    chunk_max_tokens: int = 600,
    chunk_overlap_tokens: int = 120,
    cleaning_config: Optional[Dict[str, Any]] = None,
    routing_config: Optional[Dict[str, Any]] = None,
    indexing_config: Optional[Dict[str, Any]] = None
) -> dict:
    """Запускает полную индексацию Docusaurus документации.

    Args:
        docs_root: Путь к корневой директории с документацией
        site_base_url: Базовый URL сайта
        site_docs_prefix: Префикс для документации в URL
        collection_name: Имя коллекции в Qdrant
        category_filter: Фильтр по категории (например, "АРМ_adm")
        reindex_mode: Режим переиндексации ("changed", "all")
        batch_size: Размер батча для обработки

    Returns:
        Статистика индексации
    """
    logger.info(f"🚀 Запуск индексации Docusaurus документации")
    logger.info(f"📁 Корневая директория: {docs_root}")
    logger.info(f"🌐 Базовый URL: {site_base_url}")
    logger.info(f"📚 Префикс документации: {site_docs_prefix}")
    logger.info(f"🗄️ Коллекция: {collection_name}")
    logger.info(f"🔍 Фильтр категории: {category_filter or 'нет'}")
    logger.info(f"🔄 Режим: {reindex_mode}")

    docs_path = Path(docs_root)
    if not docs_path.exists():
        raise ValueError(f"Директория {docs_root} не существует")

    # Создаем индексы payload
    logger.info("📋 Создание индексов payload...")
    create_payload_indexes(collection_name)

    # Собираем все чанки
    all_chunks = []
    total_files = 0
    processed_files = 0

    logger.info("🔍 Сканирование файлов документации...")

    # Используем crawler для получения файлов
    for item in crawl_docs(
        docs_root=docs_path,
        site_base_url=site_base_url,
        site_docs_prefix=site_docs_prefix,
        drop_prefix_all_levels=True
    ):
        total_files += 1

        try:
            # Читаем содержимое файла
            raw_text = item.abs_path.read_text(encoding="utf-8")

            # Обрабатываем markdown файл
            doc_meta, chunks = process_markdown(
                raw_text=raw_text,
                abs_path=item.abs_path,
                rel_path=item.rel_path,
                site_url=item.site_url,
                dir_meta=item.dir_meta,
                default_category="UNSPECIFIED"
            )

            # Применяем фильтр по категории если указан
            if category_filter:
                # Проверяем категорию документа
                if doc_meta.get("category") != category_filter:
                    continue

            # Добавляем чанки в общий список
            for chunk in chunks:
                # Преобразуем Chunk в формат для indexer
                chunk_dict = {
                    "text": chunk.payload.get("chunk_text", ""),
                    "payload": chunk.payload
                }
                all_chunks.append(chunk_dict)

            processed_files += 1

            if processed_files % 10 == 0:
                logger.info(f"Обработано файлов: {processed_files}/{total_files}")

        except Exception as e:
            logger.warning(f"Ошибка обработки файла {item.abs_path}: {e}")
            continue

    logger.info(f"✅ Обработано файлов: {processed_files}/{total_files}")
    logger.info(f"📦 Собрано чанков: {len(all_chunks)}")

    if not all_chunks:
        logger.warning("Не найдено чанков для индексации")
        return {
            "success": False,
            "files_processed": processed_files,
            "total_files": total_files,
            "chunks_indexed": 0,
            "error": "Нет чанков для индексации"
        }

    # Индексируем чанки батчами
    logger.info(f"🔤 Начинаем индексацию {len(all_chunks)} чанков...")

    try:
        chunks_indexed = upsert_chunks(all_chunks)

        logger.success(f"✅ Индексация завершена успешно!")
        logger.success(f"📊 Статистика:")
        logger.success(f"   📁 Файлов обработано: {processed_files}/{total_files}")
        logger.success(f"   📦 Чанков проиндексировано: {chunks_indexed}")

        return {
            "success": True,
            "files_processed": processed_files,
            "total_files": total_files,
            "chunks_indexed": chunks_indexed
        }

    except Exception as e:
        logger.error(f"❌ Ошибка индексации: {e}")
        return {
            "success": False,
            "files_processed": processed_files,
            "total_files": total_files,
            "chunks_indexed": 0,
            "error": str(e)
        }


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(
        description="Индексация Docusaurus документации в Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Базовая индексация с конфигурацией
  python -m ingestion.run --source docusaurus --config ingestion/config.yaml

  # Индексация с фильтром по категории
  python -m ingestion.run --source docusaurus --config ingestion/config.yaml --category-filter АРМ_adm

  # Полная переиндексация
  python -m ingestion.run --source docusaurus --config ingestion/config.yaml --reindex all

  # Использование профиля конфигурации
  python -m ingestion.run --source docusaurus --config ingestion/config.yaml --profile development

  # Указание кастомных параметров (переопределяют конфигурацию)
  python -m ingestion.run --source docusaurus \\
    --config ingestion/config.yaml \\
    --docs-root "C:\\CC_RAG\\docs" \\
    --site-base-url "https://docs-chatcenter.edna.ru" \\
    --collection "docs_chatcenter"
        """
    )

    parser.add_argument(
        "--source",
        choices=["docusaurus"],
        required=True,
        help="Тип источника данных"
    )

    parser.add_argument(
        "--docs-root",
        default="C:\\CC_RAG\\docs",
        help="Путь к корневой директории с документацией (по умолчанию: C:\\CC_RAG\\docs)"
    )

    parser.add_argument(
        "--site-base-url",
        default="https://docs-chatcenter.edna.ru",
        help="Базовый URL сайта (по умолчанию: https://docs-chatcenter.edna.ru)"
    )

    parser.add_argument(
        "--site-docs-prefix",
        default="/docs",
        help="Префикс для документации в URL (по умолчанию: /docs)"
    )

    parser.add_argument(
        "--collection",
        default="docs_chatcenter",
        help="Имя коллекции в Qdrant (по умолчанию: docs_chatcenter)"
    )

    parser.add_argument(
        "--category-filter",
        help="Фильтр по категории (например: АРМ_adm)"
    )

    parser.add_argument(
        "--reindex",
        choices=["changed", "all"],
        default="changed",
        help="Режим переиндексации (по умолчанию: changed)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Размер батча для обработки (по умолчанию: 16)"
    )

    parser.add_argument(
        "--config",
        default="ingestion/config.yaml",
        help="Путь к файлу конфигурации (по умолчанию: ingestion/config.yaml)"
    )

    parser.add_argument(
        "--profile",
        help="Профиль конфигурации для использования (development, production, testing)"
    )

    args = parser.parse_args()

    if args.source == "docusaurus":
        try:
            # Загружаем конфигурацию
            config = load_config(args.config)

            # Применяем профиль если указан
            if args.profile and "profiles" in config and args.profile in config["profiles"]:
                profile_config = config["profiles"][args.profile]
                # Объединяем профиль с основной конфигурацией
                config = _merge_profile_config(config, profile_config)
                logger.info(f"Используется профиль: {args.profile}")

            # Объединяем конфигурацию с аргументами командной строки
            merged_config = merge_config_with_args(config, args)

            logger.info("📋 Конфигурация:")
            logger.info(f"   📁 Корневая директория: {merged_config['docs_root']}")
            logger.info(f"   🌐 Базовый URL: {merged_config['site_base_url']}")
            logger.info(f"   📚 Префикс документации: {merged_config['site_docs_prefix']}")
            logger.info(f"   🗄️ Коллекция: {merged_config['collection_name']}")
            logger.info(f"   🔍 Фильтр категории: {merged_config['category_filter'] or 'нет'}")
            logger.info(f"   🔄 Режим: {merged_config['reindex_mode']}")
            logger.info(f"   📦 Размер батча: {merged_config['batch_size']}")

            result = run_docusaurus_indexing(
                docs_root=merged_config["docs_root"],
                site_base_url=merged_config["site_base_url"],
                site_docs_prefix=merged_config["site_docs_prefix"],
                collection_name=merged_config["collection_name"],
                category_filter=merged_config["category_filter"],
                reindex_mode=merged_config["reindex_mode"],
                batch_size=merged_config["batch_size"],
                chunk_max_tokens=merged_config.get("chunk_max_tokens", 600),
                chunk_overlap_tokens=merged_config.get("chunk_overlap_tokens", 120),
                cleaning_config=merged_config.get("cleaning"),
                routing_config=merged_config.get("routing"),
                indexing_config=merged_config.get("indexing")
            )

            if result["success"]:
                logger.success("🎉 Индексация завершена успешно!")
                sys.exit(0)
            else:
                logger.error(f"❌ Индексация завершилась с ошибкой: {result.get('error', 'Неизвестная ошибка')}")
                sys.exit(1)

        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            sys.exit(1)
    else:
        logger.error(f"Неподдерживаемый тип источника: {args.source}")
        sys.exit(1)


if __name__ == "__main__":
    main()
