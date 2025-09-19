#!/usr/bin/env python3
"""
Скрипт для отладки sparse векторов
"""
import os
import sys
import numpy as np
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from app.services.bge_embeddings import embed_unified

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def debug_sparse_vectors():
    """Отлаживает генерацию sparse векторов"""

    logger.info("🔍 Отладка sparse векторов")
    logger.info("=" * 50)

    # Тестовые запросы
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
                dense_vecs = result.get("dense", [])
                sparse_vecs = result.get("sparse", [])
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
                        weights_sample = lexical_weights[0][:10]  # Первые 10 значений
                        logger.info(f"📋 Lexical weights sample: {weights_sample}")
                else:
                    logger.warning("⚠️ Lexical weights пусты!")

            else:
                logger.error(f"❌ Неожиданный формат результата: {type(result)}")

        except Exception as e:
            logger.error(f"❌ Ошибка при генерации embeddings: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())

def check_bge_configuration():
    """Проверяет конфигурацию BGE-M3"""

    logger.info("\n🔧 Проверка конфигурации BGE-M3")
    logger.info("=" * 50)

    logger.info(f"📋 Embeddings backend: {CONFIG.embeddings_backend}")
    logger.info(f"📋 Embedding device: {CONFIG.embedding_device}")
    logger.info(f"📋 Use sparse: {CONFIG.use_sparse}")
    logger.info(f"📋 Embedding normalize: {CONFIG.embedding_normalize}")
    logger.info(f"📋 Embedding use fp16: {CONFIG.embedding_use_fp16}")

    # Проверяем, какой backend используется
    from app.services.bge_embeddings import _get_optimal_backend_strategy
    strategy = _get_optimal_backend_strategy()
    logger.info(f"📋 Оптимальная стратегия: {strategy}")

def test_direct_bge_model():
    """Тестирует BGE-M3 модель напрямую"""

    logger.info("\n🧪 Прямое тестирование BGE-M3")
    logger.info("=" * 50)

    try:
        from app.services.bge_embeddings import _get_bge_model

        # Загружаем BGE модель
        model = _get_bge_model()
        logger.info("✅ BGE-M3 модель загружена")

        # Тестируем генерацию sparse векторов
        test_text = "Как мне настроить маршрутизацию?"

        logger.info(f"📝 Тестируем текст: '{test_text}'")

        # Генерируем embeddings с sparse=True
        result = model.encode(
            [test_text],
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            normalize_embeddings=CONFIG.embedding_normalize
        )

        logger.info(f"📊 Результат BGE-M3:")
        logger.info(f"  - Dense: {len(result['dense_vecs'])} векторов")
        logger.info(f"  - Sparse: {len(result['lexical_weights'])} векторов")

        if result['lexical_weights']:
            sparse_vec = result['lexical_weights'][0]
            logger.info(f"  - Sparse размер: {len(sparse_vec)}")
            logger.info(f"  - Sparse ненулевые элементы: {np.count_nonzero(sparse_vec)}")

            # Показываем топ-10 sparse значений
            if len(sparse_vec) > 0:
                # Сортируем по убыванию и берем топ-10
                top_indices = np.argsort(sparse_vec)[-10:][::-1]
                top_values = sparse_vec[top_indices]
                logger.info(f"  - Топ-10 sparse значений: {list(zip(top_indices, top_values))}")
        else:
            logger.warning("⚠️ BGE-M3 не вернул sparse векторы!")

    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании BGE-M3: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    """Главная функция отладки"""

    logger.info("🚀 Отладка sparse векторов")
    logger.info("=" * 60)

    # Проверяем конфигурацию
    check_bge_configuration()

    # Тестируем BGE-M3 напрямую
    test_direct_bge_model()

    # Тестируем через embed_unified
    debug_sparse_vectors()

    logger.info("\n" + "=" * 60)
    logger.info("✅ Отладка завершена")

if __name__ == "__main__":
    main()
