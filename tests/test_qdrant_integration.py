from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch
import uuid

import pytest

from ingestion.indexer import create_payload_indexes, upsert_chunks
from ingestion import run as ingestion_run


def test_create_payload_indexes():
    """Тест создания индексов payload"""
    with patch('ingestion.indexer.client') as mock_client:
        mock_client.create_payload_index.return_value = None

        create_payload_indexes("test_collection")

        assert mock_client.create_payload_index.call_count >= 5  # Минимум 5 индексов
        called_fields = [call[1]['field_name'] for call in mock_client.create_payload_index.call_args_list]
        assert {"category", "groups_path", "title", "source", "content_type"} <= set(called_fields)


def test_upsert_chunks_with_chunk_id():
    """Тест upsert_chunks с использованием chunk_id из payload"""
    with patch('ingestion.indexer.client') as mock_client, \
         patch('ingestion.indexer.embed_batch_optimized') as mock_embed:

        mock_client.upsert.return_value = None
        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024, [0.2] * 1024],
            'lexical_weights': [{}, {}]
        }

        chunks = [
            {
                "text": "Тестовый текст 1",
                "payload": {
                    "chunk_id": "0123456789abcdef0123456789abcdef#0",
                    "title": "Тест 1",
                    "category": "АРМ_adm",
                    "source": "docusaurus"
                }
            },
            {
                "text": "Тестовый текст 2",
                "payload": {
                    "chunk_id": "fedcba9876543210fedcba9876543210#1",
                    "title": "Тест 2",
                    "category": "АРМ_adm",
                    "source": "docusaurus"
                }
            }
        ]

        result = upsert_chunks(chunks)

        assert result == 2
        mock_client.upsert.assert_called_once()
        points = mock_client.upsert.call_args.kwargs['points']
        assert len(points) == 2
        uuid.UUID(points[0].id)
        uuid.UUID(points[1].id)
        assert points[0].id != points[1].id  # UUID формируется из chunk_id


def test_upsert_chunks_fallback_id():
    """Тест upsert_chunks с fallback ID когда нет chunk_id"""
    with patch('ingestion.indexer.client') as mock_client, \
         patch('ingestion.indexer.embed_batch_optimized') as mock_embed, \
         patch('ingestion.indexer.text_hash') as mock_hash, \
         patch('ingestion.indexer.uuid') as mock_uuid:

        mock_client.upsert.return_value = None
        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024],
            'lexical_weights': [{}]
        }
        mock_hash.return_value = "test_hash_123456789012345678901234567890123456789012345678901234567890"
        mock_uuid.UUID.return_value = "fallback-uuid-123"

        chunks = [
            {
                "text": "Тестовый текст",
                "payload": {
                    "title": "Тест",
                    "category": "АРМ_adm"
                }
            }
        ]

        result = upsert_chunks(chunks)

        assert result == 1
        mock_client.upsert.assert_called_once()
        points = mock_client.upsert.call_args.kwargs['points']
        assert len(points) == 1
        assert points[0].id == "fallback-uuid-123"


def test_run_unified_indexing_basic(monkeypatch):
    """Проверяем, что run_unified_indexing корректно обрабатывает результат DAG."""

    class FakeStep:
        def __init__(self, name: str):
            self._name = name

        def get_step_name(self) -> str:
            return self._name

    class FakeWriter(FakeStep):
        def __init__(self):
            super().__init__("qdrant_writer")
            self.stats = {"total_chunks": 3, "processed_chunks": 3, "failed_chunks": 0}

        def ensure_collection(self):
            self.ensure_called = True

    class FakeDag:
        def __init__(self):
            self.steps = [FakeStep("parser"), FakeStep("normalizer"), FakeWriter()]

        def run(self, documents):
            list(documents)
            return {"processed_docs": 1, "total_docs": 1, "failed_docs": 0, "total_time": 0.1}

    class FakeAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def iter_documents(self):
            yield object()

    @contextmanager
    def fake_state_manager():
        yield {}

    monkeypatch.setattr(ingestion_run, "DocusaurusAdapter", FakeAdapter)
    monkeypatch.setattr(ingestion_run, "create_docusaurus_dag", lambda config: FakeDag())
    monkeypatch.setattr(ingestion_run, "get_state_manager", fake_state_manager)

    result = ingestion_run.run_unified_indexing(
        source_type="docusaurus",
        config={"docs_root": "/tmp/docs", "collection_name": "test"},
    )

    assert result["success"] is True
    assert result["stats"]["processed_docs"] == 1
    assert result["stats"]["failed_docs"] == 0


def test_run_unified_indexing_invalid_source(monkeypatch):
    """Неподдерживаемый тип источника приводит к ValueError."""
    result = ingestion_run.run_unified_indexing("unsupported", {"docs_root": "/tmp"})
    assert result["success"] is False
    assert "unsupported" in result.get("error", "")
