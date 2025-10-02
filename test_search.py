#!/usr/bin/env python3
"""
Тестирование поиска в RAG системе
"""
import sys
import os
from loguru import logger

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_encoding():
    """Настраивает правильную кодировку"""
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

def test_search():
    """Тестирует поиск в индексированной коллекции"""
    logger.info("🔍 Тестирование поиска...")

    try:
        from app.services.retrieval import hybrid_search
        from app.services.bge_embeddings import embed_unified

        # Тестовые запросы
        test_queries = [
            "Как настроить агента?",
            "Что такое WebSocket?",
            "Как работает аутентификация?",
            "Настройка производительности",
            "API для интеграции"
        ]

        logger.info(f"📝 Тестируем {len(test_queries)} запросов...")

        for i, query in enumerate(test_queries, 1):
            logger.info(f"\n🔍 Запрос {i}: '{query}'")

            try:
                # Генерируем эмбеддинги для запроса
                logger.info("  📊 Генерируем эмбеддинги...")
                query_embedding = embed_unified(
                    text=query,
                    max_length=512,
                    return_dense=True,
                    return_sparse=True,
                    context="query"
                )

                dense_vec = query_embedding.get('dense_vecs', [[]])[0]
                sparse_vec = query_embedding.get('lexical_weights', [{}])[0]

                logger.info(f"  ✅ Dense вектор: {len(dense_vec)} измерений")
                logger.info(f"  ✅ Sparse вектор: {len(sparse_vec)} токенов")

                # Выполняем поиск
                logger.info("  🔍 Выполняем поиск...")
                results = hybrid_search(
                    query_dense=dense_vec,
                    query_sparse=sparse_vec,
                    k=5
                )

                if results:
                    logger.info(f"  📋 Найдено {len(results)} результатов:")
                    for j, result in enumerate(results, 1):
                        score = result.get('score', 0)
                        payload = result.get('payload', {})
                        url = payload.get('url', 'N/A')
                        title = payload.get('title', 'N/A')
                        text_preview = payload.get('text', '')[:100] + '...' if payload.get('text') else 'N/A'

                        logger.info(f"    {j}. Score: {score:.3f}")
                        logger.info(f"       URL: {url}")
                        logger.info(f"       Title: {title}")
                        logger.info(f"       Text: {text_preview}")
                else:
                    logger.warning(f"  ⚠️  Результаты не найдены для запроса: '{query}'")

            except Exception as e:
                logger.error(f"  ❌ Ошибка при обработке запроса '{query}': {e}")

        logger.success("✅ Тестирование поиска завершено!")

    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации: {e}")
        import traceback
        logger.error(traceback.format_exc())

def test_collection_info():
    """Проверяет информацию о коллекции"""
    logger.info("📊 Проверяем информацию о коллекции...")

    try:
        from app.services.metadata_aware_indexer import MetadataAwareIndexer

        indexer = MetadataAwareIndexer()

        # Получаем информацию о коллекции
        info = indexer.client.get_collection('chatcenter_docs')

        logger.info(f"📈 Статус коллекции: {info.status}")
        logger.info(f"📊 Количество точек: {info.points_count}")
        logger.info(f"🔧 Конфигурация векторов: {info.config}")

    except Exception as e:
        logger.error(f"❌ Ошибка при получении информации о коллекции: {e}")

def main():
    """Основная функция"""
    logger.info("🚀 ТЕСТИРОВАНИЕ ПОИСКА В RAG СИСТЕМЕ")

    # Настраиваем кодировку
    setup_encoding()

    # Проверяем коллекцию
    test_collection_info()

    # Тестируем поиск
    test_search()

if __name__ == "__main__":
    main()
