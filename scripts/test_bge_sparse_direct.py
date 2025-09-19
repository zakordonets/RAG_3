#!/usr/bin/env python3
"""
Прямое тестирование BGE-M3 sparse векторов
"""
import os
import sys
import numpy as np
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from app.services.bge_embeddings import _get_bge_model

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_bge_sparse_direct():
    """Прямое тестирование BGE-M3 sparse векторов"""

    logger.info("🧪 Прямое тестирование BGE-M3 sparse векторов")
    logger.info("=" * 60)

    try:
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
            return_colbert_vecs=False
        )

        logger.info(f"📊 Результат BGE-M3:")
        logger.info(f"  - Тип результата: {type(result)}")
        logger.info(f"  - Ключи: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")

        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, list):
                    logger.info(f"  - {key}: {len(value)} элементов")
                    if len(value) > 0:
                        logger.info(f"    - Размер первого элемента: {len(value[0]) if hasattr(value[0], '__len__') else 'N/A'}")
                        if key == 'lexical_weights' and len(value[0]) > 0:
                            # Показываем первые несколько значений
                            sample = value[0][:10] if hasattr(value[0], '__getitem__') else value[0]
                            logger.info(f"    - Sample: {sample}")
                else:
                    logger.info(f"  - {key}: {type(value)} = {value}")

        # Проверяем, есть ли sparse векторы
        if 'lexical_weights' in result and result['lexical_weights']:
            lexical_weights = result['lexical_weights'][0]
            logger.info(f"📊 Lexical weights:")
            logger.info(f"  - Размер: {len(lexical_weights)}")
            logger.info(f"  - Тип: {type(lexical_weights)}")

            if hasattr(lexical_weights, '__len__') and len(lexical_weights) > 0:
                # Проверяем, есть ли ненулевые значения
                if hasattr(lexical_weights, '__iter__'):
                    non_zero_count = sum(1 for x in lexical_weights if x != 0)
                    logger.info(f"  - Ненулевые элементы: {non_zero_count}")

                    if non_zero_count > 0:
                        # Показываем топ-10 значений
                        if hasattr(lexical_weights, 'argsort'):
                            # NumPy array
                            top_indices = np.argsort(lexical_weights)[-10:][::-1]
                            top_values = lexical_weights[top_indices]
                            logger.info(f"  - Топ-10 значений: {list(zip(top_indices, top_values))}")
                        else:
                            # Обычный список
                            sorted_items = sorted(enumerate(lexical_weights), key=lambda x: x[1], reverse=True)
                            logger.info(f"  - Топ-10 значений: {sorted_items[:10]}")
                    else:
                        logger.warning("⚠️ Все lexical weights равны нулю!")
                else:
                    logger.info(f"  - Значение: {lexical_weights}")
            else:
                logger.warning("⚠️ Lexical weights пусты!")
        else:
            logger.warning("⚠️ Lexical weights не найдены в результате!")

    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании BGE-M3: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_bge_sparse_direct()
