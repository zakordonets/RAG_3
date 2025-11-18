from __future__ import annotations

"""
Гибридный поиск по коллекции Qdrant:
- параллельный dense + sparse поиск;
- RRF-фьюжн результатов;
- пост-boosting на основе метаданных и тематического роутинга;
- лёгкий кэш чанков документов.
"""

from typing import Any, Callable, TypedDict
from copy import deepcopy
import importlib
import importlib.util

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, SparseVector, SearchParams, NamedSparseVector, FieldCondition, MatchValue
from loguru import logger

from app.config import CONFIG
from app.config.boosting_config import get_boosting_config
from app.retrieval.boosting import boost_hits

# Optional tiktoken import (для оценки токенов при auto-merge)
try:
    import tiktoken
    _tokenizer = tiktoken.get_encoding("cl100k_base")
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.debug("tiktoken not available, using heuristic token estimation (len//4)")

# Optional cachetools import (lazy, чтобы не делать зависимость обязательной)
_cachetools_module = importlib.util.find_spec("cachetools")
if _cachetools_module is None:
    TTLCache = None
    CACHETOOLS_AVAILABLE = False
    logger.debug("cachetools not available, using simple dict cache (no TTL)")
else:
    cachetools = importlib.import_module("cachetools")
    TTLCache = getattr(cachetools, "TTLCache", None)
    CACHETOOLS_AVAILABLE = TTLCache is not None
    if not CACHETOOLS_AVAILABLE:
        logger.debug("cachetools module found but TTLCache missing, falling back to dict cache")


# TypedDict для payload структур, которые возвращаются из поиска
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
    """Типизация результата поиска (один документ/чанк в выдаче)."""
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

# Кэш для чанков документов — TTL, если доступен cachetools, иначе простой dict
if CACHETOOLS_AVAILABLE:
    _doc_chunk_cache: Any = TTLCache(
        maxsize=CONFIG.retrieval_cache_maxsize,
        ttl=CONFIG.retrieval_cache_ttl
    )
    logger.info(f"Using TTL cache (maxsize={CONFIG.retrieval_cache_maxsize}, ttl={CONFIG.retrieval_cache_ttl}s)")
else:
    _doc_chunk_cache: Any = {}
    logger.warning("Using simple dict cache without TTL (memory may grow over time)")


def clear_chunk_cache():
    """Полностью очищает кэш чанков документов (для админки/тестов)."""
    global _doc_chunk_cache
    if CACHETOOLS_AVAILABLE:
        _doc_chunk_cache.clear()
    else:
        _doc_chunk_cache = {}
    logger.info("Document chunk cache cleared")


def rrf_fuse(dense_hits: list[dict], sparse_hits: list[dict]) -> list[dict]:
    """
    Reciprocal Rank Fusion для объединения dense и sparse результатов.

    Используется классическая формула 1 / (RRF_K + rank) с разными весами
    для dense и sparse частей (из CONFIG.hybrid_dense_weight / hybrid_sparse_weight).
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
    """Нормализует элементы ответа Qdrant в внутренний формат hit-словаря."""
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
    group_boosts: dict[str, float] | None = None,
    routing_result: dict | None = None,
    metadata_filter: Filter | None = None,
) -> list[dict]:
    """
    Гибридный поиск в Qdrant с RRF и boosting.

    Пайплайн:
    1. Dense-поиск по вектору "dense" (BGE-M3).
    2. Sparse-поиск по вектору "sparse" (BGE-M3 sparse), если включён.
    3. RRF-фьюжн двух списков результатов.
    4. Применение boosting правил (boosting.yaml) + групповые/тематические бусты.

    Параметры:
    - query_dense: плотный вектор BGE-M3 для запроса;
    - query_sparse: словарь с полями indices/values (BGE-M3 sparse);
    - k: сколько результатов вернуть после boosting;
    - boosts: временные бусты по page_type для конкретного запроса;
    - group_boosts: бусты по группам (ARM, API и т.п.), приходит из CONFIG.group_boost_synonyms;
    - routing_result: результат тематического роутера (домен/секция/платформа);
    - metadata_filter: предрасчитанный фильтр по метаданным от оркестратора.
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
    qfilter = metadata_filter

    # Увеличиваем k для лучшего recall в RRF
    k_dense = int(k * 2)
    k_sparse = int(k * 2)

    if hasattr(logger, 'debug'):
        logger.debug(f"Hybrid search: k={k}, k_dense={k_dense}, k_sparse={k_sparse}, sparse_enabled={CONFIG.use_sparse}")

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

    boosting_cfg = get_boosting_config()
    boost_context = {
        "boosts": boosts or {},
        "group_boosts": normalized_group_boosts,
    }
    if routing_result:
        boost_context["routing_result"] = routing_result
    fused = boost_hits(fused, boosting_cfg, boost_context)

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
    """
    Строит новый документ на основе базового hit'а и списка индексов чанков.

    - склеивает тексты выбранных чанков в один;
    - пересчитывает длину контента;
    - добавляет служебные поля auto_merged / merged_chunk_indices / chunk_span / merged_chunk_ids.
    """
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


def _build_windows_for_doc(
    doc_id: str,
    items: list[tuple[int, dict]],
    max_tokens: int,
    fetch_fn: Callable[[str], list[dict[str, Any]]] | None = None,
) -> dict[tuple[str, int], tuple[tuple[str, tuple[int, ...]], dict]]:
    """
    Строит окна для одного документа и возвращает их отображение:
    (doc_id, chunk_index) -> (window_key, merged_doc).
    """
    windows: dict[tuple[str, int], tuple[tuple[str, tuple[int, ...]], dict]] = {}

    doc_chunks = _fetch_doc_chunks(doc_id, fetch_fn)
    if not doc_chunks:
        # Нет информации о чанках документа — каждый hit остаётся сам по себе
        for chunk_index, doc in items:
            key = (doc_id, (chunk_index,))
            windows[(doc_id, chunk_index)] = (key, doc)
        return windows

    # Быстрый доступ от chunk_index к позиции в списке чанков
    positions = {
        chunk["payload"].get("chunk_index"): idx
        for idx, chunk in enumerate(doc_chunks)
    }
    covered: set[int] = set()

    for chunk_index, doc in sorted(items, key=lambda x: x[0]):
        pos = positions.get(chunk_index)
        if pos is None:
            key = (doc_id, (chunk_index,))
            windows[(doc_id, chunk_index)] = (key, doc)
            continue

        # Чанк уже покрыт ранее построенным окном
        if pos in covered and (doc_id, chunk_index) in windows:
            continue

        start = end = pos
        tokens_used = _estimate_tokens(doc_chunks[pos]["payload"].get("text", ""))

        # Жадно расширяем окно влево/вправо, пока укладываемся в лимит токенов
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
            windows[(doc_id, idx)] = (window_key, merged_doc)

    return windows


def auto_merge_neighbors(hits: list[dict], max_window_tokens: int | None = None, fetch_fn: Callable[[str], list[dict[str, Any]]] | None = None) -> list[dict]:
    """
    Автоматически объединяет соседние чанки одного документа в более крупные окна.

    Алгоритм:
    1. Группирует hits по doc_id + chunk_index.
    2. Для каждого документа подтягивает все чанки и строит «окно» вокруг выбранного chunk_index,
       расширяя его влево/вправо пока суммарное число токенов (по _estimate_tokens) не превысит лимит.
    3. Если в окно попало больше одного чанка, создаёт объединённый документ через _build_merged_doc.
    4. В итоговой выдаче каждый window (набор чанков) представлен одним hit'ом; остальные скрываются.

    max_window_tokens:
        жёсткий лимит токенов на одно окно; по умолчанию берётся из CONFIG.retrieval_auto_merge_max_tokens.
    fetch_fn:
        опциональная функция для подмены источника чанков (используется в тестах).
    """
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
        doc_windows = _build_windows_for_doc(doc_id, items, max_tokens, fetch_fn)
        window_map.update(doc_windows)

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
