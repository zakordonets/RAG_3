#!/usr/bin/env python3
"""
Тестирование исправленных sparse векторов
"""
import os
import sys
import numpy as np
from collections import defaultdict
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from app.services.bge_embeddings import embed_unified

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_sparse_fixed():
    """Тестирует исправленные sparse векторы"""

    logger.info("🧪 Тестирование исправленных sparse векторов")
    logger.info("=" * 60)

    test_queries = [
        "Как мне настроить маршрутизацию?",
        "настройка маршрутизации",
        "маршрутизация",
        "routing configuration",
        "transfer thread"
    ]

    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n📝 Тест {i}: '{query}'")
        logger.info("-" * 40)

        try:
            # Генерируем embeddings
            result = embed_unified(query)

            if isinstance(result, dict):
                dense_vecs = result.get("dense_vecs", [])
                sparse_vecs = result.get("sparse_vecs", [])
                lexical_weights = result.get("lexical_weights", [])

                logger.info(f"📊 Dense векторы: {len(dense_vecs)}")
                logger.info(f"📊 Sparse векторы: {len(sparse_vecs)}")
                logger.info(f"📊 Lexical weights: {len(lexical_weights)}")

                if dense_vecs:
                    logger.info(f"📏 Dense размер: {len(dense_vecs[0]) if dense_vecs else 'N/A'}")

                if sparse_vecs:
                    logger.info(f"📏 Sparse размер: {len(sparse_vecs[0]) if sparse_vecs else 'N/A'}")
                    # Показываем первые несколько sparse значений
                    if len(sparse_vecs[0]) > 0:
                        sparse_sample = sparse_vecs[0][:10]  # Первые 10 значений
                        logger.info(f"📋 Sparse sample: {sparse_sample}")
                else:
                    logger.warning("⚠️ Sparse векторы пусты!")

                if lexical_weights:
                    logger.info(f"📏 Lexical weights размер: {len(lexical_weights[0]) if lexical_weights else 'N/A'}")
                    if len(lexical_weights[0]) > 0:
                        weights = lexical_weights[0]
                        logger.info(f"📋 Lexical weights тип: {type(weights)}")

                        if isinstance(weights, defaultdict):
                            # Показываем содержимое defaultdict
                            logger.info(f"📋 Lexical weights содержимое: {dict(weights)}")

                            # Считаем ненулевые элементы
                            non_zero_count = len([v for v in weights.values() if v != 0])
                            logger.info(f"📋 Ненулевые элементы: {non_zero_count}")

                            if non_zero_count > 0:
                                # Показываем топ-10 значений
                                sorted_items = sorted(weights.items(), key=lambda x: x[1], reverse=True)
                                logger.info(f"📋 Топ-10 значений: {sorted_items[:10]}")
                        else:
                            logger.info(f"📋 Lexical weights sample: {weights[:10] if hasattr(weights, '__getitem__') else weights}")
                else:
                    logger.warning("⚠️ Lexical weights пусты!")

            else:
                logger.error(f"❌ Неожиданный формат результата: {type(result)}")

        except Exception as e:
            logger.error(f"❌ Ошибка при генерации embeddings: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_sparse_fixed()
