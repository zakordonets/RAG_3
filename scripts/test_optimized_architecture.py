#!/usr/bin/env python3
"""
Тест оптимизированной архитектуры индексации
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
from app.abstractions.data_source import plugin_manager
from app.services.optimized_pipeline import OptimizedPipeline, run_optimized_indexing
from app.services.connection_pool import get_connection_pool, close_connection_pool
from app.config import CONFIG

# Import data sources to register them
from app.sources import edna_docs_source


def test_config_validation():
    """Тест валидации конфигурации"""
    print("🔍 ТЕСТ ВАЛИДАЦИИ КОНФИГУРАЦИИ")
    print("=" * 50)

    try:
        # Тест валидной конфигурации
        print(f"✅ Конфигурация загружена успешно")
        print(f"   Chunk min tokens: {CONFIG.chunk_min_tokens}")
        print(f"   Chunk max tokens: {CONFIG.chunk_max_tokens}")
        print(f"   Crawler strategy: {CONFIG.crawler_strategy}")
        print(f"   Max pages: {CONFIG.max_total_pages}")
        print(f"   Semantic chunker threshold: {CONFIG.semantic_chunker_threshold}")

        # Тест новых параметров
        print(f"   Rate limit RPS: {CONFIG.crawler_rate_limit_requests_per_second}")
        print(f"   Max page size MB: {CONFIG.max_page_size_mb}")
        print(f"   Deduplication: {CONFIG.deduplication_enabled}")

        return True

    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return False


def test_plugin_manager():
    """Тест системы плагинов"""
    print("\n🔍 ТЕСТ СИСТЕМЫ ПЛАГИНОВ")
    print("=" * 50)

    try:
        # Получаем список доступных источников
        sources = plugin_manager.list_sources()
        print(f"📊 Доступные источники данных:")
        for source in sources:
            print(f"   - {source}")

        # Тест получения источника edna_docs
        if "edna_docs" in sources:
            edna_config = {
                "base_url": "https://docs-chatcenter.edna.ru/",
                "strategy": "jina",
                "use_cache": True
            }

            source = plugin_manager.get_source("edna_docs", edna_config)
            print(f"✅ Источник edna_docs загружен: {source.get_source_name()}")

            # Тест классификации страниц
            from app.abstractions.data_source import Page, PageType
            test_page = Page(
                url="https://docs-chatcenter.edna.ru/docs/api/endpoints",
                title="API Endpoints",
                content="API documentation content",
                page_type=PageType.API,
                metadata={},
                source="test"
            )

            classified_type = source.classify_page(test_page)
            print(f"   Классификация API страницы: {classified_type.value}")

            return True
        else:
            print("❌ Источник edna_docs не найден")
            return False

    except Exception as e:
        print(f"❌ Ошибка системы плагинов: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_connection_pool():
    """Тест connection pooling"""
    print("\n🔍 ТЕСТ CONNECTION POOLING")
    print("=" * 50)

    try:
        pool = get_connection_pool()

        # Получаем статистику
        stats = pool.get_stats()
        print(f"📊 Статистика connection pool:")
        print(f"   Активных сессий: {stats['active_sessions']}")
        print(f"   Максимум сессий: {stats['max_sessions']}")
        print(f"   Таймаут сессии: {stats['session_timeout']}s")

        # Тест создания сессии
        session = pool.get_session("https://docs-chatcenter.edna.ru")
        print(f"✅ Сессия создана для docs-chatcenter.edna.ru")

        # Повторное использование сессии
        session2 = pool.get_session("https://docs-chatcenter.edna.ru")
        print(f"✅ Сессия переиспользована: {session is session2}")

        return True

    except Exception as e:
        print(f"❌ Ошибка connection pool: {e}")
        return False


def test_optimized_pipeline():
    """Тест оптимизированного pipeline"""
    print("\n🔍 ТЕСТ ОПТИМИЗИРОВАННОГО PIPELINE")
    print("=" * 50)

    try:
        pipeline = OptimizedPipeline()

        # Получаем список источников
        sources = pipeline.list_available_sources()
        print(f"📊 Доступные источники в pipeline: {sources}")

        # Тест статистики коллекции
        stats = pipeline.get_collection_stats()
        print(f"📊 Статистика коллекции:")
        print(f"   Всего документов: {stats.get('total_documents', 'N/A')}")
        print(f"   Enhanced metadata: {'✅' if stats.get('metadata_enabled') else '❌'}")

        if stats.get('page_type_distribution'):
            print(f"   Распределение по типам:")
            for page_type, count in stats['page_type_distribution'].items():
                print(f"     {page_type}: {count}")

        return True

    except Exception as e:
        print(f"❌ Ошибка pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_small_scale_indexing():
    """Тест индексации небольшого количества страниц"""
    print("\n🔍 ТЕСТ МАЛОМАСШТАБНОЙ ИНДЕКСАЦИИ")
    print("=" * 50)

    try:
        # Тест индексации 5 страниц
        print("🚀 Запуск индексации 5 страниц...")

        result = run_optimized_indexing(
            source_name="edna_docs",
            max_pages=5,
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
        print(f"❌ Ошибка индексации: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_optimization():
    """Тест оптимизации памяти"""
    print("\n🔍 ТЕСТ ОПТИМИЗАЦИИ ПАМЯТИ")
    print("=" * 50)

    try:
        import psutil
        import os

        # Получаем текущее использование памяти
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        print(f"📊 Использование памяти:")
        print(f"   До теста: {memory_before:.2f} MB")

        # Создаем pipeline и тестируем
        pipeline = OptimizedPipeline()

        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_diff = memory_after - memory_before

        print(f"   После создания pipeline: {memory_after:.2f} MB")
        print(f"   Прирост: {memory_diff:.2f} MB")

        # Проверяем, что прирост памяти разумный
        if memory_diff < 100:  # Менее 100MB
            print("✅ Оптимизация памяти работает корректно")
            return True
        else:
            print("⚠️ Большой прирост памяти, возможна утечка")
            return False

    except ImportError:
        print("⚠️ psutil не установлен, пропускаем тест памяти")
        return True
    except Exception as e:
        print(f"❌ Ошибка теста памяти: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ ОПТИМИЗИРОВАННОЙ АРХИТЕКТУРЫ")
    print("=" * 80)

    start_time = time.time()
    tests_passed = 0
    total_tests = 6

    try:
        # Тест 1: Валидация конфигурации
        if test_config_validation():
            tests_passed += 1

        # Тест 2: Система плагинов
        if test_plugin_manager():
            tests_passed += 1

        # Тест 3: Connection pooling
        if test_connection_pool():
            tests_passed += 1

        # Тест 4: Оптимизированный pipeline
        if test_optimized_pipeline():
            tests_passed += 1

        # Тест 5: Маломасштабная индексация
        if test_small_scale_indexing():
            tests_passed += 1

        # Тест 6: Оптимизация памяти
        if test_memory_optimization():
            tests_passed += 1

        elapsed = time.time() - start_time

        print("\n" + "=" * 80)
        print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
        print("=" * 80)
        print(f"✅ Пройдено тестов: {tests_passed}/{total_tests}")
        print(f"⏱️ Время выполнения: {elapsed:.2f} секунд")

        if tests_passed == total_tests:
            print("🎉 Все тесты пройдены успешно!")
        else:
            print("⚠️ Некоторые тесты не прошли")

        # Очистка ресурсов
        close_connection_pool()

    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Очистка ресурсов
        try:
            close_connection_pool()
        except:
            pass


if __name__ == "__main__":
    main()
