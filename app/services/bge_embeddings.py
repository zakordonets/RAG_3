"""
BGE-M3 Unified Embeddings Service

Provides unified dense and sparse embeddings generation using BAAI/bge-m3 model.
Supports CPU, CUDA, and DirectML (Windows/AMD) backends with automatic fallbacks.
"""
from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional, Any, Union

from loguru import logger

from app.config import CONFIG
from app.caching import cache_embedding

# Windows compatibility for HuggingFace Hub
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

# Global model instances
_bge_model = None
_bge_lock = threading.Lock()

# Import fallbacks for different backends
_onnx_embedder = None
_onnx_tokenizer = None
_onnx_lock = threading.Lock()


def _determine_device() -> str:
    """Determine optimal device based on configuration and availability."""
    device_config = CONFIG.embedding_device

    if device_config == "auto":
        # Auto-detection logic
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

        # Check for DirectML availability (Windows/AMD)
        try:
            import onnxruntime as ort
            if "DmlExecutionProvider" in ort.get_available_providers():
                logger.info("DirectML detected, but BGE-M3 doesn't support DirectML directly. Using CPU for BGE-M3.")
                return "cpu"
        except ImportError:
            pass

        return "cpu"

    # Explicit device configuration
    if device_config in ["cuda", "cpu"]:
        return device_config
    elif device_config == "directml":
        logger.warning("DirectML not directly supported by BGE-M3. Falling back to CPU.")
        return "cpu"
    else:
        logger.warning(f"Unknown device '{device_config}'. Falling back to CPU.")
        return "cpu"


def _get_optimal_backend_strategy() -> str:
    """
    Determine optimal backend strategy based on system capabilities.

    Returns:
        Recommended backend: 'onnx', 'bge', or 'hybrid'
    """
    # If user explicitly set backend, respect their choice
    if CONFIG.embeddings_backend != "auto":
        return CONFIG.embeddings_backend

    # Auto-detection logic for optimal strategy
    has_cuda = False
    has_directml = False

    # Check CUDA availability
    try:
        import torch
        has_cuda = torch.cuda.is_available()
        if has_cuda:
            logger.info("CUDA detected - BGE-M3 can use GPU acceleration")
    except ImportError:
        pass

    # Check DirectML availability
    try:
        import onnxruntime as ort
        has_directml = "DmlExecutionProvider" in ort.get_available_providers()
        if has_directml:
            logger.info("DirectML detected - ONNX can use GPU acceleration")
    except ImportError:
        pass

    # Determine optimal strategy
    if has_cuda:
        # NVIDIA GPU: BGE-M3 can use CUDA directly
        logger.info("Optimal strategy: BGE backend (CUDA acceleration)")
        return "bge"
    elif has_directml:
        # AMD GPU on Windows: Hybrid approach (ONNX+DML for dense, BGE+CPU for sparse)
        logger.info("Optimal strategy: Hybrid backend (DirectML + CPU)")
        return "hybrid"
    else:
        # CPU only: Use ONNX for consistency
        logger.info("Optimal strategy: ONNX backend (CPU only)")
        return "onnx"


def _get_bge_model():
    """Get singleton BGE-M3 model with optimized settings."""
    global _bge_model
    if _bge_model is None:
        with _bge_lock:
            if _bge_model is None:
                try:
                    from FlagEmbedding import BGEM3FlagModel

                    device = _determine_device()
                    logger.info(f"Loading BGE-M3 model on device: {device}")

                    _bge_model = BGEM3FlagModel(
                        'BAAI/bge-m3',
                        use_fp16=CONFIG.embedding_use_fp16 and device != "cpu",  # FP16 only on GPU
                        device=device,
                        normalize_embeddings=CONFIG.embedding_normalize,
                        query_instruction_for_retrieval=None,  # Not needed for documentation
                        passage_instruction_for_retrieval=None
                    )
                    logger.info(f"BGE-M3 model loaded successfully on {device}")

                except Exception as e:
                    logger.error(f"Failed to load BGE-M3 model: {e}")
                    logger.info("BGE-M3 model will be unavailable. Fallback to ONNX if configured.")
                    _bge_model = None

    return _bge_model


def _get_onnx_embedder():
    """Get ONNX embedder as fallback (from existing implementation)."""
    global _onnx_embedder, _onnx_tokenizer
    if _onnx_embedder is None:
        with _onnx_lock:
            if _onnx_embedder is None:
                try:
                    from transformers import AutoTokenizer
                    import onnxruntime as ort
                    from onnxruntime.capi.onnxruntime_inference_collection import InferenceSession
                    import numpy as np

                    model_path = "models/onnx/bge-m3"
                    if not os.path.exists(os.path.join(model_path, "model.onnx")):
                        logger.error(f"ONNX model not found at {model_path}. Run export script first.")
                        return None, None

                    logger.info(f"Loading ONNX embedder from {model_path}...")

                    # Determine ONNX Runtime provider based on config
                    providers = []
                    if CONFIG.onnx_provider == "dml" or (CONFIG.onnx_provider == "auto" and "DmlExecutionProvider" in ort.get_available_providers()):
                        providers.append("DmlExecutionProvider")
                        logger.info("Using DmlExecutionProvider for ONNX embeddings.")
                    providers.append("CPUExecutionProvider")  # Always add CPU as fallback

                    _onnx_embedder = InferenceSession(
                        os.path.join(model_path, "model.onnx"),
                        providers=providers
                    )
                    _onnx_tokenizer = AutoTokenizer.from_pretrained(model_path)
                    logger.info("ONNX embedder loaded successfully.")

                except Exception as e:
                    logger.error(f"Failed to load ONNX embedder: {e}")
                    _onnx_embedder = None
                    _onnx_tokenizer = None

    return _onnx_embedder, _onnx_tokenizer


def get_optimal_max_length(text: str, context: str = "query") -> int:
    """Automatically choose optimal max_length based on text and context."""
    text_len = len(text)

    if context == "query":
        if text_len < 100:
            return 256    # Very short queries
        elif text_len < 300:
            return 512   # Normal queries
        else:
            return 1024  # Long queries

    elif context == "document":
        if text_len < 500:
            return 512    # Short chunks
        elif text_len < 2000:
            return 1024  # Medium chunks
        else:
            return 2048  # Long chunks

    return 1024  # Fallback


@cache_embedding(ttl=3600)
def embed_unified(
    text: str,
    max_length: Optional[int] = None,
    return_dense: bool = True,
    return_sparse: bool = True,
    return_colbert: bool = False,
    context: str = "query"
) -> Dict[str, Any]:
    """
    Unified generation of all BGE-M3 embedding types.

    Args:
        text: Input text
        max_length: Maximum token length (None = auto-detect)
        return_dense: Generate dense vectors (1024-dim)
        return_sparse: Generate sparse vectors
        return_colbert: Generate ColBERT vectors (for reranking)
        context: Context hint for optimization ("query" or "document")

    Returns:
        Dict with keys: dense_vecs, lexical_weights, colbert_vecs
    """
    # Determine backend based on configuration and system capabilities
    backend = _get_optimal_backend_strategy()

    if backend == "onnx":
        return _embed_unified_onnx(text, max_length, return_dense, return_sparse, context)
    elif backend == "bge":
        return _embed_unified_bge(text, max_length, return_dense, return_sparse, return_colbert, context)
    elif backend == "hybrid":
        return _embed_unified_hybrid(text, max_length, return_dense, return_sparse, return_colbert, context)
    else:
        logger.error(f"Unknown embeddings backend: {backend}")
        return _get_empty_result(return_dense, return_sparse, return_colbert)


def _embed_unified_onnx(
    text: str,
    max_length: Optional[int],
    return_dense: bool,
    return_sparse: bool,
    context: str
) -> Dict[str, Any]:
    """ONNX-only embedding generation (current implementation)."""
    if max_length is None:
        max_length = get_optimal_max_length(text, context)

    embedder, tokenizer = _get_onnx_embedder()
    if embedder is None or tokenizer is None:
        logger.error("ONNX embedder not available")
        return _get_empty_result(return_dense, return_sparse, False)

    result = {"dense_vecs": None, "lexical_weights": None, "colbert_vecs": None}

    if return_dense:
        try:
            import numpy as np

            inputs = tokenizer(
                [text],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="np"
            )

            # Prepare input dict based on available keys - ensure int64 for ONNX
            input_dict = {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64)
            }
            # Only add token_type_ids if present in tokenizer output
            if "token_type_ids" in inputs:
                input_dict["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)

            outputs = embedder.run(None, input_dict)
            embeddings = outputs[0]  # Assuming the first output is the embeddings

            # Mean pooling
            input_mask_expanded = np.expand_dims(inputs["attention_mask"], axis=-1).astype(float)
            sum_embeddings = np.sum(embeddings * input_mask_expanded, axis=1)
            sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
            mean_embeddings = sum_embeddings / sum_mask

            # Normalize embeddings if configured
            if CONFIG.embedding_normalize:
                norm = np.linalg.norm(mean_embeddings, axis=1, keepdims=True)
                mean_embeddings = mean_embeddings / norm

            result["dense_vecs"] = [mean_embeddings[0].tolist()]
            logger.debug(f"ONNX dense embedding generated: max_length={max_length}")

        except Exception as e:
            logger.error(f"ONNX dense embedding failed: {e}")
            result["dense_vecs"] = [[0.0] * 1024]

    if return_sparse:
        # ONNX doesn't support sparse directly, use empty result
        logger.warning("ONNX backend doesn't support sparse embeddings. Use 'bge' or 'hybrid' backend.")
        result["lexical_weights"] = [{}]

    return result


def _embed_unified_bge(
    text: str,
    max_length: Optional[int],
    return_dense: bool,
    return_sparse: bool,
    return_colbert: bool,
    context: str
) -> Dict[str, Any]:
    """BGE-M3 native embedding generation."""
    if max_length is None:
        max_length = get_optimal_max_length(text, context)

    model = _get_bge_model()
    if model is None:
        logger.error("BGE-M3 model not available")
        return _get_empty_result(return_dense, return_sparse, return_colbert)

    try:
        output = model.encode(
            [text],
            max_length=max_length,
            return_dense=return_dense,
            return_sparse=return_sparse,
            return_colbert_vecs=return_colbert
        )

        logger.debug(f"BGE-M3 encoding completed: max_length={max_length}, "
                    f"dense={return_dense}, sparse={return_sparse}, colbert={return_colbert}")

        return output

    except Exception as e:
        logger.error(f"BGE-M3 encoding failed: {e}")
        return _get_empty_result(return_dense, return_sparse, return_colbert)


def _embed_unified_hybrid(
    text: str,
    max_length: Optional[int],
    return_dense: bool,
    return_sparse: bool,
    return_colbert: bool,
    context: str
) -> Dict[str, Any]:
    """Hybrid approach: ONNX for dense (GPU), BGE-M3 for sparse (CPU)."""
    result = {"dense_vecs": None, "lexical_weights": None, "colbert_vecs": None}

    # Dense via ONNX (can use DirectML on Windows/AMD)
    if return_dense:
        onnx_result = _embed_unified_onnx(text, max_length, True, False, context)
        result["dense_vecs"] = onnx_result["dense_vecs"]

    # Sparse via BGE-M3 (CPU)
    if return_sparse or return_colbert:
        bge_result = _embed_unified_bge(text, max_length, False, return_sparse, return_colbert, context)
        result["lexical_weights"] = bge_result["lexical_weights"]
        result["colbert_vecs"] = bge_result["colbert_vecs"]

    return result


def _get_empty_result(return_dense: bool, return_sparse: bool, return_colbert: bool) -> Dict[str, Any]:
    """Generate empty result structure for fallback cases."""
    return {
        'dense_vecs': [[0.0] * 1024] if return_dense else None,
        'lexical_weights': [{}] if return_sparse else None,
        'colbert_vecs': [[[0.0] * 1024]] if return_colbert else None
    }


def embed_dense_optimized(text: str, max_length: Optional[int] = None) -> List[float]:
    """Optimized dense embedding generation."""
    result = embed_unified(text, max_length=max_length, return_dense=True, return_sparse=False, context="query")
    return result['dense_vecs'][0] if result['dense_vecs'] else [0.0] * 1024


def embed_sparse_optimized(text: str, max_length: Optional[int] = None) -> Dict[str, List]:
    """Optimized sparse embedding generation."""
    result = embed_unified(text, max_length=max_length, return_dense=False, return_sparse=True, context="query")

    if not result.get('lexical_weights') or not result['lexical_weights'][0]:
        return {"indices": [], "values": []}

    # Convert to Qdrant format
    lex_weights = result['lexical_weights'][0]
    indices = list(lex_weights.keys())
    values = list(lex_weights.values())

    return {"indices": indices, "values": values}


def embed_batch_optimized(
    texts: List[str],
    max_length: Optional[int] = None,
    return_dense: bool = True,
    return_sparse: bool = True,
    context: str = "document"
) -> Dict[str, List]:
    """Batch embedding generation for maximum efficiency."""
    if not texts:
        return {'dense_vecs': [], 'lexical_weights': []}

    backend = _get_optimal_backend_strategy()

    # Auto-optimize max_length for batch
    if max_length is None:
        avg_length = sum(len(text) for text in texts) / len(texts)
        max_length = get_optimal_max_length("x" * int(avg_length), context)

    if backend == "bge":
        return _embed_batch_bge(texts, max_length, return_dense, return_sparse)
    elif backend == "onnx":
        return _embed_batch_onnx(texts, max_length, return_dense, return_sparse)
    elif backend == "hybrid":
        return _embed_batch_hybrid(texts, max_length, return_dense, return_sparse)
    else:
        logger.error(f"Unknown backend for batch processing: {backend}")
        return {'dense_vecs': [], 'lexical_weights': []}


def _embed_batch_bge(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """BGE-M3 batch processing."""
    model = _get_bge_model()
    if model is None:
        logger.error("BGE-M3 model not available for batch processing")
        return _fallback_individual_processing(texts, max_length, return_dense, return_sparse)

    try:
        output = model.encode(
            texts,
            max_length=max_length,
            return_dense=return_dense,
            return_sparse=return_sparse,
            return_colbert_vecs=False  # ColBERT usually not needed in batch
        )

        logger.info(f"BGE-M3 batch encoding completed: {len(texts)} texts, max_length={max_length}")
        return output

    except Exception as e:
        logger.error(f"BGE-M3 batch encoding failed: {e}")
        return _fallback_individual_processing(texts, max_length, return_dense, return_sparse)


def _embed_batch_onnx(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """ONNX batch processing (dense only)."""
    results = {'dense_vecs': [], 'lexical_weights': []}

    if return_dense:
        embedder, tokenizer = _get_onnx_embedder()
        if embedder is None or tokenizer is None:
            logger.error("ONNX embedder not available for batch processing")
            return _fallback_individual_processing(texts, max_length, return_dense, return_sparse)

        try:
            import numpy as np

            inputs = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="np"
            )

            # Prepare input dict based on available keys - ensure int64 for ONNX
            input_dict = {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64)
            }
            # Only add token_type_ids if present in tokenizer output
            if "token_type_ids" in inputs:
                input_dict["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)

            outputs = embedder.run(None, input_dict)
            embeddings = outputs[0]

            # Batch mean pooling
            input_mask_expanded = np.expand_dims(inputs["attention_mask"], axis=-1).astype(float)
            sum_embeddings = np.sum(embeddings * input_mask_expanded, axis=1)
            sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
            mean_embeddings = sum_embeddings / sum_mask

            # Normalize if configured
            if CONFIG.embedding_normalize:
                norm = np.linalg.norm(mean_embeddings, axis=1, keepdims=True)
                mean_embeddings = mean_embeddings / norm

            results['dense_vecs'] = mean_embeddings.tolist()
            logger.info(f"ONNX batch dense encoding completed: {len(texts)} texts")

        except Exception as e:
            logger.error(f"ONNX batch encoding failed: {e}")
            return _fallback_individual_processing(texts, max_length, return_dense, return_sparse)

    if return_sparse:
        logger.warning("ONNX backend doesn't support sparse embeddings in batch mode")
        results['lexical_weights'] = [{}] * len(texts)

    return results


def _embed_batch_hybrid(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """Hybrid batch processing."""
    results = {'dense_vecs': [], 'lexical_weights': []}

    # Dense via ONNX
    if return_dense:
        onnx_result = _embed_batch_onnx(texts, max_length, True, False)
        results['dense_vecs'] = onnx_result['dense_vecs']

    # Sparse via BGE-M3
    if return_sparse:
        bge_result = _embed_batch_bge(texts, max_length, False, True)
        results['lexical_weights'] = bge_result['lexical_weights']

    return results


def _fallback_individual_processing(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """Fallback to individual processing when batch fails."""
    logger.info(f"Falling back to individual processing for {len(texts)} texts")
    results = {'dense_vecs': [], 'lexical_weights': []}

    for text in texts:
        try:
            result = embed_unified(text, max_length=max_length, return_dense=return_dense, return_sparse=return_sparse, context="document")
            if return_dense and result.get('dense_vecs'):
                results['dense_vecs'].append(result['dense_vecs'][0])
            else:
                results['dense_vecs'].append([0.0] * 1024)

            if return_sparse and result.get('lexical_weights'):
                results['lexical_weights'].append(result['lexical_weights'][0])
            else:
                results['lexical_weights'].append({})
        except Exception as e:
            logger.error(f"Individual processing failed for text: {e}")
            if return_dense:
                results['dense_vecs'].append([0.0] * 1024)
            if return_sparse:
                results['lexical_weights'].append({})

    return results


# Backward compatibility functions
def embed_dense(text: str) -> List[float]:
    """Legacy function for backward compatibility."""
    return embed_dense_optimized(text)


def embed_dense_batch(texts: List[str]) -> List[List[float]]:
    """Legacy function for backward compatibility."""
    result = embed_batch_optimized(texts, return_dense=True, return_sparse=False)
    return result.get('dense_vecs', [[0.0] * 1024] * len(texts))
