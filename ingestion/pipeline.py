from __future__ import annotations

import time
from typing import Any, Optional
from loguru import logger
from tqdm import tqdm
from ingestion.crawler import crawl, crawl_mkdocs_index, crawl_sitemap, crawl_with_sitemap_progress
from ingestion.parsers_migration import extract_url_metadata
from ingestion.processors.content_processor import ContentProcessor
from app.sources_registry import get_source_config
from ingestion.chunker import chunk_text, text_hash
from ingestion.indexer import upsert_chunks
from app.services.metadata_aware_indexer import MetadataAwareIndexer
from app.services.optimized_pipeline import run_optimized_indexing


# Функция classify_page удалена - теперь используется ContentProcessor для определения типа страницы


def crawl_and_index(incremental: bool = True, strategy: str = "jina", use_cache: bool = True, reindex_mode: str = "auto", max_pages: int = None, source_name: Optional[str] = None) -> dict[str, Any]:
    """Полный цикл: краулинг → чанкинг → эмбеддинги → upsert в Qdrant.

    Args:
        incremental: если True — использует инкрементальное обновление
        strategy: стратегия crawling (jina, http)
        use_cache: использовать кеширование результатов crawling
        reindex_mode: режим переиндексации:
            - "auto": только новые/измененные страницы (по умолчанию)
            - "force": переиндексировать все страницы
            - "cache_only": использовать только кешированные страницы

    Returns:
        Статистика по страницам и чанкам
    """
    logger.info(f"Начинаем {'инкрементальную ' if incremental else ''}индексацию")
    logger.info(f"Параметры: strategy={strategy}, use_cache={use_cache}, reindex_mode={reindex_mode}")

    # Если указан источник, применяем централизованную конфигурацию
    if source_name:
        try:
            cfg = get_source_config(source_name)
            strategy = cfg.strategy or strategy
            use_cache = cfg.use_cache if cfg.use_cache is not None else use_cache
            if max_pages is None and cfg.max_pages:
                max_pages = cfg.max_pages
            logger.info(f"Источник: {source_name} | strategy={strategy} use_cache={use_cache} max_pages={max_pages}")
        except Exception as e:
            logger.warning(f"Не удалось загрузить конфиг источника '{source_name}': {e}. Использую параметры функции.")

    # 1) Используем улучшенный crawling с кешированием
    if reindex_mode == "cache_only":
        logger.info("Режим cache_only: используем только кешированные страницы")
        from ingestion.crawl_cache import get_crawl_cache
        cache = get_crawl_cache()
        pages = []

        for url in cache.get_cached_urls():
            cached_page = cache.get_page(url)
            if cached_page:
                pages.append({
                    "url": url,
                    "html": cached_page.html,
                    "text": cached_page.text,
                    "title": cached_page.title,
                    "cached": True
                })

                # Ограничиваем количество страниц для тестирования
                if max_pages and len(pages) >= max_pages:
                    break

        logger.info(f"Загружено {len(pages)} страниц из кеша")
    else:
        pages = crawl_with_sitemap_progress(strategy=strategy, use_cache=use_cache, max_pages=max_pages)

    # 2) Фолбэки если основной метод не сработал
    if not pages:
        logger.warning("Sitemap crawling не дал результатов, пробуем MkDocs index...")
        pages = crawl_mkdocs_index()
    if not pages:
        logger.warning("MkDocs index недоступен, пробуем HTTP обход...")
        pages = crawl(strategy="http")
    # Собираем все чанки для батчевой обработки
    all_chunks = []
    logger.info("Обрабатываем страницы и собираем чанки...")

    # НОВОЕ: единый процессор контента (рефакторинг вместо universal_loader)
    processor = ContentProcessor()

    with tqdm(total=len(pages), desc="Processing pages") as pbar:
        for p in pages:
            url = p["url"]
            raw_content = p.get("text") or p.get("html") or ""

            if not raw_content:
                logger.warning(f"Пустой контент для {url}, пропускаем")
                pbar.update(1)
                continue

            # Используем новый ContentProcessor (вместо universal_loader)
            # ВНИМАНИЕ: сигнатура process(raw_content, url, strategy)
            try:
                processed = processor.process(raw_content, url, strategy)

                # Извлекаем унифицированные данные
                text = processed.content or ''
                title = processed.title or 'Untitled'
                page_type = processed.page_type  # ContentProcessor уже определил тип страницы

                if not text:
                    logger.warning(f"Пустой контент после парсинга для {url}, пропускаем")
                    pbar.update(1)
                    continue

            except Exception as e:
                logger.warning(f"Ошибка парсинга для {url}: {e}, пропускаем страницу")
                pbar.update(1)
                continue

            # Генерируем чанки
            chunks_text = chunk_text(text)

            if not chunks_text:
                logger.warning(f"Не удалось создать чанки для {url}, пропускаем")
                pbar.update(1)
                continue

            # Создаем чанки с обогащенными метаданными
            for i, ct in enumerate(chunks_text):
                # Базовый payload
                payload = {
                    "url": url,
                    "content_type": strategy if strategy in ["jina", "html"] else "auto",
                    "page_type": page_type,
                    "source": "docs-site",
                    "language": "ru",
                    "title": title,
                    "text": ct,
                    "indexed_via": strategy,
                    "indexed_at": time.time(),
                    "chunk_index": i,
                    "content_length": len(text),
                }

                # Добавляем все дополнительные метаданные из нового процессора
                for key, value in (processed.metadata or {}).items():
                    if key not in ['url', 'title', 'content', 'page_type'] and value is not None:
                        payload[key] = value

                all_chunks.append({
                    "text": ct,
                    "payload": payload,
                })
            pbar.update(1)

    logger.info(f"Собрано {len(all_chunks)} чанков, начинаем enhanced metadata-aware индексацию...")

    # Enhanced metadata-aware индексация
    metadata_indexer = MetadataAwareIndexer()
    total_chunks = 0

    # Используем enhanced metadata indexer для всей коллекции чанков
    indexed = metadata_indexer.index_chunks_with_metadata(all_chunks)
    total_chunks = indexed
    return {"pages": len(pages), "chunks": total_chunks}


def crawl_and_index_optimized(
    source_name: str = "edna_docs",
    max_pages: Optional[int] = None,
    chunk_strategy: str = "adaptive"
) -> dict[str, Any]:
    """Optimized crawling and indexing using new architecture.

    Args:
        source_name: Name of the data source to use
        max_pages: Maximum number of pages to process
        chunk_strategy: Chunking strategy ("adaptive" or "standard")

    Returns:
        Dictionary with indexing results and statistics
    """
    logger.info(f"Starting optimized indexing with source: {source_name}")

    try:
        # Use the new optimized pipeline
        result = run_optimized_indexing(
            source_name=source_name,
            max_pages=max_pages,
            chunk_strategy=chunk_strategy
        )

        if result["success"]:
            logger.info(f"✅ Optimized indexing completed successfully:")
            logger.info(f"   Pages: {result['pages']}")
            logger.info(f"   Chunks: {result['chunks']}")
            logger.info(f"   Duration: {result['duration']:.2f}s")
        else:
            logger.error(f"❌ Optimized indexing failed: {result.get('error', 'Unknown error')}")

        return result

    except Exception as e:
        error_msg = f"Optimized indexing failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "pages": 0,
            "chunks": 0,
            "duration": 0.0
        }


if __name__ == "__main__":
    logger.info("🚀 Запуск переиндексации с BGE-M3 unified embeddings...")

    # Показываем текущую конфигурацию
    from app.config import CONFIG
    logger.info(f"Конфигурация эмбеддингов:")
    logger.info(f"  EMBEDDINGS_BACKEND: {CONFIG.embeddings_backend}")
    logger.info(f"  EMBEDDING_DEVICE: {CONFIG.embedding_device}")
    logger.info(f"  USE_SPARSE: {CONFIG.use_sparse}")
    logger.info(f"  EMBEDDING_MAX_LENGTH_DOC: {CONFIG.embedding_max_length_doc}")
    logger.info(f"  EMBEDDING_BATCH_SIZE: {CONFIG.embedding_batch_size}")

    # Определяем оптимальную стратегию
    from app.services.bge_embeddings import _get_optimal_backend_strategy
    optimal_backend = _get_optimal_backend_strategy()
    logger.info(f"  Оптимальная стратегия: {optimal_backend}")

    try:
        stats = crawl_and_index(incremental=False)
        logger.success(f"✅ Переиндексация завершена!")
        logger.success(f"📊 Статистика: {stats['pages']} страниц, {stats['chunks']} чанков")
    except Exception as e:
        logger.error(f"❌ Ошибка переиндексации: {e}")
        raise
