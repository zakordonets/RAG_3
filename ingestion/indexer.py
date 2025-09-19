from __future__ import annotations

import time
from typing import Iterable
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector
from app.config import CONFIG
from app.services.embeddings import embed_dense_batch, embed_sparse_batch
from app.services.bge_embeddings import embed_batch_optimized
import uuid
from ingestion.chunker import text_hash


client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)


def upsert_chunks(chunks: list[dict]) -> int:
    """Optimized chunk indexing with unified BGE-M3 batch processing."""
    if not chunks:
        return 0

    points: list[PointStruct] = []
    texts = [c["text"] for c in chunks]

    # Import and determine optimal strategy
    from app.services.bge_embeddings import _get_optimal_backend_strategy
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
        # Legacy separate embedding generation
        logger.info(f"Using legacy embedding generation for {len(texts)} chunks")
        dense_vecs = embed_dense_batch(texts)
        sparse_results = embed_sparse_batch(texts) if CONFIG.use_sparse else [{"indices": [], "values": []}] * len(texts)

    for i, ch in enumerate(chunks):
        # deterministic id → UUID из sha256-хэша
        raw_hash = ch.get("id") or text_hash(ch["text"])  # 64-символьный hex
        hex32 = raw_hash.replace("-", "")[:32]
        pid = str(uuid.UUID(hex=hex32))
        payload = ch.get("payload", {})
        payload.update({"hash": pid})
        # Начинаем с dense вектора
        vector_dict = {"dense": dense_vecs[i]}

        # Добавляем sparse только если сервис включён и вернул непустые данные
        if CONFIG.use_sparse:
            try:
                if CONFIG.embeddings_backend in ["bge", "hybrid", "auto"]:
                    # BGE-M3 format: lexical_weights dict
                    lex_weights = sparse_results[i]
                    logger.debug(f"Chunk {i}: sparse_results type: {type(lex_weights)}, content: {lex_weights}")
                    if lex_weights and isinstance(lex_weights, dict):
                        indices = [int(k) for k in lex_weights.keys()]  # Ensure int indices
                        values = [float(lex_weights[k]) for k in lex_weights.keys()]
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
