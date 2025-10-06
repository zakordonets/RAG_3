#!/usr/bin/env python3
"""
Настройка логирования с корректной кодировкой для Windows
"""

import sys
import re
import os
import platform
from loguru import logger


def clean_text_for_logging(text: str) -> str:
    """Очищает текст от символов, которые могут вызвать проблемы с кодировкой в логах"""
    from .text_processor import clean_text_for_logging as _clean_text_for_logging
    return _clean_text_for_logging(text)


def setup_windows_encoding():
    """Настраивает кодировку для Windows"""
    from .text_processor import setup_windows_encoding as _setup_windows_encoding
    return _setup_windows_encoding()


def configure_logging():
    """Настраивает логирование с корректной кодировкой для Windows"""

    # Сначала настраиваем кодировку системы
    setup_windows_encoding()

    # Удаляем стандартный обработчик
    logger.remove()

    # Создаем папку для логов
    os.makedirs("logs", exist_ok=True)

    # Добавляем обработчик для консоли с принудительной UTF-8
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        colorize=True,  # Цвета должны работать с UTF-8
        enqueue=True
    )

    # Файловые обработчики (Loguru по умолчанию использует UTF-8 для файлов)
    logger.add(
        "logs/app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days"
    )

    # Добавляем обработчик для ошибок
    logger.add(
        "logs/error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        retention="30 days"
    )


def test_logging():
    """Тестирует логирование с кириллическими символами"""
    logger.info("Тест логирования: русские символы")
    logger.warning("Предупреждение с кириллицей")
    logger.error("Ошибка с русским текстом")
    logger.debug("Отладочное сообщение: тестирование кодировки UTF-8")

    # Тест с emoji и специальными символами
    logger.info("Тест с emoji: 🚀 и специальными символами: «кавычки»")


# Автоматически настраиваем логирование при импорте модуля
configure_logging()
