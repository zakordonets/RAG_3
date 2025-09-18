from __future__ import annotations

from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, SparseVector, SearchParams, NamedSparseVector
from app.config import CONFIG


COLLECTION = CONFIG.qdrant_collection
EF_SEARCH = CONFIG.qdrant_hnsw_ef_search
RRF_K = CONFIG.rrf_k
W_DENSE = CONFIG.hybrid_dense_weight
W_SPARSE = CONFIG.hybrid_sparse_weight

client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)


def rrf_fuse(dense_hits: list[dict], sparse_hits: list[dict]) -> list[dict]:
    """Reciprocal Rank Fusion для объединения dense и sparse результатов.
    Весовые коэффициенты берутся из CONFIG (HYBRID_DENSE_WEIGHT / HYBRID_SPARSE_WEIGHT).
    """
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for rank, h in enumerate(dense_hits, start=1):
        pid = h["id"]
        items[pid] = h
        scores[pid] = scores.get(pid, 0.0) + W_DENSE * (1.0 / (RRF_K + rank))
    for rank, h in enumerate(sparse_hits, start=1):
        pid = h["id"]
        items[pid] = items.get(pid, h)
        scores[pid] = scores.get(pid, 0.0) + W_SPARSE * (1.0 / (RRF_K + rank))
    fused = [
        {**items[pid], "rrf_score": s}
        for pid, s in scores.items()
    ]
    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused


def to_hit(res) -> list[dict]:
    out = []
    for r in res:
        out.append({
            "id": str(r.id),
            "score": float(r.score or 0.0),
            "payload": r.payload or {},
        })
    return out


def hybrid_search(query_dense: list[float], query_sparse: dict, k: int, boosts: dict[str, float] | None = None) -> list[dict]:
    """Гибридный поиск в Qdrant с RRF и простым metadata-boost.
    - query_dense: плотный вектор BGE-M3
    - query_sparse: словарь с полями indices/values (BGE-M3 sparse)
    - boosts: словарь типа {page_type: factor}
    """
    from loguru import logger

    boosts = boosts or {}
    params = SearchParams(hnsw_ef=EF_SEARCH)

    # Dense search
    try:
        dense_res = client.search(
            collection_name=COLLECTION,
            query_vector=("dense", query_dense),
            with_payload=True,
            limit=k,
            search_params=params,
        )
        logger.debug(f"Dense search returned {len(dense_res)} results")
    except Exception as e:
        logger.error(f"Dense search failed: {e}")
        dense_res = []

    # Sparse search - правильная реализация
    sparse_res = []
    indices = list((query_sparse or {}).get("indices", []))
    values = list((query_sparse or {}).get("values", []))

    if indices and values and CONFIG.use_sparse:
        try:
            # Создаем правильный NamedSparseVector
            sparse_vector = NamedSparseVector(
                name="sparse",
                vector=SparseVector(indices=indices, values=values)
            )
            sparse_res = client.search(
                collection_name=COLLECTION,
                query_vector=sparse_vector,
                with_payload=True,
                limit=k,
                search_params=params,
            )
            logger.debug(f"Sparse search returned {len(sparse_res)} results")
        except Exception as e:
            logger.warning(f"Sparse search failed: {e}")
            sparse_res = []
    else:
        logger.debug("Skipping sparse search: no indices/values or disabled")

    # RRF fusion
    try:
        fused = rrf_fuse(to_hit(dense_res), to_hit(sparse_res))
        logger.debug(f"RRF fusion returned {len(fused)} results")
    except Exception as e:
        logger.error(f"RRF fusion failed: {e}")
        # Fallback to dense only
        fused = to_hit(dense_res)

    # Metadata boost
    def boost_score(item: dict) -> float:
        s = item.get("rrf_score", item.get("score", 0.0))
        page_type = (item.get("payload", {}).get("page_type") or "").lower()
        if page_type and page_type in boosts:
            s *= float(boosts[page_type])
        return s

    # Apply boosts and sort
    for it in fused:
        it["boosted_score"] = boost_score(it)

    fused.sort(key=lambda x: x["boosted_score"], reverse=True)

    logger.debug(f"Final results: {len(fused[:k])} items")
    return fused[:k]
