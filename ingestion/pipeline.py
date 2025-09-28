from __future__ import annotations

import time
from typing import Any
from loguru import logger
from tqdm import tqdm
from ingestion.crawler import crawl, crawl_mkdocs_index, crawl_sitemap, crawl_with_sitemap_progress
from ingestion.parsers import parse_api_documentation, parse_release_notes, parse_faq_content, parse_guides
from ingestion.chunker import chunk_text, text_hash
from ingestion.indexer import upsert_chunks


def classify_page(url: str) -> str:
    low = url.lower()
    if "faq" in low:
        return "faq"
    if "api" in low:
        return "api"
    if "release" in low or "changelog" in low:
        return "release_notes"
    return "guide"


def crawl_and_index(incremental: bool = True, strategy: str = "jina", use_cache: bool = True, reindex_mode: str = "auto", max_pages: int = None) -> dict[str, Any]:
    """Полный цикл: краулинг → чанкинг → эмбеддинги → upsert в Qdrant.

    Args:
        incremental: если True — использует инкрементальное обновление
        strategy: стратегия crawling (jina, http, browser)
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
        logger.warning("MkDocs index недоступен, пробуем браузерный обход...")
        pages = crawl(strategy="browser")
    # Собираем все чанки для батчевой обработки
    all_chunks = []
    logger.info("Обрабатываем страницы и собираем чанки...")

    with tqdm(total=len(pages), desc="Processing pages") as pbar:
        for p in pages:
            url = p["url"]
            html = p.get("html") or ""
            raw_text = p.get("text")
            page_type = classify_page(url)

            # Извлечение основного текста (упрощённо для старта)
            if raw_text:
                text = raw_text
                title = p.get("title")

                # Улучшенное извлечение заголовка из Jina Reader текста
                if not title and raw_text.startswith("Title:"):
                    # Извлекаем заголовок из формата "Title: Заголовок | Сайт"
                    try:
                        title_line = raw_text.split('\n')[0]  # Первая строка
                        if "Title:" in title_line:
                            title_part = title_line.split("Title:")[1].strip()
                            if "|" in title_part:
                                title = title_part.split("|")[0].strip()
                            else:
                                title = title_part
                    except Exception:
                        pass

            else:
                parsed = parse_guides(html)
                text = parsed.get("text") or html
                title = parsed.get("title")

            chunks_text = chunk_text(text)

            # Fallback для заголовка, если он пустой
            if not title:
                # Извлекаем заголовок из URL
                url_parts = url.split('/')
                title = url_parts[-1].replace('-', ' ').replace('_', ' ').title()

            for i, ct in enumerate(chunks_text):
                all_chunks.append({
                    "text": ct,
                    "payload": {
                        "url": url,
                        "page_type": page_type,
                        "source": "docs-site",
                        "language": "ru",
                        "title": title,
                        "text": ct,
                        "indexed_via": strategy,
                        "indexed_at": time.time(),
                        "chunk_index": i,
                        "content_length": len(text),
                    },
                })
            pbar.update(1)

    logger.info(f"Собрано {len(all_chunks)} чанков, начинаем батчевую индексацию...")

    # Батчевая индексация с правильным размером батча
    from app.config import CONFIG
    batch_size = CONFIG.embedding_batch_size
    total_chunks = 0

    with tqdm(total=len(all_chunks), desc="Indexing chunks", unit="chunk") as pbar:
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(all_chunks) + batch_size - 1) // batch_size

            logger.info(f"Индексируем батч {batch_num}/{total_batches}: {len(batch)} чанков")
            indexed = upsert_chunks(batch)
            total_chunks += indexed
            pbar.update(len(batch))
    return {"pages": len(pages), "chunks": total_chunks}


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
