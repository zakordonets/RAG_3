#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с индексацией
"""
import sys
import os
import psutil
import gc
from loguru import logger

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_system_resources():
    """Проверяет системные ресурсы"""
    logger.info("=== СИСТЕМНЫЕ РЕСУРСЫ ===")

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    logger.info(f"CPU использование: {cpu_percent}%")

    # Memory
    memory = psutil.virtual_memory()
    logger.info(f"Память: {memory.percent}% используется ({memory.used / 1024**3:.1f} GB / {memory.total / 1024**3:.1f} GB)")

    # Available memory
    available_gb = memory.available / 1024**3
    logger.info(f"Доступно памяти: {available_gb:.1f} GB")

    if memory.percent > 90:
        logger.warning("⚠️  ВЫСОКОЕ ИСПОЛЬЗОВАНИЕ ПАМЯТИ!")
    if cpu_percent > 95:
        logger.warning("⚠️  ВЫСОКАЯ НАГРУЗКА CPU!")

def check_semantic_chunker():
    """Проверяет доступность семантического чанкера"""
    logger.info("=== ПРОВЕРКА СЕМАНТИЧЕСКОГО ЧАНКЕРА ===")

    try:
        from ingestion.semantic_chunker import chunk_text_semantic, get_semantic_chunker
        logger.success("✅ Семантический чанкер доступен")

        # Проверяем инициализацию
        try:
            chunker = get_semantic_chunker()
            logger.info(f"Чанкер инициализирован: min_size={chunker.min_chunk_size}, max_size={chunker.max_chunk_size}")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации чанкера: {e}")

    except ImportError as e:
        logger.error(f"❌ Семантический чанкер недоступен: {e}")
        return False

    return True

def test_semantic_chunking():
    """Тестирует семантический чанкинг"""
    logger.info("=== ТЕСТ СЕМАНТИЧЕСКОГО ЧАНКИНГА ===")

    test_text = """
    Это тестовый текст для проверки семантического чанкинга.
    Он содержит несколько предложений, которые должны быть разбиты на семантически связанные части.

    Первый абзац описывает основную идею. Второй абзац содержит дополнительную информацию.
    Третий абзац завершает тему.
    """

    try:
        from ingestion.chunker import chunk_text

        # Тест с семантическим чанкингом
        chunks = chunk_text(test_text, use_semantic=True)
        logger.info(f"Семантический чанкинг: {len(chunks)} чанков")
        for i, chunk in enumerate(chunks):
            logger.debug(f"Чанк {i+1}: {len(chunk)} символов")

        # Тест без семантического чанкинга
        chunks_simple = chunk_text(test_text, use_semantic=False)
        logger.info(f"Простой чанкинг: {len(chunks_simple)} чанков")

        return len(chunks) > 0

    except Exception as e:
        logger.error(f"❌ Ошибка тестирования чанкинга: {e}")
        return False

def check_dependencies():
    """Проверяет зависимости"""
    logger.info("=== ПРОВЕРКА ЗАВИСИМОСТЕЙ ===")

    dependencies = [
        'sentence_transformers',
        'numpy',
        'torch',
        'transformers'
    ]

    for dep in dependencies:
        try:
            __import__(dep)
            logger.success(f"✅ {dep} установлен")
        except ImportError:
            logger.warning(f"⚠️  {dep} не установлен")

def main():
    """Основная функция диагностики"""
    logger.info("🔍 ДИАГНОСТИКА ПРОБЛЕМ ИНДЕКСАЦИИ")

    check_system_resources()
    check_dependencies()

    if check_semantic_chunker():
        test_semantic_chunking()

    logger.info("=== РЕКОМЕНДАЦИИ ===")

    # Проверяем память
    memory = psutil.virtual_memory()
    if memory.available < 4 * 1024**3:  # Меньше 4GB
        logger.warning("💡 Рекомендация: Освободите память или уменьшите batch_size")

    # Проверяем CPU
    cpu_count = psutil.cpu_count()
    logger.info(f"💡 Доступно CPU ядер: {cpu_count}")

    # Принудительная сборка мусора
    gc.collect()
    logger.info("🧹 Выполнена сборка мусора")

if __name__ == "__main__":
    main()
