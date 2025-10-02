#!/usr/bin/env python3
"""
Временный скрипт для полной индексации
"""
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.pipeline import crawl_and_index
from loguru import logger

def main():
    logger.info("🚀 Запуск полной индексации...")

    try:
        # Запускаем полную индексацию
        result = crawl_and_index(
            incremental=False,  # Полная индексация
            strategy='jina',     # Используем Jina Reader
            use_cache=True       # Используем кеш
        )

        logger.success(f"✅ Индексация завершена успешно!")
        logger.info(f"📊 Результаты:")
        logger.info(f"   Страниц обработано: {result['pages']}")
        logger.info(f"   Чанков создано: {result['chunks']}")

        return result

    except Exception as e:
        logger.error(f"❌ Ошибка индексации: {e}")
        raise

if __name__ == "__main__":
    main()
