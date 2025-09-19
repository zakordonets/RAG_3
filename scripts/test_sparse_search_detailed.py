#!/usr/bin/env python3
"""
Детальное тестирование sparse поиска
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from app.services.bge_embeddings import embed_unified
from qdrant_client import QdrantClient
from qdrant_client.models import NamedSparseVector, SparseVector

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_sparse_search_detailed():
    """Детальное тестирование sparse поиска"""

    logger.info("🔍 Детальное тестирование sparse поиска")
    logger.info("=" * 60)

    # Подключаемся к Qdrant
    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    # Тестируем разные запросы
    test_queries = [
        "Как мне настроить маршрутизацию?",
        "настройка маршрутизации",
        "маршрутизация",
        "routing configuration",
        "transfer thread",
        "API",
        "документация"
    ]

    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n📝 Тест {i}: '{query}'")
        logger.info("-" * 50)

        # Генерируем embeddings
        embedding_result = embed_unified(
            query,
            max_length=CONFIG.embedding_max_length_query,
            return_dense=True,
            return_sparse=CONFIG.use_sparse,
            return_colbert=False,
            context="query"
        )

        # Извлекаем sparse вектор
        q_sparse = {"indices": [], "values": []}
        if CONFIG.use_sparse and embedding_result.get('lexical_weights'):
            lex_weights = embedding_result['lexical_weights'][0]
            if lex_weights and isinstance(lex_weights, dict):
                indices = [int(k) for k in lex_weights.keys()]
                values = [float(lex_weights[k]) for k in lex_weights.keys()]
                q_sparse = {
                    "indices": indices,
                    "values": values
                }

        logger.info(f"📊 Sparse вектор: {len(q_sparse['indices'])} индексов")
        if q_sparse['indices']:
            logger.info(f"📋 Индексы: {q_sparse['indices']}")
            logger.info(f"📋 Значения: {[f'{v:.3f}' for v in q_sparse['values']]}")

        # Тестируем только sparse поиск
        if q_sparse['indices'] and q_sparse['values']:
            try:
                sparse_vector = NamedSparseVector(
                    name="sparse",
                    vector=SparseVector(indices=q_sparse['indices'], values=q_sparse['values'])
                )

                sparse_res = client.search(
                    collection_name=CONFIG.qdrant_collection,
                    query_vector=sparse_vector,
                    with_payload=True,
                    limit=5,
                )

                logger.info(f"📊 Sparse поиск: {len(sparse_res)} результатов")

                if sparse_res:
                    logger.info("📋 Результаты sparse поиска:")
                    for j, result in enumerate(sparse_res[:3], 1):
                        score = result.score if hasattr(result, 'score') else 'N/A'
                        doc_id = result.id if hasattr(result, 'id') else 'N/A'
                        logger.info(f"  {j}. ID: {doc_id}, Score: {score}")

                        if hasattr(result, 'payload') and result.payload and 'text' in result.payload:
                            text_preview = result.payload['text'][:100] + "..." if len(result.payload['text']) > 100 else result.payload['text']
                            logger.info(f"     Text: {text_preview}")
                else:
                    logger.warning("⚠️ Sparse поиск не нашел результатов")

            except Exception as e:
                logger.error(f"❌ Ошибка sparse поиска: {type(e).__name__}: {e}")
        else:
            logger.warning("⚠️ Sparse вектор пуст")

def test_sparse_indexing():
    """Проверяем, есть ли sparse векторы в индексе"""

    logger.info("\n🔍 Проверка sparse векторов в индексе")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        # Получаем информацию о коллекции
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        logger.info(f"📊 Коллекция: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Количество точек: {collection_info.points_count}")

        # Проверяем схему векторов
        if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
            params = collection_info.config.params
            if hasattr(params, 'vectors') and hasattr(params.vectors, 'sparse_vectors'):
                sparse_config = params.vectors.sparse_vectors
                logger.info(f"📊 Sparse векторы настроены: {sparse_config}")
            else:
                logger.warning("⚠️ Sparse векторы не настроены в коллекции")

        # Получаем несколько точек для проверки
        points = client.scroll(
            collection_name=CONFIG.qdrant_collection,
            limit=3,
            with_payload=True,
            with_vectors=True
        )[0]

        logger.info(f"📊 Получено {len(points)} точек для проверки")

        for i, point in enumerate(points):
            logger.info(f"\n📋 Точка {i+1}:")
            logger.info(f"  ID: {point.id}")

            if hasattr(point, 'vector') and point.vector:
                if isinstance(point.vector, dict):
                    logger.info(f"  Векторы: {list(point.vector.keys())}")
                    if 'sparse' in point.vector:
                        sparse_vec = point.vector['sparse']
                        if hasattr(sparse_vec, 'indices') and hasattr(sparse_vec, 'values'):
                            logger.info(f"  Sparse: {len(sparse_vec.indices)} индексов, {len(sparse_vec.values)} значений")
                            if sparse_vec.indices:
                                logger.info(f"    Индексы: {sparse_vec.indices[:10]}...")
                                logger.info(f"    Значения: {[f'{v:.3f}' for v in sparse_vec.values[:10]]}...")
                        else:
                            logger.info(f"  Sparse: {sparse_vec}")
                    else:
                        logger.warning("  ⚠️ Sparse вектор не найден")
                else:
                    logger.info(f"  Вектор: {type(point.vector)}")
            else:
                logger.warning("  ⚠️ Вектор не найден")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке индекса: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_sparse_search_detailed()
    test_sparse_indexing()
