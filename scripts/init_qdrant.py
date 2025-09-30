from __future__ import annotations

import os
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    HnswConfigDiff,
    OptimizersConfigDiff,
)


def main() -> None:
    from app.config import CONFIG

    url = CONFIG.qdrant_url
    api_key = CONFIG.qdrant_api_key or None
    collection = CONFIG.qdrant_collection
    dim = CONFIG.embedding_dim

    hnsw_m = CONFIG.qdrant_hnsw_m
    ef_construct = CONFIG.qdrant_hnsw_ef_construct
    ef_search = CONFIG.qdrant_hnsw_ef_search
    full_scan_threshold = CONFIG.qdrant_hnsw_full_scan_threshold

    client = QdrantClient(url=url, api_key=api_key)
    exists = client.collection_exists(collection)
    if not exists:
        client.recreate_collection(
            collection_name=collection,
            vectors_config={"dense": VectorParams(size=dim, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
            hnsw_config=HnswConfigDiff(
                m=hnsw_m,
                ef_construct=ef_construct,
                full_scan_threshold=full_scan_threshold,
            ),
            optimizers_config=OptimizersConfigDiff(default_segment_number=2),
        )
    # tune ef_search
    client.update_collection(collection, hnsw_config=HnswConfigDiff(ef_construct=ef_construct))
    print(f"Collection '{collection}' ready at {url}")


if __name__ == "__main__":
    main()


