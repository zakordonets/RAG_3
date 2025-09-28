from __future__ import annotations

from typing import Iterable, Tuple, List, Dict, Any
import os
import requests
from loguru import logger
from app.config import CONFIG
from app.caching import cache_embedding, cache_manager
from app.gpu_utils import get_device, optimize_for_gpu, clear_gpu_cache
from threading import Lock
import numpy as np
import torch
from pathlib import Path
import onnxruntime as ort

# На Windows отключаем symlink'и HuggingFace, чтобы избежать прав доступа
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

_st_model = None  # SentenceTransformers CPU/CUDA путь
_onnx_model = None  # Optimum ORT модель для DirectML (не используется при прямом ORT)
_onnx_tokenizer = None
_ort_sess: ort.InferenceSession | None = None
_ort_tokenizer = None
_st_lock: Lock | None = Lock()


# Legacy parameters removed - using BGE-M3 directly


def _init_onnx_embedder() -> Tuple[object, object]:
    """Инициализирует Optimum ORT эмбеддер (модель + токенайзер) под DirectML."""
    global _onnx_model, _onnx_tokenizer
    if _onnx_model is not None and _onnx_tokenizer is not None:
        return _onnx_model, _onnx_tokenizer

    assert _st_lock is not None
    with _st_lock:
        if _onnx_model is None or _onnx_tokenizer is None:
            from optimum.onnxruntime import ORTModelForFeatureExtraction
            from transformers import AutoTokenizer

            hf_model = 'BAAI/bge-m3'
            local_dir = Path("models/onnx/bge-m3")
            if local_dir.exists() and (local_dir/"model.onnx").exists():
                logger.info("Initializing ONNX embedder from local path (models/onnx/bge-m3) with DmlExecutionProvider...")
                _onnx_model = ORTModelForFeatureExtraction.from_pretrained(
                    str(local_dir),
                    provider="DmlExecutionProvider",
                )
                _onnx_tokenizer = AutoTokenizer.from_pretrained(str(local_dir), use_fast=True)
                logger.info("ONNX embedder initialized from local artifacts")
            else:
                logger.info("Local ONNX artifacts not found, attempting export on the fly (may require onnxruntime CPU)...")
                _onnx_model = ORTModelForFeatureExtraction.from_pretrained(
                    hf_model,
                    export=True,
                    provider="DmlExecutionProvider",
                )
                _onnx_tokenizer = AutoTokenizer.from_pretrained(hf_model, use_fast=True)
                logger.info("ONNX embedder initialized (Optimum/ORT + DML)")
    return _onnx_model, _onnx_tokenizer


def _init_st_embedder():
    """Инициализирует обычный SentenceTransformers (CPU/CUDA)."""
    global _st_model
    if _st_model is not None:
        return _st_model

    assert _st_lock is not None
    with _st_lock:
        if _st_model is None:
            from sentence_transformers import SentenceTransformer
            hf_model = 'BAAI/bge-m3'
            device = get_device()
            if device == 'dml':
                device = 'cpu'
            logger.info(f"Initializing SentenceTransformers embedder on {device}...")
            _st_model = SentenceTransformer(hf_model, device=device)
            try:
                dim = _st_model.get_sentence_embedding_dimension()
            except Exception:
                dim = "unknown"
            logger.info(f"ST embedder ready. Dim: {dim}")
    return _st_model


def _mean_pooling(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def _init_ort_session() -> Tuple[ort.InferenceSession, Any]:
    global _ort_sess, _ort_tokenizer
    if _ort_sess is not None and _ort_tokenizer is not None:
        return _ort_sess, _ort_tokenizer
    assert _st_lock is not None
    with _st_lock:
        if _ort_sess is None or _ort_tokenizer is None:
            from transformers import AutoTokenizer
            local_dir = Path("models/onnx/bge-m3")
            model_path = local_dir / "model.onnx"
            if not model_path.exists():
                raise RuntimeError(f"ONNX model not found at {model_path}")
            # Выбор провайдера на основе конфигурации
            providers = ["CPUExecutionProvider"]
            if CONFIG.onnx_provider in ("auto", "dml"):
                providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
            _ort_sess = ort.InferenceSession(str(model_path), providers=providers)
            _ort_tokenizer = AutoTokenizer.from_pretrained(str(local_dir), use_fast=True)
    return _ort_sess, _ort_tokenizer


def _prepare_ort_inputs(sess: ort.InferenceSession, enc: Dict[str, Any]) -> Dict[str, Any]:
    feed: Dict[str, Any] = {}
    input_names = {i.name for i in sess.get_inputs()}
    if "input_ids" in input_names:
        feed["input_ids"] = enc["input_ids"].cpu().numpy()
    if "attention_mask" in input_names:
        feed["attention_mask"] = enc["attention_mask"].cpu().numpy()
    if "token_type_ids" in enc and "token_type_ids" in input_names:
        feed["token_type_ids"] = enc["token_type_ids"].cpu().numpy()
    return feed


def _encode_onnx(texts: List[str], batch_size: int = 64) -> np.ndarray:
    sess, tokenizer = _init_ort_session()
    all_vecs: List[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i+batch_size]
        enc = tokenizer(chunk, padding=True, truncation=True, return_tensors="pt")
        feed = _prepare_ort_inputs(sess, enc)
        outputs = sess.run(None, feed)
        # Берём первый выход как last_hidden_state: [B, T, H]
        last_hidden = torch.from_numpy(outputs[0])
        sent_emb = _mean_pooling(last_hidden, enc["attention_mask"])  # [B, H]
        sent_emb = torch.nn.functional.normalize(sent_emb, p=2, dim=1)
        all_vecs.append(sent_emb.cpu().numpy())
    return np.vstack(all_vecs)


@cache_embedding(ttl=3600)  # Кэшируем на 1 час
def embed_dense(text: str) -> list[float]:
    """Возвращает dense-эмбеддинг через локальный SentenceTransformers (BAAI/bge-m3)."""
    device = get_device()
    if device == 'dml':
        vec = _encode_onnx([text], batch_size=32)[0]
        return vec.astype(np.float32).tolist()
    # CPU/CUDA через SentenceTransformers
    model = _init_st_embedder()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_dense_batch(texts: Iterable[str]) -> list[list[float]]:
    texts_list = list(texts)
    if not texts_list:
        return []
    device = get_device()
    if device == 'dml':
        mat = _encode_onnx(texts_list, batch_size=64)
        return [row.astype(np.float32).tolist() for row in mat]
    model = _init_st_embedder()
    mat = model.encode(texts_list, normalize_embeddings=True)
    return [row.tolist() for row in mat]


def embed_sparse(text: str) -> dict:
    """DEPRECATED: Sparse embedding through external service.

    This function is deprecated as sparse vectors are now handled by BGE-M3.
    Use embed_batch_optimized from bge_embeddings.py instead.
    """
    logger.warning("embed_sparse is deprecated. Use BGE-M3 sparse vectors instead.")
    return {"indices": [], "values": []}


def embed_sparse_batch(texts: Iterable[str]) -> list[dict[str, float]]:
    return [embed_sparse(t) for t in texts]
