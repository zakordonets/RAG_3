#!/usr/bin/env python3
"""
Тест свежей загрузки страниц без кеша
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
from app.abstractions.data_source import plugin_manager
from app.services.optimized_pipeline import run_optimized_indexing
from ingestion.chunker import chunk_text

# Import data sources
from app.sources import edna_docs_source


def test_fresh_crawl():
    """Тест свежей загрузки одной страницы"""
    print("🔍 ТЕСТ СВЕЖЕЙ ЗАГРУЗКИ СТРАНИЦЫ")
    print("=" * 50)

    try:
        # Получаем источник данных БЕЗ кеша
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": False,  # Отключаем кеш!
            "max_pages": 1
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        crawl_result = source.fetch_pages(max_pages=1)

        if not crawl_result.pages:
            print("❌ Не удалось загрузить страницы")
            return False

        page = crawl_result.pages[0]
        print(f"📄 Страница: {page.title}")
        print(f"   URL: {page.url}")
        print(f"   Тип: {page.page_type.value}")
        print(f"   Длина контента: {len(page.content)} символов")

        if len(page.content) > 0:
            print(f"   ✅ Контент загружен успешно!")
            print(f"   Первые 200 символов: {page.content[:200]}...")

            # Тест chunking
            chunks = chunk_text(page.content)
            print(f"   🔧 Сгенерировано чанков: {len(chunks)}")

            if chunks:
                for i, chunk in enumerate(chunks[:2]):
                    print(f"      Чанк {i+1}: {len(chunk)} символов")
                return True
            else:
                print(f"   ❌ Чанки не сгенерированы")
                return False
        else:
            print(f"   ❌ Контент пустой!")
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_optimized_pipeline_fresh():
    """Тест оптимизированного pipeline с свежей загрузкой"""
    print("\n🔍 ТЕСТ ОПТИМИЗИРОВАННОГО PIPELINE (СВЕЖАЯ ЗАГРУЗКА)")
    print("=" * 50)

    try:
        # Запускаем индексацию БЕЗ кеша
        result = run_optimized_indexing(
            source_name="edna_docs",
            max_pages=3,  # Небольшое количество для теста
            chunk_strategy="adaptive"
        )

        print(f"📊 Результаты индексации:")
        print(f"   Успех: {'✅' if result['success'] else '❌'}")
        print(f"   Страниц: {result.get('pages', 0)}")
        print(f"   Чанков: {result.get('chunks', 0)}")
        print(f"   Длительность: {result.get('duration', 0):.2f}s")

        if result.get('errors', 0) > 0:
            print(f"   Ошибки: {result['errors']}")

        return result['success']

    except Exception as e:
        print(f"❌ Ошибка pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ СВЕЖЕЙ ЗАГРУЗКИ")
    print("=" * 80)

    results = []

    # Тест 1: Свежая загрузка одной страницы
    result1 = test_fresh_crawl()
    results.append(("Свежая загрузка", result1))

    # Тест 2: Оптимизированный pipeline
    result2 = test_optimized_pipeline_fresh()
    results.append(("Pipeline свежая загрузка", result2))

    # Итоги
    print("\n" + "=" * 80)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 80)

    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}: {'OK' if result else 'Проблема'}")

    successful_tests = sum(1 for _, result in results if result)
    print(f"\n📈 Пройдено тестов: {successful_tests}/{len(results)}")

    if successful_tests == len(results):
        print("🎉 Все тесты пройдены! Система работает корректно.")
    else:
        print("⚠️ Обнаружены проблемы, требующие исправления.")


if __name__ == "__main__":
    main()
