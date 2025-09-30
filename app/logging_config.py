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
    if not isinstance(text, str):
        return str(text)

    # Удаляем zero-width space и другие проблемные символы
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)

    # Заменяем другие проблемные символы на безопасные
    text = text.replace('\u2013', '-')  # en dash
    text = text.replace('\u2014', '--')  # em dash
    text = text.replace('\u2018', "'")  # left single quotation mark
    text = text.replace('\u2019', "'")  # right single quotation mark
    text = text.replace('\u201c', '"')  # left double quotation mark
    text = text.replace('\u201d', '"')  # right double quotation mark

    return text


def setup_windows_encoding():
    """Настраивает кодировку для Windows"""

    # Устанавливаем UTF-8 кодировку для Python
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    # Для Windows устанавливаем кодовую страницу UTF-8
    if platform.system() == 'Windows':
        try:
            import subprocess
            subprocess.run(['chcp', '65001'], check=False,
                         capture_output=True, shell=True)
        except Exception:
            pass

    # Настраиваем stdout/stderr для UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


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
