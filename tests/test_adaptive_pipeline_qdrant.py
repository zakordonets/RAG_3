#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import socket
import time
import pytest

os.environ.setdefault("CHUNK_STRATEGY", "adaptive")
os.environ.setdefault("CRAWL_MAX_PAGES", "5")

from app.config import CONFIG
from app.services.indexing.optimized_pipeline import run_optimized_indexing


def _is_host_reachable(url: str) -> bool:
    try:
        # crude check: tcp connect to qdrant host:port from URL
        from urllib.parse import urlparse
        u = urlparse(url)
        host = u.hostname or "localhost"
        port = u.port or (443 if u.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except Exception:
        return False


@pytest.mark.integration
def test_adaptive_pipeline_qdrant_metadata_presence() -> None:
    if not _is_host_reachable(CONFIG.qdrant_url):
        pytest.skip("Qdrant is not reachable; skipping integration test")

    # Run indexing with adaptive strategy and small page limit
    result = run_optimized_indexing(source_name="edna_docs", max_pages=5, chunk_strategy=None)

    assert result.get("success") is True
    assert result.get("pages", 0) >= 1
    assert result.get("chunks", 0) >= 1

    # Allow a brief delay for upsert completion (usually synchronous, but to be safe)
    time.sleep(0.5)

    # Fetch recent points and verify adaptive metadata presence
    from qdrant_client import QdrantClient
    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key)

    points, _ = client.scroll(
        collection_name=CONFIG.qdrant_collection,
        limit=50,
        with_payload=True,
        with_vectors=False,
    )

    assert len(points) > 0
    adaptive_count = 0
    for p in points:
        payload = p.payload or {}
        if payload.get("adaptive_chunking") is True and payload.get("chunk_type") in {"short_document", "medium_document", "long_document"}:
            adaptive_count += 1

    # Expect at least one adaptive chunk from this run among recent points
    assert adaptive_count >= 1
