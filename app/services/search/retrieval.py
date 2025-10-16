from __future__ import annotations

from typing import Any, Callable, TypedDict
from copy import deepcopy
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, SparseVector, SearchParams, NamedSparseVector, FieldCondition, MatchValue
from app.config import CONFIG
from loguru import logger

# Optional tiktoken import
try:
    import tiktoken
    _tokenizer = tiktoken.get_encoding("cl100k_base")
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.debug("tiktoken not available, using heuristic token estimation (len//4)")

# Optional cachetools import
try:
    from cachetools import TTLCache
    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False
    logger.debug("cachetools not available, using simple dict cache (no TTL)")


# TypedDict для payload структур
class ChunkPayload(TypedDict, total=False):
    """Типизация payload для чанков документа."""
    doc_id: str
    chunk_index: int
    text: str
    chunk_id: str
    content_length: int
    auto_merged: bool
    merged_chunk_indices: list[int]
    merged_chunk_count: int
    chunk_span: dict[str, int]
    merged_chunk_ids: list[str]


class DocumentHit(TypedDict, total=False):
    """Типизация результата поиска."""
    id: str
    score: float
    payload: ChunkPayload
    rrf_score: float
    boosted_score: float


COLLECTION = CONFIG.qdrant_collection
EF_SEARCH = CONFIG.qdrant_hnsw_ef_search
RRF_K = CONFIG.rrf_k
W_DENSE = CONFIG.hybrid_dense_weight
W_SPARSE = CONFIG.hybrid_sparse_weight

client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

# Cache для документов - TTL если доступен cachetools, иначе простой dict
if CACHETOOLS_AVAILABLE:
    _doc_chunk_cache: Any = TTLCache(
        maxsize=CONFIG.retrieval_cache_maxsize,
        ttl=CONFIG.retrieval_cache_ttl
    )
    logger.info(f"Using TTL cache (maxsize={CONFIG.retrieval_cache_maxsize}, ttl={CONFIG.retrieval_cache_ttl}s)")
else:
    _doc_chunk_cache: Any = {}
    logger.warning("Using simple dict cache without TTL (memory may grow over time)")


def _make_filter(categories: list[str] | None) -> Filter | None:
    """Создает фильтр по категориям для разделения АРМ."""
    if not categories:
        return None
    return Filter(
        must=[FieldCondition(key="category", match=MatchValue(value=c)) for c in categories]
    )


def clear_chunk_cache():
    """Очистка кеша чанков документов."""
    global _doc_chunk_cache
    if CACHETOOLS_AVAILABLE:
        _doc_chunk_cache.clear()
    else:
        _doc_chunk_cache = {}
    logger.info("Document chunk cache cleared")


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


def hybrid_search(
    query_dense: list[float],
    query_sparse: dict,
    k: int,
    boosts: dict[str, float] | None = None,
    categories: list[str] | None = None,
    group_boosts: dict[str, float] | None = None,
) -> list[dict]:
    """Гибридный поиск в Qdrant с RRF и улучшенным ранжированием.
    - query_dense: плотный вектор BGE-M3
    - query_sparse: словарь с полями indices/values (BGE-M3 sparse)
    - k: количество результатов для возврата
    - boosts: словарь типа {page_type: factor}
    - categories: список категорий для фильтрации (например, ["АРМ_adm", "АРМ_sv"])
    """
    try:
        from loguru import logger
    except ImportError:
        import logging
        logger = logging.getLogger(__name__)

    boosts = boosts or {}
    normalized_group_boosts: dict[str, float] = {}
    if group_boosts:
        normalized_group_boosts = {
            str(key).lower().strip(): float(value)
            for key, value in group_boosts.items()
            if value
        }
    params = SearchParams(hnsw_ef=EF_SEARCH)
    qfilter = _make_filter(categories)

    # Увеличиваем k для лучшего recall в RRF
    k_dense = int(k * 2)
    k_sparse = int(k * 2)

    if hasattr(logger, 'debug'):
        logger.debug(f"Hybrid search: k={k}, k_dense={k_dense}, k_sparse={k_sparse}, categories={categories}, sparse_enabled={CONFIG.use_sparse}")

    # Dense search
    try:
        dense_res = client.search(
            collection_name=COLLECTION,
            query_vector=("dense", query_dense),
            with_payload=True,
            limit=k_dense,
            search_params=params,
            query_filter=qfilter,
        )
        if hasattr(logger, 'debug'):
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
                limit=k_sparse,
                search_params=params,
                query_filter=qfilter,
            )
            if hasattr(logger, 'debug'):
                logger.debug(f"Sparse search returned {len(sparse_res)} results")
        except Exception as e:
            logger.warning(f"Sparse search failed: {e}")
            sparse_res = []
    else:
        if hasattr(logger, 'debug'):
            logger.debug("Skipping sparse search: no indices/values or disabled")

    # RRF fusion
    try:
        fused = rrf_fuse(to_hit(dense_res), to_hit(sparse_res))
        if hasattr(logger, 'debug'):
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

        # 1.1 Boost по группам (dir_meta)
        if normalized_group_boosts:
            groups = payload.get("groups_path") or payload.get("group_labels") or []
            if isinstance(groups, str):
                groups = [groups]
            matched = False
            for group in groups:
                normalized_group = str(group).lower().strip()
                for key, factor in normalized_group_boosts.items():
                    if key and key in normalized_group:
                        s *= factor
                        matched = True
                        break
                if matched:
                    break

        # 2. Тип документа на основе URL структуры
        url = (payload.get("url") or payload.get("canonical_url") or payload.get("site_url") or "").lower()
        title = (payload.get("title") or "").lower()

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
        content_length = payload.get("content_length") or len(text)

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

    if hasattr(logger, 'debug'):
        logger.debug(f"Final results: {len(fused[:k])} items")
    return fused[:k]


def _estimate_tokens(text: str) -> int:
    """
    Оценка количества токенов в тексте.
    Использует tiktoken для точной оценки, если доступен,
    иначе fallback на эвристику len//4.
    """
    if not text:
        return 0

    if TIKTOKEN_AVAILABLE and CONFIG.retrieval_auto_merge_use_tiktoken:
        try:
            return len(_tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"tiktoken encoding failed: {e}, falling back to heuristic")

    # Fallback: эвристика для русского/английского текста
    tokens = len(text) // 4
    return tokens if tokens > 0 else 1


def _fetch_doc_chunks(doc_id: str, fetch_fn: Callable[[str], list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """
    Получает все чанки документа по doc_id.

    Args:
        doc_id: Идентификатор документа
        fetch_fn: Опциональная функция для инжекции (для тестирования)

    Returns:
        Список чанков документа, отсортированный по chunk_index
    """
    if not doc_id:
        return []

    if fetch_fn is not None:
        return fetch_fn(doc_id)

    if doc_id in _doc_chunk_cache:
        return _doc_chunk_cache[doc_id]

    qfilter = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
    offset = None
    collected: list[Any] = []

    try:
        while True:
            batch, offset = client.scroll(
                collection_name=COLLECTION,
                scroll_filter=qfilter,
                with_payload=True,
                with_vectors=False,
                limit=CONFIG.qdrant_scroll_batch_size,
                offset=offset,
            )
            if not batch:
                break
            collected.extend(batch)
            if offset is None:
                break
    except Exception as e:
        logger.warning(f"Failed to scroll chunks for doc_id={doc_id}: {e}")
        return []

    chunks: list[dict[str, Any]] = []
    for rec in collected:
        payload = getattr(rec, "payload", {}) or {}
        chunks.append({
            "id": getattr(rec, "id", None),
            "payload": payload
        })

    chunks.sort(key=lambda x: x["payload"].get("chunk_index", 0))
    _doc_chunk_cache[doc_id] = chunks
    return chunks


def _build_merged_doc(base_doc: dict, doc_chunks: list[dict[str, Any]], indices: list[int]) -> dict:
    merged = dict(base_doc)
    payload = deepcopy(base_doc.get("payload", {}) or {})

    texts = []
    chunk_indices = []
    chunk_ids = []

    for idx in indices:
        chunk_payload = doc_chunks[idx]["payload"] or {}
        text = chunk_payload.get("text", "")
        if text:
            texts.append(text.strip())
        chunk_index = chunk_payload.get("chunk_index")
        if chunk_index is not None:
            chunk_indices.append(chunk_index)
        chunk_id = chunk_payload.get("chunk_id")
        if chunk_id:
            chunk_ids.append(chunk_id)

    merged_text = "\n\n".join(t for t in texts if t).strip()
    if merged_text:
        payload["text"] = merged_text
        payload["content_length"] = len(merged_text)

    payload["auto_merged"] = True
    payload["merged_chunk_indices"] = chunk_indices
    payload["merged_chunk_count"] = len(indices)
    payload["chunk_span"] = {
        "start": chunk_indices[0] if chunk_indices else payload.get("chunk_index"),
        "end": chunk_indices[-1] if chunk_indices else payload.get("chunk_index"),
    }

    if chunk_ids:
        payload["merged_chunk_ids"] = chunk_ids

    merged["payload"] = payload
    return merged


def auto_merge_neighbors(hits: list[dict], max_window_tokens: int | None = None, fetch_fn: Callable[[str], list[dict[str, Any]]] | None = None) -> list[dict]:
    if not hits:
        return []

    if not CONFIG.retrieval_auto_merge_enabled:
        return hits

    max_tokens = max_window_tokens or CONFIG.retrieval_auto_merge_max_tokens
    if max_tokens <= 0:
        return hits

    doc_hits: dict[str, list[tuple[int, dict]]] = {}
    for doc in hits:
        payload = doc.get("payload", {}) or {}
        doc_id = payload.get("doc_id")
        chunk_index = payload.get("chunk_index")
        if doc_id is None or chunk_index is None:
            continue
        doc_hits.setdefault(doc_id, []).append((chunk_index, doc))

    window_map: dict[tuple[str, int], tuple[tuple[str, tuple[int, ...]], dict]] = {}

    for doc_id, items in doc_hits.items():
        doc_chunks = _fetch_doc_chunks(doc_id, fetch_fn)
        if not doc_chunks:
            for chunk_index, doc in items:
                key = (doc_id, (chunk_index,))
                window_map[(doc_id, chunk_index)] = (key, doc)
            continue

        positions = {
            chunk["payload"].get("chunk_index"): idx
            for idx, chunk in enumerate(doc_chunks)
        }
        covered: set[int] = set()

        for chunk_index, doc in sorted(items, key=lambda x: x[0]):
            pos = positions.get(chunk_index)
            if pos is None:
                key = (doc_id, (chunk_index,))
                window_map[(doc_id, chunk_index)] = (key, doc)
                continue

            if pos in covered and (doc_id, chunk_index) in window_map:
                continue

            start = end = pos
            tokens_used = _estimate_tokens(doc_chunks[pos]["payload"].get("text", ""))

            while True:
                expanded = False
                if start > 0 and (start - 1) not in covered:
                    candidate_text = doc_chunks[start - 1]["payload"].get("text", "")
                    candidate_tokens = _estimate_tokens(candidate_text)
                    if tokens_used + candidate_tokens <= max_tokens:
                        start -= 1
                        tokens_used += candidate_tokens
                        expanded = True
                if end + 1 < len(doc_chunks) and (end + 1) not in covered:
                    candidate_text = doc_chunks[end + 1]["payload"].get("text", "")
                    candidate_tokens = _estimate_tokens(candidate_text)
                    if tokens_used + candidate_tokens <= max_tokens:
                        end += 1
                        tokens_used += candidate_tokens
                        expanded = True
                if not expanded:
                    break

            indices = list(range(start, end + 1))
            covered.update(indices)

            merged_indices = [
                doc_chunks[i]["payload"].get("chunk_index")
                for i in indices
            ]

            if len(merged_indices) > 1:
                merged_doc = _build_merged_doc(doc, doc_chunks, indices)
            else:
                merged_doc = doc

            window_key = (doc_id, tuple(merged_indices))
            for idx in merged_indices:
                window_map[(doc_id, idx)] = (window_key, merged_doc)

    result: list[dict] = []
    seen_windows: set[tuple[str, tuple[int, ...]]] = set()

    for doc in hits:
        payload = doc.get("payload", {}) or {}
        doc_id = payload.get("doc_id")
        chunk_index = payload.get("chunk_index")

        if doc_id is None or chunk_index is None:
            result.append(doc)
            continue

        mapping = window_map.get((doc_id, chunk_index))
        if not mapping:
            window_key = (doc_id, (chunk_index,))
            if window_key in seen_windows:
                continue
            result.append(doc)
            seen_windows.add(window_key)
            continue

        window_key, merged_doc = mapping
        if window_key in seen_windows:
            continue
        result.append(merged_doc)
        seen_windows.add(window_key)

    return result
