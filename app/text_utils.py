#!/usr/bin/env python3
"""
Утилиты для безопасной обработки текстов с исправлением кодировок
"""

import re
import unicodedata
from typing import Optional, List
from loguru import logger


def safe_text_encoding(text: str) -> str:
    """
    Безопасно обрабатывает текст с исправлением проблем кодировки.

    Args:
        text: Исходный текст

    Returns:
        Исправленный текст в UTF-8
    """
    if not text:
        return ""

    if not isinstance(text, str):
        text = str(text)

    try:
        # Проверяем, можно ли закодировать текст в UTF-8
        text.encode('utf-8')
        return text
    except UnicodeEncodeError:
        # Если есть проблемы с кодировкой, исправляем их
        try:
            # Нормализуем Unicode символы
            normalized = unicodedata.normalize('NFKD', text)

            # Удаляем проблемные символы и заменяем на безопасные
            cleaned = ""
            for char in normalized:
                try:
                    # Пробуем закодировать каждый символ
                    char.encode('utf-8')
                    cleaned += char
                except UnicodeEncodeError:
                    # Заменяем проблемные символы на похожие или удаляем
                    if char in ['\u2013', '\u2014']:  # en-dash, em-dash
                        cleaned += '-'
                    elif char in ['\u2018', '\u2019']:  # smart quotes
                        cleaned += "'"
                    elif char in ['\u201c', '\u201d']:  # smart double quotes
                        cleaned += '"'
                    elif char in ['\u2026']:  # ellipsis
                        cleaned += '...'
                    elif ord(char) > 127:  # не-ASCII символы
                        # Пытаемся заменить на ASCII аналог
                        ascii_char = unicodedata.normalize('NFD', char).encode('ascii', 'ignore').decode('ascii')
                        if ascii_char:
                            cleaned += ascii_char
                        # Иначе просто пропускаем
                    # Для остальных символов (включая ASCII) просто добавляем
                    else:
                        cleaned += char

            # Финальная проверка
            cleaned.encode('utf-8')
            logger.debug(f"Исправлена кодировка текста: {len(text)} -> {len(cleaned)} символов")
            return cleaned

        except Exception as e:
            logger.warning(f"Не удалось исправить кодировку текста: {e}")
            # Последний fallback - просто удаляем проблемные символы
            return text.encode('utf-8', errors='ignore').decode('utf-8')


def clean_text_for_processing(text: str) -> str:
    """
    Очищает текст для дальнейшей обработки.

    Args:
        text: Исходный текст

    Returns:
        Очищенный текст
    """
    if not text:
        return ""

    # Сначала исправляем кодировку
    text = safe_text_encoding(text)

    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    # Удаляем нулевые символы и другие управляющие символы
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    return text


def validate_text_quality(text: str, min_length: int = 10) -> tuple[bool, str]:
    """
    Проверяет качество текста.

    Args:
        text: Текст для проверки
        min_length: Минимальная длина текста

    Returns:
        Tuple (is_valid, error_message)
    """
    if not text:
        return False, "Пустой текст"

    # Исправляем кодировку
    clean_text = clean_text_for_processing(text)

    if len(clean_text) < min_length:
        return False, f"Текст слишком короткий: {len(clean_text)} < {min_length}"

    # Проверяем, что текст содержит хотя бы некоторые буквы
    if not re.search(r'[а-яёa-z]', clean_text, re.IGNORECASE):
        return False, "Текст не содержит букв"

    # Проверяем, что текст не состоит только из специальных символов
    if re.match(r'^[^\w\s]+$', clean_text):
        return False, "Текст состоит только из специальных символов"

    return True, ""


def safe_batch_text_processing(texts: List[str]) -> List[str]:
    """
    Безопасно обрабатывает батч текстов.

    Args:
        texts: Список текстов

    Returns:
        Список обработанных текстов
    """
    processed_texts = []

    for i, text in enumerate(texts):
        try:
            clean_text = clean_text_for_processing(text)
            processed_texts.append(clean_text)
        except Exception as e:
            logger.warning(f"Ошибка обработки текста {i}: {e}")
            # Добавляем пустую строку вместо проблемного текста
            processed_texts.append("")

    return processed_texts


def is_text_encoding_safe(text: str) -> bool:
    """
    Проверяет, безопасна ли кодировка текста.

    Args:
        text: Текст для проверки

    Returns:
        True если кодировка безопасна
    """
    try:
        if isinstance(text, str):
            text.encode('utf-8')
            return True
        return False
    except UnicodeEncodeError:
        return False
