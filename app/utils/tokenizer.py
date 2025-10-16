#!/usr/bin/env python3
"""
Унифицированный токенайзер для RAG системы
Обеспечивает быструю и консистентную оценку длины текста
"""

import os
from typing import Optional, List, Union
from loguru import logger


class UnifiedTokenizer:
    """
    Унифицированный токенайзер для быстрой оценки длины текста
    Использует кэширование и оптимизации для производительности
    """

    def __init__(self):
        self._tokenizer = None
        self._cache = {}
        self._cache_size = 1000  # Максимальный размер кэша

    def _get_tokenizer(self):
        """Ленивая инициализация токенайзера"""
        if self._tokenizer is None:
            try:
                from transformers import AutoTokenizer
                # Используем быстрый токенайзер BGE-M3
                self._tokenizer = AutoTokenizer.from_pretrained(
                    "BAAI/bge-m3",
                    trust_remote_code=True,
                    use_fast=True  # Быстрый токенайзер
                )
                logger.info("Инициализирован быстрый токенайзер BGE-M3")
            except Exception as e:
                logger.warning(f"Не удалось загрузить BGE-M3 токенайзер: {e}")
                # Fallback на простой подсчет слов
                self._tokenizer = None

        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """
        Быстрый подсчет токенов с кэшированием

        Args:
            text: Текст для подсчета

        Returns:
            Количество токенов
        """
        if not text or not isinstance(text, str):
            return 0

        # Проверяем кэш
        text_hash = hash(text)
        if text_hash in self._cache:
            return self._cache[text_hash]

        # Подсчитываем токены
        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            try:
                # Используем encode без специальных токенов для точности
                tokens = tokenizer.encode(text, add_special_tokens=False)
                token_count = len(tokens)
            except Exception as e:
                logger.warning(f"Ошибка токенизации: {e}, используем fallback")
                token_count = self._fallback_count(text)
        else:
            token_count = self._fallback_count(text)

        # Кэшируем результат
        self._cache[text_hash] = token_count

        # Очищаем кэш если он слишком большой
        if len(self._cache) > self._cache_size:
            # Удаляем 20% самых старых записей
            items_to_remove = len(self._cache) // 5
            keys_to_remove = list(self._cache.keys())[:items_to_remove]
            for key in keys_to_remove:
                del self._cache[key]

        return token_count

    def _fallback_count(self, text: str) -> int:
        """
        Fallback метод подсчета токенов
        Использует эмпирическую формулу: ~1.3 слова на токен
        """
        words = len(text.split())
        return int(words * 1.3)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Усечение текста по количеству токенов. Сохраняет начало текста.

        Args:
            text: Исходный текст
            max_tokens: Максимальное число токенов

        Returns:
            Усеченный текст, не превышающий max_tokens
        """
        if not text or max_tokens <= 0:
            return ""

        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            try:
                input_ids = tokenizer.encode(text, add_special_tokens=False)
                if len(input_ids) <= max_tokens:
                    return text
                sliced = input_ids[:max_tokens]
                return tokenizer.decode(sliced, skip_special_tokens=True)
            except Exception as e:
                logger.warning(f"Ошибка усечения по токенам: {e}, используем fallback")

        # Fallback: приблизительное усечение по словам
        # Оценим соотношение слов к токенам ~1.3
        approx_words = max(1, int(max_tokens * 1.3))
        words = text.split()
        if len(words) <= approx_words:
            return text
        return " ".join(words[:approx_words])

    def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """
        Пакетный подсчет токенов для нескольких текстов

        Args:
            texts: Список текстов

        Returns:
            Список количества токенов для каждого текста
        """
        if not texts:
            return []

        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            try:
                # Пакетная токенизация для эффективности
                encoded = tokenizer(texts, add_special_tokens=False, padding=False, truncation=False)
                return [len(tokens) for tokens in encoded['input_ids']]
            except Exception as e:
                logger.warning(f"Ошибка пакетной токенизации: {e}, используем fallback")
                return [self._fallback_count(text) for text in texts]
        else:
            return [self._fallback_count(text) for text in texts]

    def is_optimal_size(self, text: str, min_tokens: int = 410, max_tokens: int = 614) -> bool:
        """
        Проверяет, находится ли текст в оптимальном диапазоне токенов

        Args:
            text: Текст для проверки
            min_tokens: Минимальное количество токенов
            max_tokens: Максимальное количество токенов

        Returns:
            True если размер оптимальный
        """
        token_count = self.count_tokens(text)
        return min_tokens <= token_count <= max_tokens

    def get_size_category(self, text: str) -> str:
        """
        Определяет категорию размера текста

        Args:
            text: Текст для анализа

        Returns:
            Категория: 'short', 'medium', 'long'
        """
        token_count = self.count_tokens(text)

        if token_count < 300:
            return 'short'
        elif token_count < 800:
            return 'medium'
        else:
            return 'long'

    def clear_cache(self):
        """Очищает кэш токенайзера"""
        self._cache.clear()
        logger.debug("Кэш токенайзера очищен")


# Глобальный экземпляр токенайзера
_tokenizer_instance: Optional[UnifiedTokenizer] = None


def get_tokenizer() -> UnifiedTokenizer:
    """
    Возвращает глобальный экземпляр токенайзера

    Returns:
        UnifiedTokenizer: Экземпляр токенайзера
    """
    global _tokenizer_instance
    if _tokenizer_instance is None:
        _tokenizer_instance = UnifiedTokenizer()
    return _tokenizer_instance


def count_tokens(text: str) -> int:
    """
    Быстрая функция для подсчета токенов

    Args:
        text: Текст для подсчета

    Returns:
        Количество токенов
    """
    return get_tokenizer().count_tokens(text)


def count_tokens_batch(texts: List[str]) -> List[int]:
    """
    Пакетная функция для подсчета токенов

    Args:
        texts: Список текстов

    Returns:
        Список количества токенов
    """
    return get_tokenizer().count_tokens_batch(texts)


def is_optimal_size(text: str, min_tokens: int = 410, max_tokens: int = 614) -> bool:
    """
    Проверяет оптимальность размера текста

    Args:
        text: Текст для проверки
        min_tokens: Минимальное количество токенов
        max_tokens: Максимальное количество токенов

    Returns:
        True если размер оптимальный
    """
    return get_tokenizer().is_optimal_size(text, min_tokens, max_tokens)


def get_size_category(text: str) -> str:
    """
    Определяет категорию размера текста

    Args:
        text: Текст для анализа

    Returns:
        Категория размера
    """
    return get_tokenizer().get_size_category(text)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """
    Глобальная функция усечения текста по количеству токенов.
    """
    return get_tokenizer().truncate_to_tokens(text, max_tokens)
