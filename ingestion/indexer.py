from __future__ import annotations

import time
from typing import Iterable
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector
from app.config import CONFIG
from app.services.core.embeddings import embed_batch_optimized
import uuid
from ingestion.chunking import text_hash


client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)


def create_payload_indexes(collection_name: str = None) -> None:
    """Создает индексы для payload полей согласно CODEX_BRIEF.md."""
    if collection_name is None:
        collection_name = CONFIG.qdrant_collection

    try:
        # Создаем индексы для ключевых полей
        indexes = [
            # category (keyword) - для фильтрации по категориям
            {
                "field_name": "category",
                "field_schema": "keyword"
            },
            # groups_path (keyword[]) - для фильтрации по группам
            {
                "field_name": "groups_path",
                "field_schema": "keyword"
            },
            # title (fulltext) - для полнотекстового поиска по заголовкам
            {
                "field_name": "title",
                "field_schema": "text"
            },
            # source (keyword) - для фильтрации по источнику
            {
                "field_name": "source",
                "field_schema": "keyword"
            },
            # content_type (keyword) - для фильтрации по типу контента
            {
                "field_name": "content_type",
                "field_schema": "keyword"
            },
        ]

        for index in indexes:
            try:
                # Используем прямой вызов API для создания индекса
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=index["field_name"],
                    field_schema=index["field_schema"]
                )
                logger.info(f"Создан индекс для поля: {index['field_name']}")
            except Exception as e:
                logger.warning(f"Не удалось создать индекс для {index['field_name']}: {e}")

    except Exception as e:
        logger.error(f"Ошибка создания индексов payload: {e}")


def upsert_chunks(chunks: list[dict]) -> int:
    """Optimized chunk indexing with unified BGE-M3 batch processing."""
    if not chunks:
        return 0

    points: list[PointStruct] = []
    texts = [c["text"] for c in chunks]

    # Батчинг: обрабатываем чанки батчами 8-32 (уменьшено для экономии памяти)
    batch_size = min(32, max(8, len(chunks)))
    total_processed = 0

    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_processed = _process_batch(batch_chunks)
        total_processed += batch_processed
        logger.info(f"Обработан батч {i//batch_size + 1}: {batch_processed} чанков")

    return total_processed


def _process_batch(chunks: list[dict]) -> int:
    """Обрабатывает один батч чанков."""
    if not chunks:
        return 0

    points: list[PointStruct] = []
    texts = [c["text"] for c in chunks]

    # Import and determine optimal strategy
    from app.services.core.embeddings import _get_optimal_backend_strategy
    optimal_backend = _get_optimal_backend_strategy()

    # Choose embedding strategy based on optimal backend
    if optimal_backend in ["bge", "hybrid"]:
        # Use unified BGE-M3 batch processing
        logger.info(f"Using {optimal_backend} backend for batch indexing of {len(texts)} chunks")
        embedding_results = embed_batch_optimized(
            texts,
            max_length=CONFIG.embedding_max_length_doc,
            return_dense=True,
            return_sparse=CONFIG.use_sparse,
            context="document"
        )
        dense_vecs = embedding_results.get('dense_vecs', [[0.0] * 1024] * len(texts))
        sparse_results = embedding_results.get('lexical_weights', [{}] * len(texts))
    else:
        # Fallback for unsupported backends
        logger.warning(f"Unsupported backend '{optimal_backend}', using fallback")
        dense_vecs = [[0.0] * 1024] * len(texts)
        sparse_results = [{"indices": [], "values": []}] * len(texts)

    def _sanitize_payload(payload: dict) -> dict:
        """Remove heavy or redundant fields from payload before indexing."""
        if not isinstance(payload, dict):
            return {}
        cleaned = dict(payload)
        # Drop potentially large or duplicate fields
        for k in ["content", "html", "text", "raw", "raw_content"]:
            if k in cleaned:
                cleaned.pop(k, None)
        # Remove None values
        cleaned = {k: v for k, v in cleaned.items() if v is not None}
        return cleaned

    for i, ch in enumerate(chunks):
        # Используем chunk_id из payload если есть, иначе создаем детерминистический ID
        payload = ch.get("payload", {})
        chunk_id = payload.get("chunk_id")

        if chunk_id:
            # Преобразуем chunk_id в UUID для Qdrant
            # chunk_id имеет формат "sha1_hash#index", нужно создать UUID из sha1_hash
            if "#" in chunk_id:
                base_hash = chunk_id.split("#")[0]
            else:
                base_hash = chunk_id

            # Создаем UUID из хеша (берем первые 32 символа)
            hex32 = base_hash.replace("-", "")[:32]
            pid = str(uuid.UUID(hex=hex32))
        else:
            # Fallback: создаем детерминистический ID из текста
            raw_hash = ch.get("id") or text_hash(ch["text"])  # 64-символьный hex
            hex32 = raw_hash.replace("-", "")[:32]
            pid = str(uuid.UUID(hex=hex32))

        payload = _sanitize_payload(payload)
        payload.update({"hash": pid})
        # Начинаем с dense вектора
        vector_dict = {"dense": dense_vecs[i]}

        # Добавляем sparse только если сервис включён и вернул непустые данные
        if CONFIG.use_sparse:
            try:
                if CONFIG.embeddings_backend in ["bge", "hybrid", "auto"]:
                    # BGE-M3 format: lexical_weights dict - OPTIMIZED
                    lex_weights = sparse_results[i]
                    logger.debug(f"Chunk {i}: sparse_results type: {type(lex_weights)}, content: {lex_weights}")
                    if lex_weights and isinstance(lex_weights, dict):
                        # Оптимизированная конверсия - избегаем дублирования доступа к ключам
                        items = list(lex_weights.items())
                        # Сортировка по весу для лучшего сжатия и производительности
                        sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
                        indices = [int(k) for k, v in sorted_items]
                        values = [float(v) for k, v in sorted_items]
                        logger.debug(f"Chunk {i}: indices={len(indices)}, values={len(values)}")
                        if indices:  # Only add if non-empty
                            # Добавляем sparse вектор в тот же dict
                            vector_dict["sparse"] = SparseVector(indices=indices, values=values)
                            logger.debug(f"Chunk {i}: Added sparse vector with {len(indices)} indices")
                        else:
                            logger.debug(f"Chunk {i}: No indices, skipping sparse vector")
                    else:
                        logger.debug(f"Chunk {i}: lex_weights is empty or not dict: {lex_weights}")
                else:
                    # Legacy format: dict with indices/values
                    sv = sparse_results[i]
                    if isinstance(sv, dict) and ("indices" in sv and "values" in sv) and sv.get("indices"):
                        vector_dict["sparse"] = SparseVector(indices=sv["indices"], values=[float(v) for v in sv["values"]])
            except Exception as e:
                logger.warning(f"Failed to process sparse vector for chunk {i}: {e}")
                pass

        point_kwargs = {
            "id": pid,
            "vector": vector_dict,
            "payload": payload,
        }
        points.append(PointStruct(**point_kwargs))

    if not points:
        return 0
    client.upsert(collection_name=CONFIG.qdrant_collection, points=points)
    return len(points)
