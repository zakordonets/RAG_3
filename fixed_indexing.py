#!/usr/bin/env python3
"""
Исправленная индексация с правильной обработкой кодировок
"""
import sys
import os
import gc
from loguru import logger

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_encoding():
    """Настраивает правильную кодировку для всех операций"""
    logger.info("🔧 Настройка кодировки UTF-8...")

    # Устанавливаем переменные окружения
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    # Настраиваем stdout/stderr
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    logger.success("✅ Кодировка настроена: UTF-8")

def safe_text_processing(text: str) -> str:
    """Безопасная обработка текста с исправлением кодировок"""
    if not text:
        return ""

    try:
        # Если текст уже строка, проверяем его корректность
        if isinstance(text, str):
            # Пробуем закодировать/декодировать для проверки
            text.encode('utf-8')
            return text
    except UnicodeEncodeError:
        # Если есть проблемы, исправляем их
        try:
            return text.encode('utf-8', errors='ignore').decode('utf-8')
        except:
            return str(text).encode('utf-8', errors='ignore').decode('utf-8')

    return text

def optimize_environment():
    """Оптимизирует переменные окружения"""
    logger.info("🔧 Оптимизация настроек...")

    # Уменьшаем batch_size для экономии памяти
    os.environ["EMBEDDING_BATCH_SIZE"] = "4"  # Еще меньше для стабильности
    os.environ["SPARSE_BATCH_SIZE"] = "8"     # Уменьшено
    os.environ["DENSE_BATCH_SIZE"] = "4"      # Уменьшено

    # Уменьшаем максимальную длину документа
    os.environ["EMBEDDING_MAX_LENGTH_DOC"] = "512"  # Еще меньше

    # Отключаем DirectML для избежания ошибок
    os.environ["EMBEDDINGS_BACKEND"] = "onnx"  # Только CPU

    # Отключаем адаптивный батчинг
    os.environ["ADAPTIVE_BATCHING"] = "false"

    logger.info("✅ Настройки оптимизированы для стабильности")

def run_fixed_indexing():
    """Запускает исправленную индексацию"""
    logger.info("🚀 Запуск исправленной индексации...")

    try:
        from scripts.indexer import Indexer

        indexer = Indexer()

        # Запускаем с исправленными параметрами
        result = indexer.reindex(
            mode='full',
            strategy='jina',
            use_cache=True,
            max_pages=None,
            sparse=True,
            backend='onnx'  # Только CPU для стабильности
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
    logger.info("🎯 ИСПРАВЛЕННАЯ ИНДЕКСАЦИЯ С ПРАВИЛЬНЫМИ КОДИРОВКАМИ")

    # Настраиваем кодировку
    setup_encoding()

    # Оптимизируем настройки
    optimize_environment()

    # Очищаем память перед началом
    cleanup_memory()

    # Запускаем индексацию
    success = run_fixed_indexing()

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
