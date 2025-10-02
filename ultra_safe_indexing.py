#!/usr/bin/env python3
"""
Ультра-безопасная индексация с минимальным потреблением памяти
"""
import sys
import os
import gc
import psutil
from loguru import logger

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_encoding():
    """Настраивает правильную кодировку"""
    logger.info("🔧 Настройка кодировки UTF-8...")
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    logger.success("✅ Кодировка настроена: UTF-8")

def monitor_memory():
    """Мониторит использование памяти"""
    memory = psutil.virtual_memory()
    logger.info(f"💾 Память: {memory.percent:.1f}% ({memory.used / 1024**3:.1f} GB / {memory.total / 1024**3:.1f} GB)")

    if memory.percent > 85:
        logger.warning("⚠️  Высокое использование памяти!")
        gc.collect()
        return False
    return True

def ultra_conservative_settings():
    """Ультра-консервативные настройки для экономии памяти"""
    logger.info("🔧 Ультра-консервативные настройки...")

    # Минимальные batch_size
    os.environ["EMBEDDING_BATCH_SIZE"] = "1"      # Один текст за раз!
    os.environ["SPARSE_BATCH_SIZE"] = "1"         # Минимум
    os.environ["DENSE_BATCH_SIZE"] = "1"          # Минимум

    # Минимальная длина документа
    os.environ["EMBEDDING_MAX_LENGTH_DOC"] = "256"  # Очень коротко

    # Только CPU, никакого GPU
    os.environ["EMBEDDINGS_BACKEND"] = "onnx"
    os.environ["EMBEDDING_DEVICE"] = "cpu"

    # Отключаем все оптимизации
    os.environ["ADAPTIVE_BATCHING"] = "false"
    os.environ["EMBEDDING_USE_FP16"] = "false"
    os.environ["USE_SPARSE"] = "false"  # Отключаем sparse векторы

    logger.info("✅ Ультра-консервативные настройки применены")

def run_ultra_safe_indexing():
    """Запускает ультра-безопасную индексацию"""
    logger.info("🚀 Запуск ультра-безопасной индексации...")

    try:
        from scripts.indexer import Indexer

        # Мониторим память перед запуском
        if not monitor_memory():
            logger.error("❌ Слишком мало свободной памяти для запуска")
            return False

        indexer = Indexer()

        # Запускаем с ультра-консервативными параметрами
        result = indexer.reindex(
            mode='full',
            strategy='jina',
            use_cache=True,
            max_pages=50,  # Ограничиваем количество страниц для теста
            sparse=False,  # Отключаем sparse векторы
            backend='onnx'  # Только CPU
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
    """Агрессивная очистка памяти"""
    logger.info("🧹 Агрессивная очистка памяти...")

    # Принудительная сборка мусора
    for _ in range(3):
        gc.collect()

    # Мониторим результат
    monitor_memory()

def main():
    """Основная функция"""
    logger.info("🎯 УЛЬТРА-БЕЗОПАСНАЯ ИНДЕКСАЦИЯ")

    # Настраиваем кодировку
    setup_encoding()

    # Применяем ультра-консервативные настройки
    ultra_conservative_settings()

    # Агрессивная очистка памяти
    cleanup_memory()

    # Запускаем индексацию
    success = run_ultra_safe_indexing()

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
