#!/usr/bin/env python3
"""
Легкий интеграционный тест пайплайна с мок-страницами (без сети и индексации)
"""

import pytest

from app.services.optimized_pipeline import OptimizedPipeline
from app.abstractions.data_source import Page, PageType


def make_page(idx: int) -> Page:
    url = f"http://example.com/page-{idx}"
    title = f"Test Page {idx}"
    content = ("This is a small test page content with several sentences. "
               "It is used to validate adaptive chunking without heavy IO.") * 3
    metadata = {"source": "mock", "idx": idx}
    return Page(
        url=url,
        title=title,
        content=content,
        page_type=PageType.GUIDE,
        metadata=metadata,
        source="mock"
    )


def test_pipeline_process_pages_to_chunks_small_batch():
    pipeline = OptimizedPipeline()

    pages = [make_page(i) for i in range(3)]

    chunks = pipeline._process_pages_to_chunks(pages, chunk_strategy="adaptive")

    assert isinstance(chunks, list)
    assert len(chunks) > 0

    # Проверим, что у чанков есть ожидаемые поля
    sample = chunks[0]
    assert "text" in sample
    assert "payload" in sample
    payload = sample["payload"]
    assert "chunk_type" in payload
    assert payload.get("page_type") is not None
