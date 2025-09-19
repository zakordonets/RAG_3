#!/usr/bin/env python3
"""
Поиск тестовых точек в Qdrant
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from qdrant_client import QdrantClient
from ingestion.chunker import text_hash
import uuid

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def find_test_points():
    """Ищет тестовые точки в Qdrant"""

    logger.info("🔍 Поиск тестовых точек в Qdrant")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    # Тестовые тексты из нашего теста
    test_texts = [
        "Как настроить маршрутизацию в edna Chat Center",
        "API для перенаправления диалогов и сообщений",
        "Документация по настройке кнопок клиента"
    ]

    logger.info(f"📝 Ищем точки для {len(test_texts)} тестовых текстов...")

    try:
        found_points = 0
        for i, text in enumerate(test_texts):
            # Вычисляем ID точки так же, как в индексере
            raw_hash = text_hash(text)
            hex32 = raw_hash.replace("-", "")[:32]
            pid = str(uuid.UUID(hex=hex32))

            logger.info(f"\n📋 Тест {i+1}: '{text}'")
            logger.info(f"  Ожидаемый ID: {pid}")

            # Пытаемся получить точку по ID
            try:
                points = client.retrieve(
                    collection_name=CONFIG.qdrant_collection,
                    ids=[pid],
                    with_payload=True,
                    with_vectors=True
                )

                if points:
                    point = points[0]
                    found_points += 1
                    logger.success(f"  ✅ Точка найдена!")

                    if hasattr(point, 'vector') and point.vector:
                        if isinstance(point.vector, dict):
                            vector_types = list(point.vector.keys())
                            logger.info(f"    Типы векторов: {vector_types}")

                            if 'sparse' in vector_types:
                                sparse_vec = point.vector['sparse']
                                if hasattr(sparse_vec, 'indices') and hasattr(sparse_vec, 'values'):
                                    logger.success(f"    ✅ Sparse вектор: {len(sparse_vec.indices)} индексов, {len(sparse_vec.values)} значений")
                                    logger.info(f"      Индексы: {sparse_vec.indices[:10]}...")
                                    logger.info(f"      Значения: {[f'{v:.3f}' for v in sparse_vec.values[:10]]}...")
                                else:
                                    logger.warning(f"    ⚠️ Неправильный формат sparse вектора: {sparse_vec}")
                            else:
                                logger.warning("    ❌ Sparse вектор отсутствует")

                            if 'dense' in vector_types:
                                dense_vec = point.vector['dense']
                                logger.info(f"    Dense вектор: {len(dense_vec)} элементов")
                        else:
                            logger.info(f"    Вектор: {type(point.vector)}")
                    else:
                        logger.warning("    ⚠️ Вектор не найден")
                else:
                    logger.warning(f"  ❌ Точка не найдена")

            except Exception as e:
                logger.error(f"  ❌ Ошибка при получении точки: {e}")

        logger.info(f"\n📊 Результат: {found_points}/{len(test_texts)} тестовых точек найдено")

        if found_points > 0:
            logger.success("✅ Тестовые точки найдены в индексе!")
            return True
        else:
            logger.error("❌ Тестовые точки не найдены")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка при поиске: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    find_test_points()
