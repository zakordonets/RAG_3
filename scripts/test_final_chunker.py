#!/usr/bin/env python3
"""
Финальное тестирование оптимального chunker'а.
"""

from __future__ import annotations

import sys
import os

# Добавляем корневую папку проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from ingestion.chunker import chunk_text
from ingestion.crawl_cache import get_crawl_cache


def test_final_chunker():
    """Тестирует финальную версию chunker'а."""
    logger.info("🎯 Финальное тестирование оптимального chunker'а")

    cache = get_crawl_cache()
    cached_urls = list(cache.get_cached_urls())

    if not cached_urls:
        logger.error("❌ Нет закешированных страниц для тестирования")
        return False

    # Тестируем на 5 страницах
    test_urls = cached_urls[:5]

    total_pages = 0
    total_chunks = 0
    chunk_sizes = []

    for url in test_urls:
        cached_page = cache.get_page(url)
        if not cached_page:
            continue

        chunks = chunk_text(cached_page.html)

        total_pages += 1
        total_chunks += len(chunks)

        logger.info(f"\n📄 {url}")
        logger.info(f"  Исходный размер: {len(cached_page.html)} символов")
        logger.info(f"  Создано чанков: {len(chunks)}")

        for i, chunk in enumerate(chunks, 1):
            tokens = len(chunk.split())
            chunk_sizes.append(tokens)
            status = "✅" if 60 <= tokens <= 250 else "⚠️"
            logger.info(f"    Чанк {i}: {tokens} токенов {status}")

    if chunk_sizes:
        avg_size = sum(chunk_sizes) / len(chunk_sizes)
        min_size = min(chunk_sizes)
        max_size = max(chunk_sizes)

        logger.info(f"\n📊 Итоговая статистика:")
        logger.info(f"  Страниц: {total_pages}")
        logger.info(f"  Чанков: {total_chunks}")
        logger.info(f"  Чанков на страницу: {total_chunks/total_pages:.1f}")
        logger.info(f"  Средний размер: {avg_size:.0f} токенов")
        logger.info(f"  Диапазон: {min_size}-{max_size} токенов")

        # Оценка качества
        optimal_chunks = sum(1 for size in chunk_sizes if 60 <= size <= 250)
        success_rate = optimal_chunks / len(chunk_sizes) * 100

        logger.info(f"  Оптимальных чанков: {optimal_chunks}/{len(chunk_sizes)} ({success_rate:.1f}%)")

        if success_rate >= 80:
            logger.success("✅ Chunker работает отлично!")
            return True
        elif success_rate >= 60:
            logger.warning("⚠️ Chunker работает приемлемо")
            return True
        else:
            logger.error("❌ Chunker требует доработки")
            return False

    return False


if __name__ == "__main__":
    success = test_final_chunker()
    sys.exit(0 if success else 1)
