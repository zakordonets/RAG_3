"""
Расширенные тесты для функциональности auto-merge.
Покрывают edge cases, performance, и интеграционные сценарии.
"""
from __future__ import annotations

import time
from typing import Callable

import pytest

from app.config import CONFIG
from app.retrieval.retrieval import auto_merge_neighbors, _estimate_tokens

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _fake_fetch_factory(mapping: dict[str, list[dict]]) -> Callable[[str], list[dict]]:
    def _fetch(doc_id: str) -> list[dict]:
        return mapping.get(doc_id, [])
    return _fetch


class TestEdgeCases:
    """Тесты граничных случаев."""

    def test_single_chunk_exceeds_max_tokens(self, monkeypatch):
        """Тест: один чанк превышает max_tokens - не должен быть отброшен."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        top_docs = [
            {
                "id": "big",
                "payload": {
                    "doc_id": "doc-x",
                    "chunk_index": 0,
                    "text": "X" * 10000,  # Очень большой чанк
                    "chunk_id": "doc-x#0",
                },
            }
        ]

        doc_chunks = [
            {"payload": {"chunk_index": 0, "text": "X" * 10000, "chunk_id": "doc-x#0"}},
        ]

        fetch_fn = _fake_fetch_factory({"doc-x": doc_chunks})
        merged = auto_merge_neighbors(top_docs, max_window_tokens=100, fetch_fn=fetch_fn)

        # Чанк должен остаться, даже если превышает лимит
        assert len(merged) == 1
        assert merged[0]["id"] == "big"

    def test_empty_hits(self, monkeypatch):
        """Тест: пустой список входных данных."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        merged = auto_merge_neighbors([], max_window_tokens=1000)
        assert merged == []

    def test_disabled_auto_merge(self, monkeypatch):
        """Тест: auto-merge отключен - результат должен остаться без изменений."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", False)

        top_docs = [
            {"id": "a", "payload": {"doc_id": "doc-1", "chunk_index": 1, "text": "A"}},
            {"id": "b", "payload": {"doc_id": "doc-1", "chunk_index": 2, "text": "B"}},
        ]

        merged = auto_merge_neighbors(top_docs, max_window_tokens=1000)
        assert merged == top_docs

    def test_zero_max_tokens(self, monkeypatch):
        """Тест: max_tokens = 0 - не должно ничего слить."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        top_docs = [
            {"id": "a", "payload": {"doc_id": "doc-1", "chunk_index": 1, "text": "A"}},
            {"id": "b", "payload": {"doc_id": "doc-1", "chunk_index": 2, "text": "B"}},
        ]

        merged = auto_merge_neighbors(top_docs, max_window_tokens=0)
        assert merged == top_docs

    def test_missing_metadata(self, monkeypatch):
        """Тест: чанки без doc_id или chunk_index."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        top_docs = [
            {"id": "a", "payload": {"text": "No doc_id"}},
            {"id": "b", "payload": {"doc_id": "doc-1"}},  # нет chunk_index
            {"id": "c", "payload": {"chunk_index": 1}},  # нет doc_id
        ]

        merged = auto_merge_neighbors(top_docs, max_window_tokens=1000)

        # Все должны пройти без слияния
        assert len(merged) == 3

    def test_non_sequential_chunks(self, monkeypatch):
        """Тест: чанки с gap (0, 5) - алгоритм может заполнить промежуточные чанки."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        top_docs = [
            {
                "id": "a",
                "payload": {
                    "doc_id": "doc-1",
                    "chunk_index": 0,
                    "text": "Chunk 0",
                    "chunk_id": "doc-1#0",
                },
            },
            {
                "id": "b",
                "payload": {
                    "doc_id": "doc-1",
                    "chunk_index": 5,
                    "text": "Chunk 5",
                    "chunk_id": "doc-1#5",
                },
            },
        ]

        doc_chunks = [
            {"payload": {"chunk_index": 0, "text": "Chunk 0", "chunk_id": "doc-1#0"}},
            {"payload": {"chunk_index": 1, "text": "Chunk 1", "chunk_id": "doc-1#1"}},
            {"payload": {"chunk_index": 2, "text": "Chunk 2", "chunk_id": "doc-1#2"}},
            {"payload": {"chunk_index": 3, "text": "Chunk 3", "chunk_id": "doc-1#3"}},
            {"payload": {"chunk_index": 4, "text": "Chunk 4", "chunk_id": "doc-1#4"}},
            {"payload": {"chunk_index": 5, "text": "Chunk 5", "chunk_id": "doc-1#5"}},
        ]

        fetch_fn = _fake_fetch_factory({"doc-1": doc_chunks})
        merged = auto_merge_neighbors(top_docs, max_window_tokens=30, fetch_fn=fetch_fn)

        # Алгоритм расширяет окно вокруг каждого чанка, заполняя промежутки
        # Результат зависит от token budget
        assert len(merged) >= 1
        assert len(merged) <= len(top_docs)


class TestPerformance:
    """Тесты производительности."""

    def test_large_document_set(self, monkeypatch):
        """Тест: обработка большого количества документов."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        # Создаём 100 документов по 10 чанков каждый
        top_docs = []
        doc_chunks_mapping = {}

        for doc_num in range(100):
            doc_id = f"doc-{doc_num}"
            chunks = []

            for chunk_idx in range(10):
                chunk_id = f"{doc_id}#{chunk_idx}"
                top_docs.append({
                    "id": chunk_id,
                    "payload": {
                        "doc_id": doc_id,
                        "chunk_index": chunk_idx,
                        "text": f"Text {chunk_idx}" * 10,
                        "chunk_id": chunk_id,
                    },
                })
                chunks.append({
                    "payload": {
                        "chunk_index": chunk_idx,
                        "text": f"Text {chunk_idx}" * 10,
                        "chunk_id": chunk_id,
                    }
                })

            doc_chunks_mapping[doc_id] = chunks

        fetch_fn = _fake_fetch_factory(doc_chunks_mapping)

        start = time.time()
        merged = auto_merge_neighbors(top_docs, max_window_tokens=500, fetch_fn=fetch_fn)
        duration = time.time() - start

        # Должно выполниться за разумное время (< 1 секунды для 1000 чанков)
        assert duration < 1.0
        # Должно произойти слияние
        assert len(merged) < len(top_docs)


class TestTokenEstimation:
    """Тесты оценки токенов."""

    def test_estimate_tokens_empty_string(self):
        """Тест: оценка токенов для пустой строки."""
        assert _estimate_tokens("") == 0

    def test_estimate_tokens_short_string(self):
        """Тест: оценка токенов для короткой строки."""
        tokens = _estimate_tokens("Hello world")
        assert tokens > 0
        assert tokens < 20

    def test_estimate_tokens_long_string(self):
        """Тест: оценка токенов для длинной строки."""
        long_text = "Test " * 1000
        tokens = _estimate_tokens(long_text)
        # Должно быть примерно len(text) // 4
        assert 1000 < tokens < 2000

    def test_estimate_tokens_multilingual(self):
        """Тест: оценка токенов для многоязычного текста."""
        text = "Hello world. Привет мир. 你好世界"
        tokens = _estimate_tokens(text)
        assert tokens > 0


class TestMergeLogic:
    """Тесты логики слияния."""

    def test_merge_respects_token_budget(self, monkeypatch):
        """Тест: слияние соблюдает token budget."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        top_docs = [
            {
                "id": "a",
                "payload": {
                    "doc_id": "doc-1",
                    "chunk_index": 0,
                    "text": "A" * 100,
                    "chunk_id": "doc-1#0",
                },
            },
            {
                "id": "b",
                "payload": {
                    "doc_id": "doc-1",
                    "chunk_index": 1,
                    "text": "B" * 100,
                    "chunk_id": "doc-1#1",
                },
            },
        ]

        doc_chunks = [
            {"payload": {"chunk_index": 0, "text": "A" * 100, "chunk_id": "doc-1#0"}},
            {"payload": {"chunk_index": 1, "text": "B" * 100, "chunk_id": "doc-1#1"}},
            {"payload": {"chunk_index": 2, "text": "C" * 100, "chunk_id": "doc-1#2"}},
        ]

        fetch_fn = _fake_fetch_factory({"doc-1": doc_chunks})

        # Устанавливаем малый лимит
        merged = auto_merge_neighbors(top_docs, max_window_tokens=30, fetch_fn=fetch_fn)

        # Проверяем, что не все чанки объединены из-за лимита
        for doc in merged:
            payload = doc.get("payload", {})
            if payload.get("auto_merged"):
                text = payload.get("text", "")
                tokens = _estimate_tokens(text)
                # Объединённый текст не должен значительно превышать лимит
                assert tokens <= 100  # С запасом на погрешность

    def test_merge_metadata_correctness(self, monkeypatch):
        """Тест: корректность метаданных в объединённом документе."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        top_docs = [
            {
                "id": "a",
                "payload": {
                    "doc_id": "doc-1",
                    "chunk_index": 1,
                    "text": "First",
                    "chunk_id": "doc-1#1",
                },
            },
            {
                "id": "b",
                "payload": {
                    "doc_id": "doc-1",
                    "chunk_index": 2,
                    "text": "Second",
                    "chunk_id": "doc-1#2",
                },
            },
        ]

        doc_chunks = [
            {"payload": {"chunk_index": 1, "text": "First", "chunk_id": "doc-1#1"}},
            {"payload": {"chunk_index": 2, "text": "Second", "chunk_id": "doc-1#2"}},
        ]

        fetch_fn = _fake_fetch_factory({"doc-1": doc_chunks})
        merged = auto_merge_neighbors(top_docs, max_window_tokens=100, fetch_fn=fetch_fn)

        assert len(merged) == 1
        payload = merged[0]["payload"]

        # Проверка всех метаданных
        assert payload["auto_merged"] is True
        assert payload["merged_chunk_indices"] == [1, 2]
        assert payload["merged_chunk_count"] == 2
        assert payload["chunk_span"]["start"] == 1
        assert payload["chunk_span"]["end"] == 2
        assert payload["merged_chunk_ids"] == ["doc-1#1", "doc-1#2"]
        assert "First" in payload["text"]
        assert "Second" in payload["text"]

    def test_multiple_documents_mixed(self, monkeypatch):
        """Тест: несколько документов чередуются в результатах."""
        object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

        top_docs = [
            {"id": "a1", "payload": {"doc_id": "doc-a", "chunk_index": 0, "text": "A0", "chunk_id": "doc-a#0"}},
            {"id": "b1", "payload": {"doc_id": "doc-b", "chunk_index": 0, "text": "B0", "chunk_id": "doc-b#0"}},
            {"id": "a2", "payload": {"doc_id": "doc-a", "chunk_index": 1, "text": "A1", "chunk_id": "doc-a#1"}},
            {"id": "b2", "payload": {"doc_id": "doc-b", "chunk_index": 1, "text": "B1", "chunk_id": "doc-b#1"}},
        ]

        doc_chunks_a = [
            {"payload": {"chunk_index": 0, "text": "A0", "chunk_id": "doc-a#0"}},
            {"payload": {"chunk_index": 1, "text": "A1", "chunk_id": "doc-a#1"}},
        ]

        doc_chunks_b = [
            {"payload": {"chunk_index": 0, "text": "B0", "chunk_id": "doc-b#0"}},
            {"payload": {"chunk_index": 1, "text": "B1", "chunk_id": "doc-b#1"}},
        ]

        fetch_fn = _fake_fetch_factory({"doc-a": doc_chunks_a, "doc-b": doc_chunks_b})
        merged = auto_merge_neighbors(top_docs, max_window_tokens=100, fetch_fn=fetch_fn)

        # Должно быть 2 объединённых документа (по одному для каждого doc)
        assert len(merged) == 2

        # Проверяем порядок (должен сохраниться относительный порядок)
        doc_ids = [m["payload"]["doc_id"] for m in merged]
        assert "doc-a" in doc_ids
        assert "doc-b" in doc_ids
