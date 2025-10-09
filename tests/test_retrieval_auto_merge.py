from __future__ import annotations

from typing import Callable

from app.config import CONFIG
from app.services.search.retrieval import auto_merge_neighbors


def _fake_fetch_factory(mapping: dict[str, list[dict]]) -> Callable[[str], list[dict]]:
    def _fetch(doc_id: str) -> list[dict]:
        return mapping.get(doc_id, [])
    return _fetch


def test_auto_merge_neighbors_merges_adjacent_chunks(monkeypatch):
    object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

    top_docs = [
        {
            "id": "p1",
            "payload": {
                "doc_id": "doc-1",
                "chunk_index": 2,
                "text": "Chunk-2 snippet",
                "chunk_id": "doc-1#2",
            },
        },
        {
            "id": "p2",
            "payload": {
                "doc_id": "doc-1",
                "chunk_index": 3,
                "text": "Chunk-3 snippet",
                "chunk_id": "doc-1#3",
            },
        },
    ]

    doc_chunks = [
        {"payload": {"chunk_index": 1, "text": "Intro segment" * 10, "chunk_id": "doc-1#1"}},
        {"payload": {"chunk_index": 2, "text": "Chunk-2 snippet", "chunk_id": "doc-1#2"}},
        {"payload": {"chunk_index": 3, "text": "Chunk-3 snippet", "chunk_id": "doc-1#3"}},
        {"payload": {"chunk_index": 4, "text": "Outro block" * 30, "chunk_id": "doc-1#4"}},
    ]

    fetch_fn = _fake_fetch_factory({"doc-1": doc_chunks})

    merged = auto_merge_neighbors(top_docs, max_window_tokens=20, fetch_fn=fetch_fn)

    assert len(merged) == 1
    payload = merged[0]["payload"]
    assert payload.get("auto_merged") is True
    assert payload.get("merged_chunk_indices") == [2, 3]
    assert "chunk-2" in payload.get("text", "").lower()
    assert "chunk-3" in payload.get("text", "").lower()
    span = payload.get("chunk_span", {})
    assert span.get("start") == 2
    assert span.get("end") == 3
    assert payload.get("merged_chunk_count") == 2


def test_auto_merge_neighbors_preserves_order_and_missing_docs(monkeypatch):
    object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", True)

    top_docs = [
        {
            "id": "a",
            "payload": {
                "doc_id": "doc-x",
                "chunk_index": 0,
                "text": "Head section",
                "chunk_id": "doc-x#0",
            },
        },
        {
            "id": "standalone",
            "payload": {
                "text": "orphan context",
            },
        },
        {
            "id": "b",
            "payload": {
                "doc_id": "doc-x",
                "chunk_index": 3,
                "text": "Tail section",
                "chunk_id": "doc-x#3",
            },
        },
    ]

    doc_chunks = [
        {"payload": {"chunk_index": 0, "text": "Head section", "chunk_id": "doc-x#0"}},
        {"payload": {"chunk_index": 1, "text": "Mid part A", "chunk_id": "doc-x#1"}},
        {"payload": {"chunk_index": 2, "text": "Mid part B", "chunk_id": "doc-x#2"}},
        {"payload": {"chunk_index": 3, "text": "Tail section", "chunk_id": "doc-x#3"}},
    ]

    fetch_fn = _fake_fetch_factory({"doc-x": doc_chunks})

    merged = auto_merge_neighbors(top_docs, max_window_tokens=4, fetch_fn=fetch_fn)

    assert len(merged) == 3
    assert merged[0]["payload"]["text"] == "Head section"
    assert merged[1]["payload"]["text"] == "orphan context"
    assert merged[2]["payload"]["text"] == "Tail section"
    assert merged[0]["payload"].get("auto_merged") is None
    assert merged[2]["payload"].get("auto_merged") is None
