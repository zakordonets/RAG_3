#!/usr/bin/env python3
"""
Проверка sparse векторов в Qdrant
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

def check_qdrant_sparse():
    """Проверяет sparse векторы в Qdrant"""

    logger.info("🔍 Проверка sparse векторов в Qdrant")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        # Получаем информацию о коллекции
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        logger.info(f"📊 Коллекция: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Количество точек: {collection_info.points_count}")

        # Проверяем конфигурацию векторов
        if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
            params = collection_info.config.params
            logger.info(f"📊 Параметры коллекции: {params}")

            if hasattr(params, 'vectors'):
                vectors_config = params.vectors
                logger.info(f"📊 Конфигурация векторов: {vectors_config}")

                if hasattr(vectors_config, 'sparse_vectors'):
                    sparse_config = vectors_config.sparse_vectors
                    logger.info(f"📊 Sparse векторы настроены: {sparse_config}")
                else:
                    logger.warning("⚠️ Sparse векторы не настроены в коллекции!")
                    return
            else:
                logger.warning("⚠️ Конфигурация векторов не найдена!")
                return

        # Получаем несколько точек для проверки
        logger.info(f"\n🔍 Получаем точки из коллекции...")
        points = client.scroll(
            collection_name=CONFIG.qdrant_collection,
            limit=5,
            with_payload=True,
            with_vectors=True
        )[0]

        logger.info(f"📊 Получено {len(points)} точек для проверки")

        sparse_found = 0
        for i, point in enumerate(points):
            logger.info(f"\n📋 Точка {i+1}:")
            logger.info(f"  ID: {point.id}")

            if hasattr(point, 'vector') and point.vector:
                if isinstance(point.vector, dict):
                    vector_types = list(point.vector.keys())
                    logger.info(f"  Типы векторов: {vector_types}")

                    if 'sparse' in point.vector:
                        sparse_vec = point.vector['sparse']
                        logger.info(f"  ✅ Sparse вектор найден!")
                        sparse_found += 1

                        if hasattr(sparse_vec, 'indices') and hasattr(sparse_vec, 'values'):
                            logger.info(f"    Размер: {len(sparse_vec.indices)} индексов, {len(sparse_vec.values)} значений")
                            if sparse_vec.indices:
                                logger.info(f"    Индексы: {sparse_vec.indices[:10]}...")
                                logger.info(f"    Значения: {[f'{v:.3f}' for v in sparse_vec.values[:10]]}...")
                        else:
                            logger.info(f"    Формат: {type(sparse_vec)} = {sparse_vec}")
                    else:
                        logger.warning("  ⚠️ Sparse вектор не найден")
                        logger.info(f"    Доступные векторы: {vector_types}")
                else:
                    logger.info(f"  Вектор: {type(point.vector)}")
            else:
                logger.warning("  ⚠️ Вектор не найден")

        logger.info(f"\n📊 Итого: {sparse_found}/{len(points)} точек содержат sparse векторы")

        if sparse_found == 0:
            logger.error("❌ Sparse векторы не найдены в индексе!")
            logger.info("💡 Возможные причины:")
            logger.info("  1. Sparse векторы не индексируются при добавлении документов")
            logger.info("  2. Коллекция была создана без поддержки sparse векторов")
            logger.info("  3. Нужно переиндексировать документы с sparse векторами")
        else:
            logger.success(f"✅ Sparse векторы найдены в {sparse_found} точках")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке Qdrant: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    check_qdrant_sparse()
