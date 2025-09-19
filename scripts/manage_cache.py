#!/usr/bin/env python3
"""
Утилита для управления кешем crawling.
"""

from __future__ import annotations

import sys
import os
import argparse
from pathlib import Path

# Добавляем корневую папку проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from ingestion.crawl_cache import get_crawl_cache


def show_cache_stats():
    """Показывает статистику кеша."""
    cache = get_crawl_cache()
    stats = cache.get_cache_stats()
    
    print("📊 Статистика кеша crawling:")
    print(f"  Всего страниц: {stats['total_pages']}")
    print(f"  Размер кеша: {stats['total_size_mb']} MB")
    print(f"  Директория кеша: {stats['cache_dir']}")
    print(f"  Файл индекса: {stats['index_file']}")
    
    if stats['total_pages'] > 0:
        print("\n📋 Закешированные URL:")
        urls = cache.get_cached_urls()
        for i, url in enumerate(sorted(urls), 1):
            cached_page = cache.get_page(url)
            if cached_page:
                print(f"  {i:3d}. {url}")
                print(f"       Тип: {cached_page.page_type}, Размер: {cached_page.content_length} байт")
                print(f"       Кеширован: {cached_page.cached_at}")


def clear_cache():
    """Очищает весь кеш."""
    cache = get_crawl_cache()
    
    stats = cache.get_cache_stats()
    if stats['total_pages'] == 0:
        print("✅ Кеш уже пуст")
        return
    
    print(f"⚠️  Вы собираетесь удалить {stats['total_pages']} закешированных страниц ({stats['total_size_mb']} MB)")
    
    confirm = input("Продолжить? (y/N): ").lower().strip()
    if confirm not in ['y', 'yes', 'да']:
        print("❌ Операция отменена")
        return
    
    cache.clear_cache()
    print("✅ Кеш очищен")


def validate_cache():
    """Проверяет целостность кеша."""
    cache = get_crawl_cache()
    
    print("🔍 Проверка целостности кеша...")
    
    cached_urls = cache.get_cached_urls()
    valid_count = 0
    invalid_count = 0
    
    for url in cached_urls:
        try:
            cached_page = cache.get_page(url)
            if cached_page and cached_page.html:
                valid_count += 1
            else:
                invalid_count += 1
                print(f"❌ Невалидная страница: {url}")
        except Exception as e:
            invalid_count += 1
            print(f"❌ Ошибка загрузки: {url} - {e}")
    
    print(f"\n📊 Результаты проверки:")
    print(f"  ✅ Валидных страниц: {valid_count}")
    print(f"  ❌ Невалидных страниц: {invalid_count}")
    
    if invalid_count > 0:
        print(f"\n⚠️  Найдено {invalid_count} поврежденных записей")
        confirm = input("Удалить поврежденные записи? (y/N): ").lower().strip()
        if confirm in ['y', 'yes', 'да']:
            # Здесь можно добавить логику очистки поврежденных записей
            print("🔧 Очистка поврежденных записей не реализована")


def test_cache_performance():
    """Тестирует производительность кеша."""
    import time
    from ingestion.crawler import crawl_sitemap
    
    print("🚀 Тестирование производительности кеша...")
    
    # Получаем список URL для тестирования
    urls = crawl_sitemap()
    if not urls:
        print("❌ Не удалось получить URL из sitemap")
        return
    
    test_urls = urls[:10]  # Тестируем первые 10 URL
    print(f"Тестируем на {len(test_urls)} URL")
    
    cache = get_crawl_cache()
    
    # Тест загрузки из кеша
    print("\n📖 Тест загрузки из кеша...")
    start_time = time.time()
    
    loaded_count = 0
    for url in test_urls:
        cached_page = cache.get_page(url)
        if cached_page:
            loaded_count += 1
    
    cache_time = time.time() - start_time
    
    print(f"  Загружено из кеша: {loaded_count}/{len(test_urls)} страниц")
    print(f"  Время загрузки: {cache_time:.2f} секунд")
    print(f"  Скорость: {loaded_count/cache_time:.1f} страниц/сек" if cache_time > 0 else "  Скорость: мгновенно")


def rebuild_index():
    """Перестраивает индекс кеша."""
    cache = get_crawl_cache()
    
    print("🔧 Перестройка индекса кеша...")
    
    # Сканируем директорию с файлами страниц
    pages_dir = cache.pages_dir
    if not pages_dir.exists():
        print("❌ Директория кеша не найдена")
        return
    
    page_files = list(pages_dir.glob("*.json"))
    print(f"Найдено {len(page_files)} файлов кеша")
    
    if len(page_files) == 0:
        print("✅ Нет файлов для перестройки индекса")
        return
    
    # Очищаем текущий индекс
    cache._index.clear()
    
    # Восстанавливаем индекс из файлов
    rebuilt_count = 0
    for page_file in page_files:
        try:
            import json
            with open(page_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = data.get('metadata', {})
            if 'url' in metadata:
                from ingestion.crawl_cache import PageCache
                page_cache = PageCache(**metadata)
                page_cache.html = ""  # Не загружаем в память
                page_cache.text = ""
                cache._index[page_cache.url] = page_cache
                rebuilt_count += 1
        except Exception as e:
            logger.warning(f"Failed to rebuild index for {page_file}: {e}")
    
    # Сохраняем восстановленный индекс
    cache._save_index()
    
    print(f"✅ Индекс перестроен: {rebuilt_count} страниц")


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Управление кешем crawling")
    
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Статистика
    subparsers.add_parser('stats', help='Показать статистику кеша')
    
    # Очистка
    subparsers.add_parser('clear', help='Очистить весь кеш')
    
    # Валидация
    subparsers.add_parser('validate', help='Проверить целостность кеша')
    
    # Тест производительности
    subparsers.add_parser('test', help='Тестировать производительность кеша')
    
    # Перестройка индекса
    subparsers.add_parser('rebuild', help='Перестроить индекс кеша')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'stats':
            show_cache_stats()
        elif args.command == 'clear':
            clear_cache()
        elif args.command == 'validate':
            validate_cache()
        elif args.command == 'test':
            test_cache_performance()
        elif args.command == 'rebuild':
            rebuild_index()
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n⚠️ Операция прервана пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()


