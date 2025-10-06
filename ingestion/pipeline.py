from __future__ import annotations

import time
import re
from typing import Any, Optional
from loguru import logger
from tqdm import tqdm
from ingestion.crawlers import CrawlerFactory
from app.config.sources_config import get_source_config
from ingestion.processors.content_processor import ContentProcessor
from ingestion.chunkers import chunk_text
from app.services.indexing.metadata_aware_indexer import MetadataAwareIndexer
from app.services.indexing.optimized_pipeline import run_optimized_indexing
from app.config import CONFIG
from app.utils import clean_text_for_processing, validate_text_quality, safe_batch_text_processing

def _resolve_content_strategy(page: dict[str, Any], default_strategy: str | None) -> str:
    explicit = page.get("content_strategy")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    raw = page.get("text") or page.get("html") or ""
    normalized = (raw or '').lstrip('\ufeff \n\n\t')
    normalized_lower = normalized.lower()
    sample = normalized[:1000]
    sample_lower = normalized_lower[:1000]

    if sample.startswith("Title:") and "URL Source:" in sample:
        return 'jina'
    if sample_lower.startswith("<!doctype html") or sample_lower.startswith("<html") or '<html' in sample_lower:
        return 'html'
    if sample.startswith("#") or sample.startswith("---"):
        return 'markdown'
    if '<' not in sample_lower and '>' not in sample_lower and '\n' in sample:
        return 'markdown'

    fallback = (default_strategy or 'auto').strip()
    if fallback in ('jina', 'jina_reader'):
        return 'auto'
    if fallback in ('html', 'markdown'):
        return fallback
    return 'auto'


def _resolve_page_limit(requested: int | None) -> int | None:
    """Определяет лимит страниц с учетом конфигурации."""
    if requested is not None and requested > 0:
        return requested
    if CONFIG.crawl_max_pages > 0:
        return CONFIG.crawl_max_pages
    return None



# Функция classify_page удалена - теперь используется ContentProcessor для определения типа страницы


def crawl_and_index(incremental: bool = True, strategy: str = "jina", use_cache: bool = True, reindex_mode: str = "auto", max_pages: int = None, source_name: Optional[str] = None, cleanup_cache: bool = False) -> dict[str, Any]:
    """Полный цикл: краулинг → чанкинг → эмбеддинги → upsert в Qdrant.

    Args:
        incremental: если True — использует инкрементальное обновление
        strategy: стратегия crawling (jina, http)
        use_cache: использовать кеширование результатов crawling
        reindex_mode: режим переиндексации:
            - "auto": только новые/измененные страницы (по умолчанию)
            - "force": переиндексировать все страницы
            - "cache_only": использовать только кешированные страницы
        max_pages: максимальное количество страниц для обработки
        source_name: имя источника данных
        cleanup_cache: очищать устаревшие записи из кеша (по умолчанию False)

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

    # 1) Используем новую архитектуру crawlers
    page_strategy = strategy
    page_limit = _resolve_page_limit(max_pages)

    # Получаем конфигурацию источника
    if source_name:
        try:
            source_config = get_source_config(source_name)
        except Exception as e:
            logger.warning(f"Не удалось загрузить конфиг источника '{source_name}': {e}. Использую параметры функции.")
            # Создаем временную конфигурацию
            from app.config.sources_config import SourceConfig, SourceType
            source_config = SourceConfig(
                name=source_name or "default",
                source_type=SourceType.DOCS_SITE,
                base_url=CONFIG.crawl_start_url,
                strategy=strategy,
                use_cache=use_cache,
                max_pages=max_pages
            )
    else:
        # Создаем временную конфигурацию
        from app.config.sources_config import SourceConfig, SourceType
        source_config = SourceConfig(
            name="default",
            source_type=SourceType.DOCS_SITE,
            base_url=CONFIG.crawl_start_url,
            strategy=strategy,
            use_cache=use_cache,
            max_pages=max_pages
        )

    # Создаем crawler через фабрику
    crawler = CrawlerFactory.create_crawler(source_config)

    if reindex_mode == "cache_only":
        logger.info("Режим cache_only: используем только кешированные страницы")
        from ingestion.crawl_cache import get_crawl_cache
        cache = get_crawl_cache()
        pages = []

        for url in cache.get_cached_urls():
            cached_page = cache.get_page(url)
            if cached_page:
                from ingestion.crawlers import CrawlResult
                pages.append(CrawlResult(
                    url=url,
                    html=cached_page.html,
                    text=cached_page.text,
                    title=cached_page.title or "",
                    metadata={"cached": True, "content_strategy": getattr(cached_page, "content_strategy", "auto")}
                ))

                # Ограничиваем количество страниц для тестирования
                if page_limit and len(pages) >= page_limit:
                    break

        logger.info(f"Загружено {len(pages)} страниц из кеша")
    else:
        # Используем новый crawler
        pages = crawler.crawl(max_pages=page_limit, strategy=strategy, use_cache=use_cache, cleanup_cache=cleanup_cache)
        page_strategy = strategy
    # Собираем все чанки для батчевой обработки
    all_chunks = []
    logger.info("Обрабатываем страницы и собираем чанки...")

    # НОВОЕ: единый процессор контента (рефакторинг вместо universal_loader)
    processor = ContentProcessor()

    html_tag_re = re.compile(r"<[^>]+>")

    with tqdm(total=len(pages), desc="Processing pages") as pbar:
        for p in pages:
            # Поддерживаем как объекты, так и словари
            if hasattr(p, 'url'):
                url = p.url
                raw_content = p.text or p.html or ""
            else:
                # Если это словарь
                url = p.get('url', '')
                raw_content = p.get('text') or p.get('html') or ""

            if not raw_content:
                logger.warning(f"Пустой контент для {url}, пропускаем")
                pbar.update(1)
                continue

            page_strategy_for_page = page_strategy

            if page_strategy_for_page == "html":
                html_content = p.html or ""
                text_content = p.text or ""
                html_stripped = html_content.strip()
                text_stripped = text_content.strip()

                lacks_html_markup = not html_tag_re.search(html_stripped)
                html_equals_text = html_stripped == text_stripped and html_stripped != ""

                if html_content and (lacks_html_markup or html_equals_text):
                    page_strategy_for_page = "markdown"

            # Используем новый ContentProcessor (вместо universal_loader)
            # ВНИМАНИЕ: сигнатура process(raw_content, url, strategy)
            try:
                processed = processor.process(raw_content, url, page_strategy_for_page)

                # Извлекаем унифицированные данные
                raw_text = processed.content or ''
                title = processed.title or 'Untitled'
                page_type = processed.page_type  # ContentProcessor уже определил тип страницы

                # Безопасная обработка текста с исправлением кодировок
                text = clean_text_for_processing(raw_text)

                # Проверяем качество текста
                is_valid, error_msg = validate_text_quality(text, min_length=20)
                if not is_valid:
                    logger.warning(f"Низкое качество текста для {url}: {error_msg}, пропускаем")
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
                    "content_type": page_strategy_for_page if page_strategy_for_page in ["jina", "html", "markdown"] else "auto",
                    "page_type": page_type,
                    "source": "docs-site",
                    "language": "ru",
                    "title": title,
                    "text": ct,
                    "indexed_via": page_strategy_for_page,
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
    from app.services.core.embeddings import _get_optimal_backend_strategy
    optimal_backend = _get_optimal_backend_strategy()
    logger.info(f"  Оптимальная стратегия: {optimal_backend}")

    try:
        stats = crawl_and_index(incremental=False)
        logger.success(f"✅ Переиндексация завершена!")
        logger.success(f"📊 Статистика: {stats['pages']} страниц, {stats['chunks']} чанков")
    except Exception as e:
        logger.error(f"❌ Ошибка переиндексации: {e}")
        raise
