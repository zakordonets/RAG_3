#!/usr/bin/env python3
"""
Единый процессор текста для всех операций очистки и обработки.
Консолидирует функции из text_utils.py и logging_config.py.
"""

import re
import unicodedata
import sys
import os
import platform
from typing import Optional, List
from loguru import logger


class TextProcessor:
    """Единый процессор текста для всех операций очистки и обработки"""

    def __init__(self):
        self.logger = logger.bind(component="TextProcessor")

    def safe_text_encoding(self, text: str) -> str:
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
                self.logger.debug(f"Исправлена кодировка текста: {len(text)} -> {len(cleaned)} символов")
                return cleaned

            except Exception as e:
                self.logger.warning(f"Не удалось исправить кодировку текста: {e}")
                # Последний fallback - просто удаляем проблемные символы
                return text.encode('utf-8', errors='ignore').decode('utf-8')

    def clean_for_processing(self, text: str) -> str:
        """
        Очищает текст для дальнейшей обработки (например, для chunking, embeddings).

        Args:
            text: Исходный текст

        Returns:
            Очищенный текст
        """
        if not text:
            return ""

        # Сначала исправляем кодировку
        text = self.safe_text_encoding(text)

        # Удаляем лишние пробелы и переносы строк
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # Удаляем нулевые символы и другие управляющие символы
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        return text

    def clean_for_logging(self, text: str) -> str:
        """
        Очищает текст от символов, которые могут вызвать проблемы с кодировкой в логах.

        Args:
            text: Исходный текст

        Returns:
            Очищенный текст для логирования
        """
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

    def validate_quality(self, text: str, min_length: int = 10) -> tuple[bool, str]:
        """
        Валидирует качество текста.

        Args:
            text: Текст для валидации
            min_length: Минимальная длина текста

        Returns:
            Tuple (is_valid, error_message)
        """
        if not text or not text.strip():
            return False, "Пустой текст"

        clean_text = self.clean_for_processing(text)

        if len(clean_text) < min_length:
            return False, f"Текст слишком короткий: {len(clean_text)} < {min_length}"

        # Проверяем наличие букв
        if not re.search(r'[а-яёa-z]', clean_text, re.IGNORECASE):
            return False, "Текст не содержит букв"

        # Проверяем, что текст не состоит только из спецсимволов
        if re.match(r'^[^\w\s]+$', clean_text):
            return False, "Текст состоит только из спецсимволов"

        return True, ""

    def safe_batch_processing(self, texts: List[str]) -> List[str]:
        """
        Безопасно обрабатывает список текстов.

        Args:
            texts: Список текстов для обработки

        Returns:
            Список обработанных текстов
        """
        processed_texts = []

        for i, text in enumerate(texts):
            try:
                clean_text = self.clean_for_processing(text)
                processed_texts.append(clean_text)
            except Exception as e:
                self.logger.warning(f"Ошибка обработки текста {i}: {e}")
                processed_texts.append("")  # Добавляем пустую строку как fallback

        return processed_texts

    def setup_windows_encoding(self):
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
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# Глобальный экземпляр для обратной совместимости
_text_processor = TextProcessor()

# Функции для обратной совместимости
def safe_text_encoding(text: str) -> str:
    """Безопасно обрабатывает текст с исправлением проблем кодировки."""
    return _text_processor.safe_text_encoding(text)

def clean_text_for_processing(text: str) -> str:
    """Очищает текст для дальнейшей обработки."""
    return _text_processor.clean_for_processing(text)

def clean_text_for_logging(text: str) -> str:
    """Очищает текст от символов, которые могут вызвать проблемы с кодировкой в логах."""
    return _text_processor.clean_for_logging(text)

def validate_text_quality(text: str, min_length: int = 10) -> tuple[bool, str]:
    """Валидирует качество текста."""
    return _text_processor.validate_quality(text, min_length)

def safe_batch_text_processing(texts: List[str]) -> List[str]:
    """Безопасно обрабатывает список текстов."""
    return _text_processor.safe_batch_processing(texts)

def setup_windows_encoding():
    """Настраивает кодировку для Windows"""
    return _text_processor.setup_windows_encoding()
