#!/usr/bin/env python3
"""
Оптимизированная индексация с уменьшенными batch_size для экономии памяти
"""
import sys
import os
import gc
from loguru import logger

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def optimize_environment():
    """Оптимизирует переменные окружения для экономии памяти"""
    logger.info("🔧 Оптимизация настроек для экономии памяти...")

    # Уменьшаем batch_size для экономии памяти
    os.environ["EMBEDDING_BATCH_SIZE"] = "8"  # Было 16, стало 8
    os.environ["SPARSE_BATCH_SIZE"] = "16"    # Было 32, стало 16
    os.environ["DENSE_BATCH_SIZE"] = "8"      # Было 16, стало 8

    # Уменьшаем максимальную длину документа
    os.environ["EMBEDDING_MAX_LENGTH_DOC"] = "1024"  # Было 2048

    # Отключаем адаптивный батчинг для предсказуемости
    os.environ["ADAPTIVE_BATCHING"] = "false"

    # Принудительно используем hybrid backend для лучшей производительности
    os.environ["EMBEDDINGS_BACKEND"] = "hybrid"

    logger.info("✅ Настройки оптимизированы:")
    logger.info(f"   EMBEDDING_BATCH_SIZE: {os.environ['EMBEDDING_BATCH_SIZE']}")
    logger.info(f"   SPARSE_BATCH_SIZE: {os.environ['SPARSE_BATCH_SIZE']}")
    logger.info(f"   DENSE_BATCH_SIZE: {os.environ['DENSE_BATCH_SIZE']}")
    logger.info(f"   EMBEDDING_MAX_LENGTH_DOC: {os.environ['EMBEDDING_MAX_LENGTH_DOC']}")

def run_optimized_indexing():
    """Запускает оптимизированную индексацию"""
    logger.info("🚀 Запуск оптимизированной индексации...")

    try:
        from scripts.indexer import Indexer

        indexer = Indexer()

        # Запускаем с оптимизированными параметрами
        result = indexer.reindex(
            mode='full',
            strategy='jina',
            use_cache=True,
            max_pages=None,  # Без ограничений
            sparse=True,
            backend='hybrid'  # Принудительно hybrid
        )

        if result['success']:
            logger.success("✅ Индексация завершена успешно!")
            logger.info(f"📊 Результаты:")
            logger.info(f"   Страниц: {result.get('pages', 'N/A')}")
            logger.info(f"   Чанков: {result.get('chunks', 'N/A')}")
            logger.info(f"   Время: {result.get('duration', 'N/A')}")
            return True
        else:
            logger.error(f"❌ Ошибка индексации: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def cleanup_memory():
    """Очищает память"""
    logger.info("🧹 Очистка памяти...")
    gc.collect()
    logger.info("✅ Память очищена")

def main():
    """Основная функция"""
    logger.info("🎯 ОПТИМИЗИРОВАННАЯ ИНДЕКСАЦИЯ")

    # Оптимизируем настройки
    optimize_environment()

    # Очищаем память перед началом
    cleanup_memory()

    # Запускаем индексацию
    success = run_optimized_indexing()

    # Финальная очистка
    cleanup_memory()

    if success:
        logger.success("🎉 Индексация завершена успешно!")
        return 0
    else:
        logger.error("💥 Индексация завершилась с ошибкой!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
