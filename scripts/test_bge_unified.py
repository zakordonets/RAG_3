#!/usr/bin/env python3
"""
Тест unified BGE-M3 embeddings сервиса
"""
import sys
import os
sys.path.append(os.getcwd())

from app.services.bge_embeddings import (
    embed_unified,
    embed_dense_optimized,
    embed_sparse_optimized,
    embed_batch_optimized
)
from app.config import CONFIG
from loguru import logger
import time

def test_unified_embeddings():
    """Тестируем unified embeddings с разными бэкендами."""
    test_text = "Как настроить маршрутизацию чатов в edna Chat Center?"

    logger.info(f"Testing with backend: {CONFIG.embeddings_backend}")
    logger.info(f"Device: {CONFIG.embedding_device}")
    logger.info(f"Use sparse: {CONFIG.use_sparse}")

    # Test 1: Unified embeddings
    logger.info("=== Test 1: Unified Embeddings ===")
    start = time.time()
    try:
        result = embed_unified(
            test_text,
            return_dense=True,
            return_sparse=CONFIG.use_sparse,
            return_colbert=False,
            context="query"
        )
        duration = time.time() - start

        logger.info(f"✅ Unified embeddings completed in {duration:.3f}s")
        if result.get('dense_vecs'):
            logger.info(f"Dense vector shape: {len(result['dense_vecs'][0])}")
        if result.get('lexical_weights'):
            sparse_tokens = len(result['lexical_weights'][0])
            logger.info(f"Sparse tokens: {sparse_tokens}")

    except Exception as e:
        logger.error(f"❌ Unified embeddings failed: {e}")

    # Test 2: Dense only
    logger.info("=== Test 2: Dense Optimized ===")
    start = time.time()
    try:
        dense_vec = embed_dense_optimized(test_text)
        duration = time.time() - start
        logger.info(f"✅ Dense embedding completed in {duration:.3f}s, shape: {len(dense_vec)}")
    except Exception as e:
        logger.error(f"❌ Dense embedding failed: {e}")

    # Test 3: Sparse only (if enabled)
    if CONFIG.use_sparse:
        logger.info("=== Test 3: Sparse Optimized ===")
        start = time.time()
        try:
            sparse_result = embed_sparse_optimized(test_text)
            duration = time.time() - start
            logger.info(f"✅ Sparse embedding completed in {duration:.3f}s")
            logger.info(f"Sparse indices: {len(sparse_result.get('indices', []))}")
        except Exception as e:
            logger.error(f"❌ Sparse embedding failed: {e}")

    # Test 4: Batch processing
    logger.info("=== Test 4: Batch Processing ===")
    test_texts = [
        "Как настроить маршрутизацию чатов?",
        "Что такое веб-виджет в edna Chat Center?",
        "Как добавить оператора в группу?"
    ]

    start = time.time()
    try:
        batch_result = embed_batch_optimized(
            test_texts,
            return_dense=True,
            return_sparse=CONFIG.use_sparse,
            context="document"
        )
        duration = time.time() - start

        logger.info(f"✅ Batch processing completed in {duration:.3f}s")
        if batch_result.get('dense_vecs'):
            logger.info(f"Dense vectors: {len(batch_result['dense_vecs'])} x {len(batch_result['dense_vecs'][0])}")
        if batch_result.get('lexical_weights'):
            logger.info(f"Sparse results: {len(batch_result['lexical_weights'])} texts")

    except Exception as e:
        logger.error(f"❌ Batch processing failed: {e}")

def test_backend_comparison():
    """Сравниваем производительность разных бэкендов."""
    test_text = "Настройка маршрутизации чатов из веб-виджета на отдел продаж"

    logger.info("=== Backend Performance Comparison ===")

    backends = ["onnx", "bge", "hybrid"]
    for backend in backends:
        if backend == "bge" and not CONFIG.use_sparse:
            logger.info(f"Skipping {backend} - requires sparse support")
            continue

        logger.info(f"Testing backend: {backend}")

        # Временно меняем бэкенд
        original_backend = CONFIG.embeddings_backend
        CONFIG.__dict__['embeddings_backend'] = backend

        start = time.time()
        try:
            result = embed_unified(
                test_text,
                return_dense=True,
                return_sparse=True,
                context="query"
            )
            duration = time.time() - start
            logger.info(f"✅ {backend}: {duration:.3f}s")

        except Exception as e:
            logger.error(f"❌ {backend}: {e}")
        finally:
            # Восстанавливаем оригинальный бэкенд
            CONFIG.__dict__['embeddings_backend'] = original_backend

if __name__ == "__main__":
    logger.info("Starting BGE-M3 unified embeddings test")
    logger.info(f"Configuration:")
    logger.info(f"  EMBEDDINGS_BACKEND: {CONFIG.embeddings_backend}")
    logger.info(f"  EMBEDDING_DEVICE: {CONFIG.embedding_device}")
    logger.info(f"  ONNX_PROVIDER: {CONFIG.onnx_provider}")
    logger.info(f"  USE_SPARSE: {CONFIG.use_sparse}")
    logger.info(f"  MAX_LENGTH_QUERY: {CONFIG.embedding_max_length_query}")
    logger.info("")

    test_unified_embeddings()
    print()
    test_backend_comparison()

    logger.info("BGE-M3 unified embeddings test completed")
