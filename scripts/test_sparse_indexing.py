#!/usr/bin/env python3
"""
Тест индексации sparse векторов
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from ingestion.indexer import upsert_chunks

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="DEBUG")

def test_sparse_indexing():
    """Тестирует индексацию с sparse векторами"""

    logger.info("🧪 Тест индексации sparse векторов")
    logger.info("=" * 60)

    # Создаем тестовые чанки
    test_chunks = [
        {
            "text": "Как настроить маршрутизацию в edna Chat Center",
            "payload": {"source": "test", "page": "test_page_1"}
        },
        {
            "text": "API для перенаправления диалогов и сообщений",
            "payload": {"source": "test", "page": "test_page_2"}
        },
        {
            "text": "Документация по настройке кнопок клиента",
            "payload": {"source": "test", "page": "test_page_3"}
        }
    ]

    logger.info(f"📝 Индексируем {len(test_chunks)} тестовых чанков...")

    try:
        result = upsert_chunks(test_chunks)
        logger.success(f"✅ Индексация завершена: {result} чанков")

        # Проверяем, что sparse векторы добавились
        from qdrant_client import QdrantClient
        client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

        # Ищем наши тестовые точки
        points = client.scroll(
            collection_name=CONFIG.qdrant_collection,
            limit=10,
            with_payload=True,
            with_vectors=True
        )[0]

        logger.info(f"📊 Проверяем {len(points)} точек...")

        sparse_found = 0
        for i, point in enumerate(points):
            if hasattr(point, 'vector') and point.vector:
                if isinstance(point.vector, dict):
                    vector_types = list(point.vector.keys())
                    if 'sparse' in vector_types:
                        sparse_found += 1
                        logger.info(f"✅ Точка {i+1}: {vector_types} (включает sparse)")
                    else:
                        logger.info(f"❌ Точка {i+1}: {vector_types} (без sparse)")

        logger.info(f"\n📊 Результат: {sparse_found}/{len(points)} точек содержат sparse векторы")

        if sparse_found > 0:
            logger.success("✅ Sparse векторы успешно индексируются!")
        else:
            logger.error("❌ Sparse векторы не найдены в индексе")

    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_sparse_indexing()
