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
    """Гибридный поиск в Qdrant с RRF и улучшенным ранжированием.
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

    # Универсальная система бустинга документов
    def boost_score(item: dict) -> float:
        s = item.get("rrf_score", item.get("score", 0.0))
        payload = item.get("payload", {})

        # 1. Metadata boost (существующий)
        page_type = (payload.get("page_type") or "").lower()
        if page_type and page_type in boosts:
            s *= float(boosts[page_type])

        # 2. Тип документа на основе URL структуры
        url = payload.get("url", "").lower()
        title = payload.get("title", "").lower()

        # Обзорная документация (высокий приоритет)
        if any(path in url for path in ["/start/", "/overview", "/introduction", "/what-is", "/about"]):
            s *= CONFIG.boost_overview_docs
        # FAQ и справочники (средний приоритет)
        elif any(path in url for path in ["/faq", "/guide", "/manual", "/help"]):
            s *= CONFIG.boost_faq_guides
        # Техническая документация (средний приоритет)
        elif any(path in url for path in ["/admin/", "/api/", "/sdk/", "/integration"]):
            s *= CONFIG.boost_technical_docs
        # Release notes и блоги (низкий приоритет для общих вопросов)
        elif any(path in url for path in ["/blog", "/release", "/version", "/changelog"]):
            s *= CONFIG.boost_release_notes

        # 3. Boost на основе заголовка
        if any(keyword in title for keyword in ["что такое", "обзор", "введение", "начало работы", "возможности"]):
            s *= CONFIG.boost_overview_docs
        elif any(keyword in title for keyword in ["настройка", "конфигурация", "установка"]):
            s *= CONFIG.boost_technical_docs

        # 4. Boost на основе полноты информации
        text = payload.get("text", "")
        content_length = payload.get("content_length", 0)

        # Документы средней длины (не слишком короткие, не слишком длинные)
        if 1000 <= content_length <= 5000:
            s *= CONFIG.boost_optimal_length
        elif content_length > 5000:
            s *= CONFIG.boost_technical_docs  # Длинные документы могут быть избыточными

        # 5. Boost для документов с хорошей структурой
        if text:
            text_lower = text.lower()
            # Документы с заголовками и списками (хорошо структурированные)
            if any(marker in text_lower for marker in ["##", "###", "•", "1.", "2.", "3."]):
                s *= CONFIG.boost_well_structured
            # Документы с примерами (практические)
            if any(marker in text_lower for marker in ["пример", "например", "как", "шаг"]):
                s *= CONFIG.boost_technical_docs

        # 6. Boost для документов из надежных источников
        source = payload.get("source", "").lower()
        if source in ["docs-site", "official-docs", "main-docs"]:
            s *= CONFIG.boost_reliable_source

        # 7. Понижение для дублирующихся документов (по URL паттерну)
        # Это поможет избежать повторения похожих документов
        url_parts = url.split("/")
        if len(url_parts) > 4:  # Глубоко вложенные документы
            s *= 0.95

        return s

    # Apply boosts and sort
    for it in fused:
        it["boosted_score"] = boost_score(it)

    fused.sort(key=lambda x: x["boosted_score"], reverse=True)

    logger.debug(f"Final results: {len(fused[:k])} items")
    return fused[:k]
