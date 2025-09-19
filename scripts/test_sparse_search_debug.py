#!/usr/bin/env python3
"""
Отладка sparse поиска
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from app.services.bge_embeddings import embed_unified
from app.services.retrieval import hybrid_search

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_sparse_search_debug():
    """Отлаживает sparse поиск"""

    logger.info("🔍 Отладка sparse поиска")
    logger.info("=" * 50)

    query = "Как мне настроить маршрутизацию?"

    # Генерируем embeddings
    logger.info(f"📝 Запрос: '{query}'")

    embedding_result = embed_unified(
        query,
        max_length=CONFIG.embedding_max_length_query,
        return_dense=True,
        return_sparse=CONFIG.use_sparse,
        return_colbert=False,
        context="query"
    )

    logger.info(f"📊 Результат embed_unified:")
    logger.info(f"  - dense_vecs: {len(embedding_result.get('dense_vecs', []))}")
    logger.info(f"  - sparse_vecs: {len(embedding_result.get('sparse_vecs', []))}")
    logger.info(f"  - lexical_weights: {len(embedding_result.get('lexical_weights', []))}")

    # Извлекаем dense вектор
    q_dense = embedding_result['dense_vecs'][0] if embedding_result.get('dense_vecs') else []
    logger.info(f"📏 Dense размер: {len(q_dense)}")

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
            logger.info(f"📏 Sparse размер: {len(indices)} индексов, {len(values)} значений")
            logger.info(f"📋 Sparse индексы: {indices}")
            logger.info(f"📋 Sparse значения: {values}")
        else:
            logger.warning("⚠️ lexical_weights пусты или не словарь")
    else:
        logger.warning("⚠️ use_sparse=False или lexical_weights отсутствуют")

    # Тестируем поиск
    logger.info(f"\n🔍 Тестируем hybrid_search...")
    try:
        results = hybrid_search(q_dense, q_sparse, k=10)
        logger.info(f"📊 Результаты поиска: {len(results)}")

        if results:
            logger.info("📋 Первые 3 результата:")
            for i, result in enumerate(results[:3]):
                logger.info(f"  {i+1}. ID: {result.get('id', 'N/A')}, Score: {result.get('score', 'N/A')}")
                if 'payload' in result and 'text' in result['payload']:
                    text_preview = result['payload']['text'][:100] + "..." if len(result['payload']['text']) > 100 else result['payload']['text']
                    logger.info(f"     Text: {text_preview}")
        else:
            logger.warning("⚠️ Поиск не вернул результатов")

    except Exception as e:
        logger.error(f"❌ Ошибка при поиске: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_sparse_search_debug()
