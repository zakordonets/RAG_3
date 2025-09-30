#!/usr/bin/env python3
"""
Детальная проверка Qdrant коллекции
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

def check_qdrant_detailed():
    """Детальная проверка Qdrant коллекции"""

    logger.info("🔍 Детальная проверка Qdrant коллекции")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        # Получаем информацию о коллекции
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        logger.info(f"📊 Коллекция: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Количество точек: {collection_info.points_count}")

        # Детальная информация о конфигурации
        logger.info(f"\n📋 Полная конфигурация коллекции:")
        logger.info(f"  - config: {collection_info.config}")

        if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
            params = collection_info.config.params
            logger.info(f"  - params: {params}")

            if hasattr(params, 'vectors'):
                vectors_config = params.vectors
                logger.info(f"  - vectors: {vectors_config}")
                logger.info(f"  - vectors type: {type(vectors_config)}")
                logger.info(f"  - vectors dict: {vectors_config.__dict__ if hasattr(vectors_config, '__dict__') else 'No __dict__'}")

                # Проверяем все атрибуты
                for attr in dir(vectors_config):
                    if not attr.startswith('_'):
                        value = getattr(vectors_config, attr)
                        logger.info(f"    - {attr}: {value} (type: {type(value)})")

                if hasattr(vectors_config, 'sparse_vectors'):
                    sparse_config = vectors_config.sparse_vectors
                    logger.info(f"  ✅ Sparse векторы найдены: {sparse_config}")
                    logger.info(f"  - sparse_vectors type: {type(sparse_config)}")

                    if hasattr(sparse_config, '__dict__'):
                        logger.info(f"  - sparse_vectors dict: {sparse_config.__dict__}")

                    # Проверяем все атрибуты sparse_vectors
                    for attr in dir(sparse_config):
                        if not attr.startswith('_'):
                            value = getattr(sparse_config, attr)
                            logger.info(f"    - sparse.{attr}: {value} (type: {type(value)})")
                else:
                    logger.warning("  ❌ Sparse векторы не найдены в vectors")
            else:
                logger.warning("  ❌ Конфигурация векторов не найдена")

        # Получаем несколько точек для проверки
        logger.info(f"\n🔍 Проверяем точки в коллекции...")
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
                    vector_types = list(point.vector.keys())
                    logger.info(f"  Типы векторов: {vector_types}")

                    for vector_name, vector_data in point.vector.items():
                        logger.info(f"  - {vector_name}: {type(vector_data)}")
                        if hasattr(vector_data, '__dict__'):
                            logger.info(f"    dict: {vector_data.__dict__}")

                        # Для sparse векторов
                        if vector_name == 'sparse':
                            if hasattr(vector_data, 'indices') and hasattr(vector_data, 'values'):
                                logger.info(f"    ✅ Sparse вектор: {len(vector_data.indices)} индексов, {len(vector_data.values)} значений")
                                if vector_data.indices:
                                    logger.info(f"      Индексы: {vector_data.indices[:10]}...")
                                    logger.info(f"      Значения: {[f'{v:.3f}' for v in vector_data.values[:10]]}...")
                            else:
                                logger.info(f"    ❌ Неправильный формат sparse вектора: {vector_data}")
                else:
                    logger.info(f"  Вектор: {type(point.vector)}")
            else:
                logger.warning("  ⚠️ Вектор не найден")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке Qdrant: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    check_qdrant_detailed()
