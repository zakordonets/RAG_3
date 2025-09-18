#!/usr/bin/env python3
"""
Тест автоматического выбора оптимальной стратегии эмбеддингов
"""
import sys
import os
sys.path.append(os.getcwd())

from app.services.bge_embeddings import _get_optimal_backend_strategy
from app.config import CONFIG
from loguru import logger
import time

def test_system_detection():
    """Тестируем определение возможностей системы."""
    logger.info("=== System Capabilities Detection ===")

    # Check CUDA
    try:
        import torch
        has_cuda = torch.cuda.is_available()
        if has_cuda:
            logger.info("✅ CUDA available")
            logger.info(f"   Device: {torch.cuda.get_device_name()}")
            logger.info(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        else:
            logger.info("❌ CUDA not available")
    except ImportError:
        logger.info("❌ PyTorch not available")

    # Check DirectML
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if "DmlExecutionProvider" in providers:
            logger.info("✅ DirectML available")
            logger.info(f"   Available providers: {providers}")
        else:
            logger.info("❌ DirectML not available")
            logger.info(f"   Available providers: {providers}")
    except ImportError:
        logger.info("❌ ONNX Runtime not available")

    # Check BGE-M3 availability
    try:
        from FlagEmbedding import BGEM3FlagModel
        logger.info("✅ FlagEmbedding (BGE-M3) available")
    except ImportError:
        logger.info("❌ FlagEmbedding (BGE-M3) not available")

def test_strategy_selection():
    """Тестируем выбор оптимальной стратегии."""
    logger.info("=== Strategy Selection Test ===")

    # Test with current configuration
    logger.info(f"Current EMBEDDINGS_BACKEND: {CONFIG.embeddings_backend}")

    if CONFIG.embeddings_backend == "auto":
        optimal_strategy = _get_optimal_backend_strategy()
        logger.info(f"🎯 Optimal strategy selected: {optimal_strategy}")
    else:
        logger.info(f"🔧 Using explicit configuration: {CONFIG.embeddings_backend}")
        optimal_strategy = CONFIG.embeddings_backend

    return optimal_strategy

def test_strategy_performance():
    """Тестируем производительность выбранной стратегии."""
    from app.services.bge_embeddings import embed_unified

    optimal_strategy = test_strategy_selection()
    logger.info(f"=== Performance Test ({optimal_strategy}) ===")

    test_text = "Как настроить маршрутизацию чатов из веб-виджета на отдел продаж в edna Chat Center?"

    # Test unified embeddings
    start = time.time()
    try:
        result = embed_unified(
            test_text,
            return_dense=True,
            return_sparse=CONFIG.use_sparse,
            context="query"
        )
        duration = time.time() - start

        logger.info(f"✅ Unified embeddings completed in {duration:.3f}s")
        if result.get('dense_vecs'):
            logger.info(f"   Dense vector shape: {len(result['dense_vecs'][0])}")
        if result.get('lexical_weights') and result['lexical_weights'][0]:
            sparse_tokens = len(result['lexical_weights'][0])
            logger.info(f"   Sparse tokens: {sparse_tokens}")
        else:
            logger.info("   Sparse: not available or empty")

    except Exception as e:
        logger.error(f"❌ Strategy test failed: {e}")

def simulate_different_systems():
    """Симулируем разные системные конфигурации."""
    logger.info("=== System Configuration Simulation ===")

    # Simulate different scenarios
    scenarios = [
        ("NVIDIA GPU (CUDA)", "Should choose: bge"),
        ("AMD GPU (DirectML)", "Should choose: hybrid"),
        ("CPU only", "Should choose: onnx"),
    ]

    for scenario, expected in scenarios:
        logger.info(f"{scenario}: {expected}")

if __name__ == "__main__":
    logger.info("Starting automatic strategy selection test")
    logger.info(f"Configuration:")
    logger.info(f"  EMBEDDINGS_BACKEND: {CONFIG.embeddings_backend}")
    logger.info(f"  EMBEDDING_DEVICE: {CONFIG.embedding_device}")
    logger.info(f"  USE_SPARSE: {CONFIG.use_sparse}")
    logger.info("")

    test_system_detection()
    print()

    strategy = test_strategy_selection()
    print()

    test_strategy_performance()
    print()

    simulate_different_systems()

    logger.info("Automatic strategy selection test completed")
    logger.info(f"🎯 Final recommendation: Use EMBEDDINGS_BACKEND={strategy} for your system")
