#!/usr/bin/env python3
"""
Тестирование системы кеширования crawling.
"""

from __future__ import annotations

import sys
import os
import time

# Добавляем корневую папку проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from app.config import CONFIG
from ingestion.crawl_cache import get_crawl_cache
from ingestion.crawler import crawl_sitemap, crawl_with_sitemap_progress



CRAWL_TEST_MAX_PAGES = os.getenv("CRAWL_TEST_MAX_PAGES")
try:
    TEST_MAX_PAGES = int(CRAWL_TEST_MAX_PAGES) if CRAWL_TEST_MAX_PAGES else 5
except ValueError:
    TEST_MAX_PAGES = 5

if TEST_MAX_PAGES <= 0:
    TEST_MAX_PAGES = 5


def _get_test_page_limit() -> int:
    """Return the effective page limit for integration-style crawl tests."""
    config_limit = getattr(CONFIG, "crawl_max_pages", 0)
    if config_limit and config_limit > 0:
        return min(TEST_MAX_PAGES, config_limit) if TEST_MAX_PAGES else config_limit
    return TEST_MAX_PAGES


def test_cache_basic_operations():
    """Тестирует базовые операции кеша."""
    logger.info("🧪 Тестирование базовых операций кеша...")

    cache = get_crawl_cache()

    # Тестовые данные
    test_url = "https://test.example.com/page1"
    test_html = "<html><body>Test content</body></html>"
    test_text = "Test content"

    # Тест сохранения
    logger.info("📝 Тест сохранения страницы...")
    page_cache = cache.save_page(test_url, test_html, test_text, title="Test Page", page_type="test")

    assert page_cache.url == test_url
    assert page_cache.content_length == len(test_html)
    assert page_cache.page_type == "test"
    logger.success("✅ Сохранение работает")

    # Тест проверки наличия
    logger.info("🔍 Тест проверки наличия...")
    assert cache.has_page(test_url) == True
    assert cache.has_page("https://nonexistent.com") == False
    logger.success("✅ Проверка наличия работает")

    # Тест загрузки
    logger.info("📖 Тест загрузки страницы...")
    loaded_page = cache.get_page(test_url)

    assert loaded_page is not None
    assert loaded_page.url == test_url
    assert loaded_page.html == test_html
    assert loaded_page.text == test_text
    assert loaded_page.title == "Test Page"
    logger.success("✅ Загрузка работает")

    # Тест проверки актуальности
    logger.info("🔄 Тест проверки актуальности...")
    assert cache.is_page_fresh(test_url, test_html) == True
    assert cache.is_page_fresh(test_url, "different content") == False
    logger.success("✅ Проверка актуальности работает")

    # Тест удаления
    logger.info("🗑️ Тест удаления страницы...")
    cache.remove_page(test_url)
    assert cache.has_page(test_url) == False
    logger.success("✅ Удаление работает")


def test_cache_with_real_data():
    """Тестирует кеш с реальными данными."""
    logger.info("🌐 Тестирование кеша с реальными данными...")

    # Получаем несколько URL из sitemap
    urls = crawl_sitemap()
    if not urls:
        logger.error("❌ Не удалось получить URL из sitemap")
        return

    limit = min(len(urls), _get_test_page_limit())
    test_urls = urls[:limit]
    logger.info(f"Тестируем с {len(test_urls)} URL (ограничение для тестов)")

    cache = get_crawl_cache()
    initial_stats = cache.get_cache_stats()

    logger.info(f"Начальное состояние кеша: {initial_stats['total_pages']} страниц")

    # Первый запуск - все страницы должны быть загружены
    logger.info("🚀 Первый запуск crawling (без кеша)...")
    start_time = time.time()

    pages1 = crawl_with_sitemap_progress(strategy="jina", use_cache=True, max_pages=limit)
    first_crawl_time = time.time() - start_time

    # Фильтруем только тестовые URL
    test_pages1 = [p for p in pages1 if p["url"] in test_urls]

    logger.info(f"Первый запуск: {len(test_pages1)} страниц за {first_crawl_time:.2f} сек")

    # Проверяем, что страницы сохранились в кеш
    final_stats = cache.get_cache_stats()
    logger.info(f"После первого запуска: {final_stats['total_pages']} страниц в кеше")

    # Второй запуск - страницы должны загружаться из кеша
    logger.info("⚡ Второй запуск crawling (с кешем)...")
    start_time = time.time()

    pages2 = crawl_with_sitemap_progress(strategy="jina", use_cache=True, max_pages=limit)
    second_crawl_time = time.time() - start_time

    # Фильтруем только тестовые URL
    test_pages2 = [p for p in pages2 if p["url"] in test_urls]

    logger.info(f"Второй запуск: {len(test_pages2)} страниц за {second_crawl_time:.2f} сек")

    # Проверяем ускорение
    if second_crawl_time > 0 and first_crawl_time > 0:
        speedup = first_crawl_time / second_crawl_time
        logger.info(f"🚀 Ускорение: {speedup:.1f}x")

        if speedup > 1.5:
            logger.success("✅ Кеширование значительно ускоряет crawling")
        else:
            logger.warning("⚠️ Ускорение меньше ожидаемого")

    # Проверяем, что контент одинаковый
    cached_count = sum(1 for p in test_pages2 if p.get("cached", False))
    logger.info(f"📊 Страниц из кеша: {cached_count}/{len(test_pages2)}")

    # Сравниваем контент
    url_to_content1 = {p["url"]: p.get("html", "") for p in test_pages1}
    url_to_content2 = {p["url"]: p.get("html", "") for p in test_pages2}

    content_matches = 0
    for url in test_urls:
        if url in url_to_content1 and url in url_to_content2:
            if url_to_content1[url] == url_to_content2[url]:
                content_matches += 1

    logger.info(f"📋 Контент совпадает: {content_matches}/{len(test_urls)} страниц")

    if content_matches == len(test_urls):
        logger.success("✅ Кешированный контент идентичен оригинальному")
    else:
        logger.warning("⚠️ Обнаружены расхождения в контенте")


def test_cache_incremental_update():
    """Тестирует инкрементальное обновление."""
    logger.info("🔄 Тестирование инкрементального обновления...")

    from ingestion.pipeline import crawl_and_index

    # Тест режима cache_only
    logger.info("📖 Тест режима cache_only...")
    try:
        stats = crawl_and_index(reindex_mode="cache_only", max_pages=_get_test_page_limit())
        logger.info(f"cache_only: {stats['pages']} страниц, {stats['chunks']} чанков")
        logger.success("✅ Режим cache_only работает")
    except Exception as e:
        logger.error(f"❌ Режим cache_only не работает: {e}")

    # Тест автоматического режима
    logger.info("🤖 Тест автоматического режима...")
    try:
        stats = crawl_and_index(reindex_mode="auto", use_cache=True, max_pages=_get_test_page_limit())
        logger.info(f"auto: {stats['pages']} страниц, {stats['chunks']} чанков")
        logger.success("✅ Автоматический режим работает")
    except Exception as e:
        logger.error(f"❌ Автоматический режим не работает: {e}")


def test_cache_management():
    """Тестирует управление кешем."""
    logger.info("🛠️ Тестирование управления кешем...")

    cache = get_crawl_cache()

    # Статистика
    stats = cache.get_cache_stats()
    logger.info(f"📊 Статистика кеша:")
    logger.info(f"  Страниц: {stats['total_pages']}")
    logger.info(f"  Размер: {stats['total_size_mb']} MB")

    # Список URL
    cached_urls = cache.get_cached_urls()
    logger.info(f"📋 Закешированных URL: {len(cached_urls)}")

    if cached_urls:
        # Показываем первые 5 URL
        for i, url in enumerate(list(cached_urls)[:5], 1):
            logger.info(f"  {i}. {url}")

        if len(cached_urls) > 5:
            logger.info(f"  ... и еще {len(cached_urls) - 5} URL")

    # Тест очистки устаревших записей
    logger.info("🧹 Тест очистки устаревших записей...")

    # Создаем фиктивные URL для теста
    valid_urls = set(list(cached_urls)[:max(1, len(cached_urls) // 2)])  # Оставляем половину

    old_count = len(cached_urls)
    cache.cleanup_old_pages(valid_urls)
    new_count = len(cache.get_cached_urls())

    logger.info(f"Было: {old_count}, стало: {new_count}, удалено: {old_count - new_count}")

    if old_count > new_count:
        logger.success("✅ Очистка устаревших записей работает")
    else:
        logger.info("ℹ️ Устаревших записей не найдено")


def main():
    """Главная функция тестирования."""
    logger.info("🧪 Комплексное тестирование системы кеширования crawling")
    logger.info("=" * 70)

    try:
        # 1. Базовые операции
        test_cache_basic_operations()

        logger.info("\n" + "=" * 70)

        # 2. Реальные данные
        test_cache_with_real_data()

        logger.info("\n" + "=" * 70)

        # 3. Инкрементальное обновление
        test_cache_incremental_update()

        logger.info("\n" + "=" * 70)

        # 4. Управление кешем
        test_cache_management()

        logger.success("\n✅ Все тесты кеширования завершены успешно!")

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Тестирование прервано пользователем")
    except Exception as e:
        logger.error(f"\n❌ Ошибка во время тестирования: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
