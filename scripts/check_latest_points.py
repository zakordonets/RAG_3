#!/usr/bin/env python3
"""
Проверка последних точек в Qdrant
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from qdrant_client import QdrantClient

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def check_latest_points():
    """Проверяет последние точки в Qdrant"""

    logger.info("🔍 Проверка последних точек в Qdrant")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        # Получаем информацию о коллекции
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        logger.info(f"📊 Коллекция: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Количество точек: {collection_info.points_count}")

        # Получаем последние точки (с offset)
        logger.info(f"\n🔍 Получаем последние 10 точек...")
        points = client.scroll(
            collection_name=CONFIG.qdrant_collection,
            limit=10,
            offset=collection_info.points_count - 10,  # Получаем последние 10 точек
            with_payload=True,
            with_vectors=True
        )[0]

        logger.info(f"📊 Получено {len(points)} точек")

        sparse_found = 0
        for i, point in enumerate(points):
            logger.info(f"\n📋 Точка {i+1}:")
            logger.info(f"  ID: {point.id}")

            if hasattr(point, 'vector') and point.vector:
                if isinstance(point.vector, dict):
                    vector_types = list(point.vector.keys())
                    logger.info(f"  Типы векторов: {vector_types}")

                    for vector_name, vector_data in point.vector.items():
                        logger.info(f"  - {vector_name}: {type(vector_data)}")

                        # Для sparse векторов
                        if vector_name == 'sparse':
                            sparse_found += 1
                            if hasattr(vector_data, 'indices') and hasattr(vector_data, 'values'):
                                logger.info(f"    ✅ Sparse вектор: {len(vector_data.indices)} индексов, {len(vector_data.values)} значений")
                                if vector_data.indices:
                                    logger.info(f"      Индексы: {vector_data.indices[:10]}...")
                                    logger.info(f"      Значения: {[f'{v:.3f}' for v in vector_data.values[:10]]}...")
                            else:
                                logger.info(f"    ❌ Неправильный формат sparse вектора: {vector_data}")
                        elif vector_name == 'dense':
                            logger.info(f"    Dense вектор: {len(vector_data)} элементов")
                else:
                    logger.info(f"  Вектор: {type(point.vector)}")
            else:
                logger.warning("  ⚠️ Вектор не найден")

        logger.info(f"\n📊 Результат: {sparse_found}/{len(points)} точек содержат sparse векторы")

        if sparse_found > 0:
            logger.success("✅ Sparse векторы найдены в последних точках!")
        else:
            logger.error("❌ Sparse векторы не найдены в последних точках")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    check_latest_points()
