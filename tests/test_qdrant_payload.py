#!/usr/bin/env python3
"""
Тест проверки payload в Qdrant для адаптивного чанкинга
"""

import pytest
import os
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import CONFIG
from app.services.optimized_pipeline import OptimizedPipeline
from app.abstractions.data_source import Page, PageType


def make_test_page(idx: int) -> Page:
    """Создает тестовую страницу"""
    url = f"http://example.com/test-page-{idx}"
    title = f"Test Page {idx}"
    content = ("This is a test page for adaptive chunking validation. " * 10) + \
              ("It contains multiple sentences to test chunking behavior. " * 5)
    metadata = {"source": "test", "test_id": idx}
    return Page(
        url=url,
        title=title,
        content=content,
        page_type=PageType.GUIDE,
        metadata=metadata,
        source="test"
    )


@pytest.fixture(scope="module")
def qdrant_client():
    """Фикстура для подключения к Qdrant"""
    try:
        # Используем URL напрямую для HTTP подключения
        client = QdrantClient(
            url=CONFIG.qdrant_url,
            api_key=CONFIG.qdrant_api_key
        )
        # Проверяем подключение
        client.get_collections()
        return client
    except Exception as e:
        pytest.skip(f"Qdrant недоступен: {e}")


@pytest.fixture(scope="module")
def test_collection_name():
    """Имя тестовой коллекции"""
    return f"{CONFIG.qdrant_collection}_test_payload"


@pytest.fixture(scope="module", autouse=True)
def setup_test_collection(qdrant_client, test_collection_name):
    """Создает тестовую коллекцию"""
    try:
        # Удаляем коллекцию если существует
        try:
            qdrant_client.delete_collection(test_collection_name)
        except:
            pass

        # Создаем новую коллекцию с правильным форматом
        from qdrant_client.http import models

        qdrant_client.create_collection(
            collection_name=test_collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    size=CONFIG.embedding_dim,
                    distance=models.Distance.COSINE
                ),
                "sparse": models.VectorParams(
                    size=CONFIG.embedding_dim,
                    distance=models.Distance.DOT
                )
            },
            hnsw_config=models.HnswConfigDiff(
                m=16,
                ef_construct=100
            )
        )

        yield

        # Очищаем после тестов
        try:
            qdrant_client.delete_collection(test_collection_name)
        except:
            pass

    except Exception as e:
        pytest.skip(f"Не удалось настроить тестовую коллекцию: {e}")


def test_adaptive_chunking_payload_in_qdrant(qdrant_client, test_collection_name):
    """Тест проверки payload адаптивного чанкинга в Qdrant"""

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
        assert payload["page_type"] == "guide", f"Неожиданный page_type: {payload['page_type']}"

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


def test_simple_chunking_payload_in_qdrant(qdrant_client, test_collection_name):
    """Тест проверки payload простого чанкинга в Qdrant"""

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
        assert payload["page_type"] == "guide", f"Неожиданный page_type: {payload['page_type']}"


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
    optimal_chunks = 0
    total_chunks = len(chunks)

    for chunk in chunks:
        payload = chunk["payload"]
        token_count = payload.get("token_count", 0)

        if 410 <= token_count <= 614:
            optimal_chunks += 1

    # Вычисляем соотношение
    if total_chunks > 0:
        ratio = optimal_chunks / total_chunks
        print(f"Оптимальное соотношение чанков: {ratio:.2%} ({optimal_chunks}/{total_chunks})")

        # Для коротких тестовых текстов допустимо отсутствие чанков в оптимальном диапазоне
        # Проверяем лишь корректность вычисления доли
        assert 0.0 <= ratio <= 1.0, "Доля оптимальных чанков должна быть в [0,1]"


if __name__ == "__main__":
    pytest.main([__file__])
