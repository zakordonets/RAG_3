#!/usr/bin/env python3
"""
Тест всех оптимизаций индексации
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
from app.services.metadata_aware_indexer import MetadataAwareIndexer
from app.models.enhanced_metadata import EnhancedMetadata
from app.services.retrieval import client, COLLECTION

def test_enhanced_metadata():
    """Тест Enhanced Metadata функциональности"""
    print("🔍 ТЕСТ ENHANCED METADATA")
    print("=" * 50)

    # Создаем тестовый текст
    test_text = """
    edna Chat Center поддерживает следующие каналы связи:

    1. Telegram - популярный мессенджер для общения с клиентами
    2. WhatsApp - международный мессенджер с широкой аудиторией
    3. Viber - мессенджер с возможностью звонков
    4. Авито - платформа для объявлений
    5. Веб-виджет - встроенный чат на сайте
    6. Мобильные приложения - iOS и Android приложения

    Для подключения каждого канала требуется настройка в админ-панели.
    """

    # Создаем metadata
    metadata = EnhancedMetadata.from_text_and_metadata(
        text=test_text,
        url="https://docs-chatcenter.edna.ru/docs/start/channels",
        title="Поддерживаемые каналы связи",
        page_type="guide",
        chunk_index=0
    )

    print(f"📊 Результаты анализа:")
    print(f"   Complexity Score: {metadata.complexity_score}")
    print(f"   Semantic Density: {metadata.semantic_density}")
    print(f"   Readability Score: {metadata.readability_score}")
    print(f"   Boost Factor: {metadata.boost_factor}")
    print(f"   Keywords: {metadata.keywords[:5]}")
    print(f"   Entities: {metadata.entities[:5]}")
    print(f"   Semantic Tags: {metadata.semantic_tags}")

    # Тест payload
    payload = metadata.to_search_payload()
    print(f"   Payload keys: {list(payload.keys())}")

    return metadata

def test_metadata_aware_indexer():
    """Тест Metadata-Aware Indexer"""
    print("\n🔍 ТЕСТ METADATA-AWARE INDEXER")
    print("=" * 50)

    indexer = MetadataAwareIndexer()

    # Тест оптимальных размеров батчей
    sparse_batch = indexer.get_optimal_batch_size("sparse")
    dense_batch = indexer.get_optimal_batch_size("dense")
    unified_batch = indexer.get_optimal_batch_size("unified")

    print(f"📊 Оптимальные размеры батчей:")
    print(f"   Sparse: {sparse_batch}")
    print(f"   Dense: {dense_batch}")
    print(f"   Unified: {unified_batch}")

    # Тест стратегий поиска
    test_metadata = EnhancedMetadata(
        url="https://test.com/api",
        page_type="api",
        title="API Documentation",
        complexity_score=0.8,
        semantic_density=0.6
    )

    strategy = indexer.get_search_strategy(test_metadata)
    print(f"   Search Strategy for API docs: {strategy}")

    # Тест оптимизации sparse vectors
    test_lex_weights = {
        "123": 0.8,
        "456": 0.6,
        "789": 0.4,
        "101": 0.2,
        "112": 0.1
    }

    indices, values = indexer.optimize_sparse_conversion(test_lex_weights)
    print(f"   Sparse optimization: {len(indices)} indices, sorted by weight: {values[:3]}")

    return indexer

def test_collection_stats():
    """Тест статистики коллекции"""
    print("\n🔍 ТЕСТ СТАТИСТИКИ КОЛЛЕКЦИИ")
    print("=" * 50)

    indexer = MetadataAwareIndexer()

    try:
        stats = indexer.get_collection_metadata_stats()

        if "error" in stats:
            print(f"❌ Ошибка: {stats['error']}")
            return

        print(f"📊 Статистика коллекции:")
        print(f"   Всего документов: {stats.get('total_documents', 'N/A')}")
        print(f"   Размер выборки: {stats.get('sample_size', 'N/A')}")
        print(f"   Enhanced metadata: {'✅' if stats.get('metadata_enabled') else '❌'}")

        if stats.get('page_type_distribution'):
            print(f"   Распределение по типам:")
            for page_type, count in stats['page_type_distribution'].items():
                print(f"     {page_type}: {count}")

        if stats.get('avg_complexity_score'):
            print(f"   Средняя сложность: {stats['avg_complexity_score']:.3f}")
            print(f"   Средняя плотность: {stats['avg_semantic_density']:.3f}")
            print(f"   Средний boost: {stats['avg_boost_factor']:.3f}")

    except Exception as e:
        print(f"❌ Ошибка при получении статистики: {e}")

def test_optimized_search():
    """Тест оптимизированного поиска"""
    print("\n🔍 ТЕСТ ОПТИМИЗИРОВАННОГО ПОИСКА")
    print("=" * 50)

    # Тест поиска с metadata filtering
    indexer = MetadataAwareIndexer()

    # Создаем тестовые векторы (заглушки)
    test_dense_vector = [0.1] * 1024
    test_sparse_vector = {
        "indices": [1, 2, 3, 4, 5],
        "values": [0.8, 0.6, 0.4, 0.2, 0.1]
    }

    # Тест поиска с фильтрами
    filters = {
        "page_type": "guide"
    }

    try:
        results = indexer.search_with_metadata_filtering(
            query="каналы связи",
            dense_vector=test_dense_vector,
            sparse_vector=test_sparse_vector,
            filters=filters,
            limit=5
        )

        print(f"📊 Результаты поиска с фильтрами:")
        print(f"   Найдено документов: {len(results)}")

        for i, result in enumerate(results[:3], 1):
            payload = result.get('payload', {})
            print(f"   {i}. {payload.get('title', 'N/A')}")
            print(f"      URL: {payload.get('url', 'N/A')}")
            print(f"      Boost: {payload.get('boost_factor', 'N/A')}")
            print(f"      Complexity: {payload.get('complexity_score', 'N/A')}")

    except Exception as e:
        print(f"❌ Ошибка при тестировании поиска: {e}")

def test_chunk_size_optimization():
    """Тест оптимизации размеров чанков"""
    print("\n🔍 ТЕСТ ОПТИМИЗАЦИИ РАЗМЕРОВ ЧАНКОВ")
    print("=" * 50)

    indexer = MetadataAwareIndexer()

    # Тест для разных типов контента
    test_cases = [
        ("api", "API Documentation", 0.8),
        ("guide", "User Guide", 0.4),
        ("faq", "FAQ", 0.2),
        ("release_notes", "Release Notes", 0.6)
    ]

    print("📊 Оптимальные размеры чанков по типам:")
    for page_type, title, complexity in test_cases:
        metadata = EnhancedMetadata(
            url=f"https://test.com/{page_type}",
            page_type=page_type,
            title=title,
            complexity_score=complexity
        )

        optimal_size = indexer.get_optimal_chunk_size(metadata)
        print(f"   {page_type}: {optimal_size} токенов")

def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ ОПТИМИЗАЦИЙ ИНДЕКСАЦИИ")
    print("=" * 80)

    start_time = time.time()

    try:
        # Тест 1: Enhanced Metadata
        test_enhanced_metadata()

        # Тест 2: Metadata-Aware Indexer
        test_metadata_aware_indexer()

        # Тест 3: Статистика коллекции
        test_collection_stats()

        # Тест 4: Оптимизированный поиск
        test_optimized_search()

        # Тест 5: Оптимизация размеров чанков
        test_chunk_size_optimization()

        elapsed = time.time() - start_time
        print(f"\n✅ Все тесты завершены за {elapsed:.2f} секунд")

    except Exception as e:
        print(f"\n❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
