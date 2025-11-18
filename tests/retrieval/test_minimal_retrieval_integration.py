from __future__ import annotations

import uuid
import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import CONFIG
from app.retrieval import retrieval


pytestmark = pytest.mark.integration


def _basis_vector(dimension: int, index: int) -> list[float]:
    vector = [0.0] * dimension
    vector[index] = 1.0
    return vector


@pytest.mark.integration
def test_minimal_qdrant_retrieval_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)
    collection_name = f"test_retrieval_{uuid.uuid4().hex[:8]}"
    dimension = CONFIG.embedding_dim

    client.recreate_collection(
        collection_name=collection_name,
        vectors_config={"dense": VectorParams(size=dimension, distance=Distance.COSINE)},
    )

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector={"dense": _basis_vector(dimension, idx)},
            payload={
                "doc_id": f"doc-{idx}",
                "chunk_index": idx,
                "text": f"Sample content #{idx}",
                "content_length": 18,
                "source": "test-suite",
            },
        )
        for idx in range(3)
    ]
    client.upsert(collection_name=collection_name, points=points)

    monkeypatch.setattr(retrieval, "client", client)
    monkeypatch.setattr(retrieval, "COLLECTION", collection_name)

    query_vector = _basis_vector(dimension, 0)
    results = None
    try:
        results = retrieval.hybrid_search(query_vector, {"indices": [], "values": []}, k=2)
        assert results, "Hybrid search should return at least one result"
        top_hit = results[0]
        assert "id" in top_hit and "score" in top_hit
        payload = top_hit.get("payload") or {}
        assert payload.get("doc_id") == "doc-0"
        assert isinstance(payload.get("chunk_index"), int)
        assert "text" in payload and payload["text"].startswith("Sample content")
    finally:
        try:
            client.delete_collection(collection_name=collection_name)
        except Exception:
            pass
