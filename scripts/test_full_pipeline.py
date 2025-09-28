#!/usr/bin/env python3
"""
Полный end-to-end тест: от извлечения документа до записи в Qdrant
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
from app.abstractions.data_source import plugin_manager
from app.services.optimized_pipeline import OptimizedPipeline
from app.services.metadata_aware_indexer import MetadataAwareIndexer
from ingestion.chunker import chunk_text
from app.config import CONFIG

# Import data sources
from app.sources import edna_docs_source


def test_full_pipeline_single_document():
    """Полный тест pipeline для одного документа"""
    print("🔍 ПОЛНЫЙ ТЕСТ PIPELINE - ОДИН ДОКУМЕНТ")
    print("=" * 60)

    try:
        # Шаг 1: Извлечение документа
        print("📄 Шаг 1: Извлечение документа")
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": False,  # Без кеша для свежих данных
            "max_pages": 1
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        crawl_result = source.fetch_pages(max_pages=1)

        if not crawl_result.pages:
            print("❌ Не удалось извлечь документы")
            return False

        page = crawl_result.pages[0]
        print(f"   ✅ Документ извлечен:")
        print(f"      URL: {page.url}")
        print(f"      Заголовок: {page.title}")
        print(f"      Тип: {page.page_type.value}")
        print(f"      Длина контента: {len(page.content)} символов")

        if len(page.content) == 0:
            print("   ❌ Контент пустой!")
            return False

        print(f"      Первые 200 символов: {page.content[:200]}...")

        # Шаг 2: Chunking
        print(f"\n🔧 Шаг 2: Chunking")
        chunks = chunk_text(page.content)
        print(f"   ✅ Сгенерировано чанков: {len(chunks)}")

        if len(chunks) == 0:
            print("   ❌ Чанки не сгенерированы!")
            return False

        for i, chunk in enumerate(chunks[:3]):
            print(f"      Чанк {i+1}: {len(chunk)} символов")
            print(f"         Начало: {chunk[:100]}...")

        # Шаг 3: Подготовка для индексации
        print(f"\n📝 Шаг 3: Подготовка для индексации")
        chunks_for_indexing = []
        for i, chunk_text_content in enumerate(chunks):
            chunk = {
                "text": chunk_text_content,
                "payload": {
                    "url": page.url,
                    "title": page.title,
                    "page_type": page.page_type.value,
                    "source": page.source,
                    "language": page.language,
                    "chunk_index": i,
                    "content_length": len(chunk_text_content),
                    "test_run": True,  # Маркер тестового запуска
                    **page.metadata
                }
            }
            chunks_for_indexing.append(chunk)

        print(f"   ✅ Подготовлено {len(chunks_for_indexing)} чанков для индексации")

        # Шаг 4: Индексация в Qdrant
        print(f"\n🗄️ Шаг 4: Индексация в Qdrant")
        indexer = MetadataAwareIndexer()

        start_time = time.time()
        indexed_count = indexer.index_chunks_with_metadata(chunks_for_indexing)
        indexing_time = time.time() - start_time

        print(f"   ✅ Индексация завершена:")
        print(f"      Записано чанков: {indexed_count}")
        print(f"      Время индексации: {indexing_time:.2f}s")

        if indexed_count == 0:
            print("   ❌ Чанки не записаны в Qdrant!")
            return False

        # Шаг 5: Проверка записи в Qdrant
        print(f"\n🔍 Шаг 5: Проверка записи в Qdrant")
        from app.services.retrieval import client, COLLECTION

        # Ищем наши тестовые документы
        search_result = client.scroll(
            collection_name=COLLECTION,
            scroll_filter={"must": [{"key": "test_run", "match": {"value": True}}]},
            limit=10,
            with_payload=True,
            with_vectors=False
        )

        found_chunks = search_result[0]
        print(f"   ✅ Найдено тестовых чанков в Qdrant: {len(found_chunks)}")

        if found_chunks:
            test_chunk = found_chunks[0]
            payload = test_chunk.payload
            print(f"      URL: {payload.get('url')}")
            print(f"      Заголовок: {payload.get('title')}")
            print(f"      Chunk index: {payload.get('chunk_index')}")
            print(f"      Content length: {payload.get('content_length')}")

            # Проверяем enhanced metadata
            if 'complexity_score' in payload:
                print(f"      Enhanced metadata: ✅")
                print(f"         Complexity: {payload.get('complexity_score')}")
                print(f"         Semantic density: {payload.get('semantic_density')}")
                print(f"         Boost factor: {payload.get('boost_factor')}")
            else:
                print(f"      Enhanced metadata: ❌")

        # Шаг 6: Очистка тестовых данных
        print(f"\n🧹 Шаг 6: Очистка тестовых данных")
        if found_chunks:
            test_ids = [str(chunk.id) for chunk in found_chunks]
            client.delete(
                collection_name=COLLECTION,
                points_selector=test_ids
            )
            print(f"   ✅ Удалено {len(test_ids)} тестовых чанков")

        return True

    except Exception as e:
        print(f"❌ Ошибка в pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_optimized_pipeline_end_to_end():
    """Тест оптимизированного pipeline end-to-end"""
    print("\n🔍 ТЕСТ ОПТИМИЗИРОВАННОГО PIPELINE END-TO-END")
    print("=" * 60)

    try:
        # Запускаем полный pipeline
        from app.services.optimized_pipeline import run_optimized_indexing
        result = run_optimized_indexing(
            source_name="edna_docs",
            max_pages=3,  # Небольшое количество для теста
            chunk_strategy="adaptive"
        )

        print(f"📊 Результаты полного pipeline:")
        print(f"   Успех: {'✅' if result['success'] else '❌'}")
        print(f"   Страниц обработано: {result.get('pages', 0)}")
        print(f"   Чанков проиндексировано: {result.get('chunks', 0)}")
        print(f"   Время выполнения: {result.get('duration', 0):.2f}s")
        print(f"   Ошибки: {result.get('errors', 0)}")

        if result['success'] and result.get('chunks', 0) > 0:
            print(f"   ✅ Pipeline работает корректно!")

            # Дополнительная проверка коллекции
            indexer = MetadataAwareIndexer()
            stats = indexer.get_collection_metadata_stats()

            print(f"\n📈 Статистика коллекции:")
            print(f"   Всего документов: {stats.get('total_documents', 'N/A')}")
            print(f"   Enhanced metadata: {'✅' if stats.get('metadata_enabled') else '❌'}")

            return True
        else:
            print(f"   ❌ Pipeline не работает корректно!")
            return False

    except Exception as e:
        print(f"❌ Ошибка оптимизированного pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chunking_quality():
    """Тест качества chunking"""
    print("\n🔍 ТЕСТ КАЧЕСТВА CHUNKING")
    print("=" * 60)

    try:
        # Получаем документ с хорошим контентом
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": False,
            "max_pages": 1
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        crawl_result = source.fetch_pages(max_pages=1)

        if not crawl_result.pages or len(crawl_result.pages[0].content) == 0:
            print("❌ Не удалось получить документ с контентом")
            return False

        page = crawl_result.pages[0]
        print(f"📄 Тестируем chunking для: {page.title}")
        print(f"   Длина контента: {len(page.content)} символов")

        # Тестируем разные стратегии chunking
        strategies = ["adaptive", "standard"]

        for strategy in strategies:
            print(f"\n🔧 Стратегия: {strategy}")

            pipeline = OptimizedPipeline()

            if strategy == "adaptive":
                chunks = pipeline._adaptive_chunk_page(page)
            else:
                chunks = pipeline._standard_chunk_page(page)

            print(f"   Чанков: {len(chunks)}")

            if chunks:
                total_chars = sum(len(chunk['text']) for chunk in chunks)
                avg_chars = total_chars / len(chunks)

                print(f"   Общая длина: {total_chars} символов")
                print(f"   Средняя длина чанка: {avg_chars:.0f} символов")

                # Проверяем качество chunking
                if avg_chars < 100:
                    print(f"   ⚠️ Чанки слишком короткие")
                elif avg_chars > 2000:
                    print(f"   ⚠️ Чанки слишком длинные")
                else:
                    print(f"   ✅ Размер чанков оптимальный")

                # Показываем первые несколько чанков
                for i, chunk in enumerate(chunks[:2]):
                    print(f"      Чанк {i+1}: {len(chunk['text'])} символов")
                    print(f"         Начало: {chunk['text'][:100]}...")
            else:
                print(f"   ❌ Чанки не сгенерированы")
                return False

        return True

    except Exception as e:
        print(f"❌ Ошибка тестирования chunking: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 ПОЛНОЕ ТЕСТИРОВАНИЕ PIPELINE")
    print("=" * 80)

    results = []

    # Тест 1: Полный pipeline одного документа
    result1 = test_full_pipeline_single_document()
    results.append(("Полный pipeline", result1))

    # Тест 2: Оптимизированный pipeline
    result2 = test_optimized_pipeline_end_to_end()
    results.append(("Оптимизированный pipeline", result2))

    # Тест 3: Качество chunking
    result3 = test_chunking_quality()
    results.append(("Качество chunking", result3))

    # Итоги
    print("\n" + "=" * 80)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 80)

    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}: {'OK' if result else 'Проблема'}")

    successful_tests = sum(1 for _, result in results if result)
    print(f"\n📈 Пройдено тестов: {successful_tests}/{len(results)}")

    if successful_tests == len(results):
        print("🎉 Все тесты пройдены! Pipeline работает корректно от начала до конца.")
    else:
        print("⚠️ Обнаружены проблемы в pipeline, требующие исправления.")


if __name__ == "__main__":
    main()
