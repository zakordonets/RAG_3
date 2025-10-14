#!/usr/bin/env python3
"""
Тесты для унифицированного токенайзера
"""

import pytest
import time
from app.utils import (
    UnifiedTokenizer,
    get_tokenizer,
    count_tokens,
    count_tokens_batch,
    is_optimal_size,
    get_size_category
)

pytestmark = pytest.mark.unit


class TestUnifiedTokenizer:
    """Тесты для класса UnifiedTokenizer"""

    def test_tokenizer_initialization(self):
        """Тест инициализации токенайзера"""
        tokenizer = UnifiedTokenizer()
        assert tokenizer is not None
        assert tokenizer._tokenizer is None  # Ленивая инициализация

    def test_count_tokens_empty(self):
        """Тест подсчета токенов для пустого текста"""
        tokenizer = UnifiedTokenizer()
        assert tokenizer.count_tokens("") == 0
        assert tokenizer.count_tokens(None) == 0

    def test_count_tokens_simple(self):
        """Тест подсчета токенов для простого текста"""
        tokenizer = UnifiedTokenizer()
        text = "Hello world"
        tokens = tokenizer.count_tokens(text)
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_count_tokens_caching(self):
        """Тест кэширования результатов"""
        tokenizer = UnifiedTokenizer()
        text = "Test text for caching"

        # Первый вызов
        tokens1 = tokenizer.count_tokens(text)
        assert tokens1 > 0

        # Второй вызов должен использовать кэш
        tokens2 = tokenizer.count_tokens(text)
        assert tokens1 == tokens2

        # Проверяем, что результат в кэше
        assert hash(text) in tokenizer._cache

    def test_count_tokens_batch(self):
        """Тест пакетного подсчета токенов"""
        tokenizer = UnifiedTokenizer()
        texts = ["Hello", "World", "Test"]
        tokens = tokenizer.count_tokens_batch(texts)

        assert len(tokens) == len(texts)
        assert all(isinstance(t, int) for t in tokens)
        assert all(t > 0 for t in tokens)

    def test_is_optimal_size(self):
        """Тест проверки оптимального размера"""
        tokenizer = UnifiedTokenizer()

        # Короткий текст
        short_text = "Short text"
        assert not tokenizer.is_optimal_size(short_text, 410, 614)

        # Длинный текст (создаем искусственно длинный)
        long_text = " ".join(["word"] * 1000)
        assert not tokenizer.is_optimal_size(long_text, 410, 614)

    def test_get_size_category(self):
        """Тест определения категории размера"""
        tokenizer = UnifiedTokenizer()

        # Короткий текст
        short_text = "Short text"
        assert tokenizer.get_size_category(short_text) == 'short'

        # Длинный текст
        long_text = " ".join(["word"] * 1000)
        assert tokenizer.get_size_category(long_text) == 'long'

    def test_clear_cache(self):
        """Тест очистки кэша"""
        tokenizer = UnifiedTokenizer()
        text = "Test text"

        # Заполняем кэш
        tokenizer.count_tokens(text)
        assert len(tokenizer._cache) > 0

        # Очищаем кэш
        tokenizer.clear_cache()
        assert len(tokenizer._cache) == 0


class TestTokenizerFunctions:
    """Тесты для функций-оберток"""

    def test_get_tokenizer_singleton(self):
        """Тест получения глобального экземпляра токенайзера"""
        tokenizer1 = get_tokenizer()
        tokenizer2 = get_tokenizer()
        assert tokenizer1 is tokenizer2

    def test_count_tokens_function(self):
        """Тест функции count_tokens"""
        text = "Test text"
        tokens = count_tokens(text)
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_count_tokens_batch_function(self):
        """Тест функции count_tokens_batch"""
        texts = ["Hello", "World"]
        tokens = count_tokens_batch(texts)
        assert len(tokens) == len(texts)
        assert all(isinstance(t, int) for t in tokens)

    def test_is_optimal_size_function(self):
        """Тест функции is_optimal_size"""
        text = "Test text"
        result = is_optimal_size(text, 1, 1000)
        assert isinstance(result, bool)

    def test_get_size_category_function(self):
        """Тест функции get_size_category"""
        text = "Test text"
        category = get_size_category(text)
        assert category in ['short', 'medium', 'long']


class TestTokenizerPerformance:
    """Тесты производительности токенайзера"""

    def test_caching_performance(self):
        """Тест производительности кэширования"""
        tokenizer = UnifiedTokenizer()
        text = "Performance test text"

        # Первый вызов (медленный)
        import time
        start = time.time()
        tokens1 = tokenizer.count_tokens(text)
        first_call_time = time.time() - start

        # Второй вызов (быстрый из кэша)
        start = time.time()
        tokens2 = tokenizer.count_tokens(text)
        second_call_time = time.time() - start

        assert tokens1 == tokens2
        # Второй вызов должен быть значительно быстрее
        assert second_call_time < first_call_time * 0.1

    def test_batch_vs_individual(self):
        """Тест сравнения пакетной и индивидуальной обработки"""
        tokenizer = UnifiedTokenizer()
        texts = ["Text " + str(i) for i in range(10)]

        # Индивидуальная обработка
        start = time.time()
        individual_tokens = [tokenizer.count_tokens(text) for text in texts]
        individual_time = time.time() - start

        # Пакетная обработка
        start = time.time()
        batch_tokens = tokenizer.count_tokens_batch(texts)
        batch_time = time.time() - start

        assert individual_tokens == batch_tokens
        # Пакетная обработка должна быть быстрее
        assert batch_time <= individual_time


if __name__ == "__main__":
    pytest.main([__file__])
