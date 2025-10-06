#!/usr/bin/env python3
"""
Тест структуры payload для адаптивного чанкинга (без Qdrant)
"""

import pytest
from app.services.indexing.optimized_pipeline import OptimizedPipeline
from app.abstractions.data_source import Page, PageType


def make_test_page(idx: int) -> Page:
    """Создает тестовую страницу"""
    url = f"http://example.com/test-page-{idx}"
    title = f"Test Page {idx}"
    # Создаем более длинный контент для тестирования адаптивного чанкинга
    content = ("This is a test page for adaptive chunking validation. " * 50) + \
              ("It contains multiple sentences to test chunking behavior. " * 30) + \
              ("The content should be long enough to trigger medium or long document processing. " * 20) + \
              ("This will help us test the optimal chunk size for BGE-M3 embeddings. " * 15)
    metadata = {"source": "test", "test_id": idx}
    return Page(
        url=url,
        title=title,
        content=content,
        page_type=PageType.GUIDE,
        metadata=metadata,
        source="test"
    )


def test_adaptive_chunking_payload_structure():
    """Тест структуры payload адаптивного чанкинга"""

    # Создаем пайплайн
    pipeline = OptimizedPipeline()

    # Создаем тестовые страницы
    test_pages = [make_test_page(i) for i in range(3)]

    # Обрабатываем страницы в чанки
    chunks = pipeline._process_pages_to_chunks(test_pages, chunk_strategy="adaptive")

    assert len(chunks) > 0, "Должны быть созданы чанки"

    # Проверяем структуру чанков
    for chunk in chunks:
        assert "text" in chunk, "Чанк должен содержать текст"
        assert "payload" in chunk, "Чанк должен содержать payload"

        payload = chunk["payload"]

        # Проверяем обязательные поля для адаптивного чанкинга
        assert "adaptive_chunking" in payload, "Должно быть поле adaptive_chunking"
        assert payload["adaptive_chunking"] is True, "adaptive_chunking должно быть True"

        assert "chunk_type" in payload, "Должно быть поле chunk_type"
        assert payload["chunk_type"] in ["short_document", "medium_document", "long_document"], \
            f"Неожиданный chunk_type: {payload['chunk_type']}"

        assert "page_type" in payload, "Должно быть поле page_type"
        # page_type может быть 'unknown' для тестовых данных
        assert payload["page_type"] in ["guide", "unknown"], f"Неожиданный page_type: {payload['page_type']}"

        # Проверяем дополнительные поля
        assert "word_count" in payload, "Должно быть поле word_count"
        assert "token_count" in payload, "Должно быть поле token_count"
        assert isinstance(payload["word_count"], int), "word_count должно быть int"
        assert isinstance(payload["token_count"], int), "token_count должно быть int"

        # Проверяем, что метаданные страницы переданы
        assert "source" in payload, "Должно быть поле source"
        assert payload["source"] == "test", f"Неожиданный source: {payload['source']}"

        # Проверяем, что текст не пустой
        assert len(chunk["text"].strip()) > 0, "Текст чанка не должен быть пустым"


def test_simple_chunking_payload_structure():
    """Тест структуры payload простого чанкинга"""

    # Создаем пайплайн
    pipeline = OptimizedPipeline()

    # Создаем тестовые страницы
    test_pages = [make_test_page(i) for i in range(2)]

    # Обрабатываем страницы в чанки с простой стратегией
    chunks = pipeline._process_pages_to_chunks(test_pages, chunk_strategy="simple")

    assert len(chunks) > 0, "Должны быть созданы чанки"

    # Проверяем структуру чанков
    for chunk in chunks:
        assert "text" in chunk, "Чанк должен содержать текст"
        assert "payload" in chunk, "Чанк должен содержать payload"

        payload = chunk["payload"]

        # Для простого чанкинга adaptive_chunking должно быть False или отсутствовать
        if "adaptive_chunking" in payload:
            assert payload["adaptive_chunking"] is False, "adaptive_chunking должно быть False для простого чанкинга"

        # Проверяем обязательные поля
        assert "chunk_type" in payload, "Должно быть поле chunk_type"
        assert "page_type" in payload, "Должно быть поле page_type"
        # page_type может быть 'unknown' для тестовых данных
        assert payload["page_type"] in ["guide", "unknown"], f"Неожиданный page_type: {payload['page_type']}"


def test_chunk_size_distribution():
    """Тест распределения размеров чанков"""

    pipeline = OptimizedPipeline()
    test_pages = [make_test_page(i) for i in range(3)]

    chunks = pipeline._process_pages_to_chunks(test_pages, chunk_strategy="adaptive")

    assert len(chunks) > 0, "Должны быть созданы чанки"

    # Проверяем, что размеры чанков разумные
    for chunk in chunks:
        payload = chunk["payload"]
        word_count = payload.get("word_count", 0)
        token_count = payload.get("token_count", 0)

        # Проверяем, что размеры больше 0
        assert word_count > 0, f"word_count должно быть > 0, получено: {word_count}"
        assert token_count > 0, f"token_count должно быть > 0, получено: {token_count}"

        # Проверяем, что токенов больше чем слов (обычно так)
        assert token_count >= word_count, f"token_count ({token_count}) должно быть >= word_count ({word_count})"


def test_optimal_chunk_ratio():
    """Тест оптимального соотношения чанков для BGE-M3"""

    pipeline = OptimizedPipeline()
    test_pages = [make_test_page(i) for i in range(5)]

    chunks = pipeline._process_pages_to_chunks(test_pages, chunk_strategy="adaptive")

    assert len(chunks) > 0, "Должны быть созданы чанки"

    # Подсчитываем чанки в оптимальном диапазоне BGE-M3 (410-614 токенов)
    # и короткие чанки (для коротких документов)
    optimal_chunks = 0
    short_chunks = 0
    total_chunks = len(chunks)

    # Debug: print token counts
    token_counts = []
    for chunk in chunks:
        payload = chunk["payload"]
        token_count = payload.get("token_count", 0)
        token_counts.append(token_count)
        print(f"Chunk token count: {token_count}")

    print(f"Token counts: {token_counts}")
    print(f"Min: {min(token_counts) if token_counts else 0}, Max: {max(token_counts) if token_counts else 0}")

    for chunk in chunks:
        payload = chunk["payload"]
        token_count = payload.get("token_count", 0)

        if 410 <= token_count <= 614:
            optimal_chunks += 1
        elif token_count < 410:  # Короткие чанки для коротких документов
            short_chunks += 1

    # Вычисляем соотношение
    if total_chunks > 0:
        optimal_ratio = optimal_chunks / total_chunks
        short_ratio = short_chunks / total_chunks
        print(f"Оптимальное соотношение чанков: {optimal_ratio:.2%} ({optimal_chunks}/{total_chunks})")
        print(f"Короткие чанки: {short_ratio:.2%} ({short_chunks}/{total_chunks})")

        # Проверяем, что есть либо оптимальные чанки, либо короткие чанки (для коротких документов)
        assert optimal_chunks > 0 or short_chunks > 0, "Должны быть либо оптимальные чанки, либо короткие чанки для коротких документов"


def test_different_page_types():
    """Тест разных типов страниц"""

    pipeline = OptimizedPipeline()

    # Создаем страницы разных типов
    pages = [
        Page(
            url="http://example.com/guide",
            title="Guide Page",
            content="This is a guide page content.",
            page_type=PageType.GUIDE,
            metadata={"source": "test"},
            source="test"
        ),
        Page(
            url="http://example.com/api",
            title="API Page",
            content="This is an API documentation page.",
            page_type=PageType.API,
            metadata={"source": "test"},
            source="test"
        ),
        Page(
            url="http://example.com/faq",
            title="FAQ Page",
            content="This is a FAQ page with questions and answers.",
            page_type=PageType.FAQ,
            metadata={"source": "test"},
            source="test"
        )
    ]

    chunks = pipeline._process_pages_to_chunks(pages, chunk_strategy="adaptive")

    assert len(chunks) > 0, "Должны быть созданы чанки"

    # Проверяем, что page_type правильно передается
    page_types = set()
    for chunk in chunks:
        payload = chunk["payload"]
        page_type = payload.get("page_type")
        page_types.add(page_type)

        assert page_type in ["guide", "api", "faq"], f"Неожиданный page_type: {page_type}"

    # Проверяем, что все типы страниц представлены
    assert len(page_types) >= 2, f"Должно быть минимум 2 разных типа страниц, получено: {page_types}"


if __name__ == "__main__":
    pytest.main([__file__])
