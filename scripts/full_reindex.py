#!/usr/bin/env python3
"""
Полная переиндексация с sparse векторами
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from ingestion.pipeline import crawl_and_index

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def main():
    """Выполняет полную переиндексацию с sparse векторами"""
    logger.info("🚀 Полная переиндексация с sparse векторами")
    logger.info("=" * 60)

    logger.info(f"📋 Коллекция: {CONFIG.qdrant_collection}")
    logger.info(f"📊 Backend: {CONFIG.embeddings_backend}")
    logger.info(f"📊 Sparse векторы: {'включены' if CONFIG.use_sparse else 'отключены'}")
    logger.info(f"📊 Размер чанков: {CONFIG.chunk_min_tokens}-{CONFIG.chunk_max_tokens} токенов")

    try:
        # Выполняем полную переиндексацию
        # incremental=False означает полное пересканирование
        # use_cache=True использует кеш для ускорения
        # reindex_mode="full" принудительно переиндексирует все

        logger.info("\n📝 Начинаем полную переиндексацию...")
        logger.warning("⚠️ Это может занять длительное время!")

        result = crawl_and_index(
            incremental=False,  # Полное пересканирование
            use_cache=True,     # Используем кеш для ускорения
            reindex_mode="full" # Принудительная переиндексация
        )

        logger.success(f"✅ Переиндексация завершена!")
        logger.info(f"📊 Результат: {result}")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при переиндексации: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    main()
