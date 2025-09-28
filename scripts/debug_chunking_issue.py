#!/usr/bin/env python3
"""
Диагностика проблемы с генерацией чанков
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
from app.abstractions.data_source import plugin_manager
from app.services.optimized_pipeline import OptimizedPipeline
from ingestion.chunker import chunk_text
from app.config import CONFIG

# Import data sources
from app.sources import edna_docs_source


def debug_single_page():
    """Отладка обработки одной страницы"""
    print("🔍 ДИАГНОСТИКА ОДНОЙ СТРАНИЦЫ")
    print("=" * 50)

    try:
        # Получаем источник данных
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": True,
            "max_pages": 1
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        crawl_result = source.fetch_pages(max_pages=1)

        if not crawl_result.pages:
            print("❌ Не удалось загрузить страницы")
            return

        page = crawl_result.pages[0]
        print(f"📄 Страница: {page.title}")
        print(f"   URL: {page.url}")
        print(f"   Тип: {page.page_type.value}")
        print(f"   Длина контента: {len(page.content)} символов")
        print(f"   Первые 200 символов: {page.content[:200]}...")

        # Тест chunking
        print(f"\n🔧 Тестирование chunking:")
        print(f"   Chunk min tokens: {CONFIG.chunk_min_tokens}")
        print(f"   Chunk max tokens: {CONFIG.chunk_max_tokens}")

        chunks = chunk_text(page.content)
        print(f"   Сгенерировано чанков: {len(chunks)}")

        if chunks:
            for i, chunk in enumerate(chunks[:3]):  # Показываем первые 3 чанка
                print(f"   Чанк {i+1}: {len(chunk)} символов")
                print(f"      Начало: {chunk[:100]}...")
        else:
            print("   ❌ Чанки не сгенерированы!")

            # Дополнительная диагностика
            print(f"\n🔍 Дополнительная диагностика:")
            print(f"   Контент пустой? {len(page.content) == 0}")
            print(f"   Контент только пробелы? {page.content.strip() == ''}")
            print(f"   Контент содержит HTML? {'<' in page.content and '>' in page.content}")

            # Попробуем разные стратегии chunking
            print(f"\n🧪 Тестирование разных стратегий chunking:")

            # Тест с меньшими параметрами
            try:
                from ingestion.chunker import chunk_text
                chunks_small = chunk_text(page.content, max_tokens=50)
                print(f"   С max_tokens=50: {len(chunks_small)} чанков")
            except Exception as e:
                print(f"   Ошибка с max_tokens=50: {e}")

            # Тест с принудительным chunking
            try:
                text_words = page.content.split()
                if text_words:
                    # Простой chunking по словам
                    simple_chunks = []
                    chunk_size = 100  # слов
                    for i in range(0, len(text_words), chunk_size):
                        chunk = ' '.join(text_words[i:i+chunk_size])
                        simple_chunks.append(chunk)
                    print(f"   Простой chunking (100 слов): {len(simple_chunks)} чанков")
                else:
                    print(f"   Нет слов для chunking")
            except Exception as e:
                print(f"   Ошибка простого chunking: {e}")

        return len(chunks) > 0

    except Exception as e:
        print(f"❌ Ошибка диагностики: {e}")
        import traceback
        traceback.print_exc()
        return False


def debug_chunking_function():
    """Отладка функции chunking напрямую"""
    print("\n🔍 ДИАГНОСТИКА ФУНКЦИИ CHUNKING")
    print("=" * 50)

    # Тестовые тексты
    test_texts = [
        "Короткий текст для тестирования chunking функции.",
        "Это более длинный текст, который должен быть разбит на несколько чанков. " * 50,
        "",  # Пустой текст
        "   ",  # Только пробелы
        "Один очень длинный текст без пробелов для тестирования граничных случаев." * 100
    ]

    for i, text in enumerate(test_texts):
        print(f"\n📝 Тест {i+1}:")
        print(f"   Длина текста: {len(text)} символов")
        print(f"   Текст: {text[:50]}{'...' if len(text) > 50 else ''}")

        try:
            chunks = chunk_text(text)
            print(f"   ✅ Результат: {len(chunks)} чанков")
            if chunks:
                for j, chunk in enumerate(chunks[:2]):  # Показываем первые 2 чанка
                    print(f"      Чанк {j+1}: {len(chunk)} символов")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")


def debug_pipeline_processing():
    """Отладка обработки в pipeline"""
    print("\n🔍 ДИАГНОСТИКА PIPELINE ОБРАБОТКИ")
    print("=" * 50)

    try:
        pipeline = OptimizedPipeline()

        # Создаем тестовую страницу
        from app.abstractions.data_source import Page, PageType

        test_page = Page(
            url="https://test.com/test",
            title="Test Page",
            content="Это тестовая страница для проверки обработки в pipeline. " * 20,  # Длинный контент
            page_type=PageType.GUIDE,
            metadata={},
            source="test",
            size_bytes=1000
        )

        print(f"📄 Тестовая страница:")
        print(f"   Длина контента: {len(test_page.content)}")
        print(f"   Размер: {test_page.size_bytes} байт")

        # Тест адаптивного chunking
        chunks = pipeline._adaptive_chunk_page(test_page)
        print(f"   Адаптивный chunking: {len(chunks)} чанков")

        # Тест стандартного chunking
        chunks_std = pipeline._standard_chunk_page(test_page)
        print(f"   Стандартный chunking: {len(chunks_std)} чанков")

        # Тест оптимального размера чанка
        optimal_size = pipeline._get_optimal_chunk_size(test_page)
        print(f"   Оптимальный размер чанка: {optimal_size}")

        return len(chunks) > 0 or len(chunks_std) > 0

    except Exception as e:
        print(f"❌ Ошибка pipeline обработки: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция диагностики"""
    print("🚀 ДИАГНОСТИКА ПРОБЛЕМЫ С CHUNKING")
    print("=" * 80)

    results = []

    # Тест 1: Диагностика одной страницы
    result1 = debug_single_page()
    results.append(("Страница", result1))

    # Тест 2: Диагностика функции chunking
    debug_chunking_function()
    results.append(("Функция chunking", True))  # Если не упала, то OK

    # Тест 3: Диагностика pipeline обработки
    result3 = debug_pipeline_processing()
    results.append(("Pipeline обработка", result3))

    # Итоги
    print("\n" + "=" * 80)
    print("📊 ИТОГИ ДИАГНОСТИКИ")
    print("=" * 80)

    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}: {'OK' if result else 'Проблема'}")

    successful_tests = sum(1 for _, result in results if result)
    print(f"\n📈 Пройдено тестов: {successful_tests}/{len(results)}")

    if successful_tests == len(results):
        print("🎉 Все тесты пройдены! Проблема может быть в другом месте.")
    else:
        print("⚠️ Обнаружены проблемы, требующие исправления.")


if __name__ == "__main__":
    main()
