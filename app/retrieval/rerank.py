from __future__ import annotations

from typing import Any
import os
import threading
from FlagEmbedding import FlagReranker
from sentence_transformers import CrossEncoder
from app.config import CONFIG
from app.hardware import get_device, optimize_for_gpu, clear_gpu_cache
from loguru import logger
from pathlib import Path
import onnxruntime as ort
import torch


_reranker = None
_ort_model = None
_ort_tokenizer = None
_ort_sess: ort.InferenceSession | None = None
_lock = threading.Lock()


def _get_reranker() -> Any:
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                # Определяем устройство
                device = get_device() if CONFIG.gpu_enabled else CONFIG.reranker_device

                # Настраиваем потоки только для CPU
                if device == "cpu":
                    os.environ["OMP_NUM_THREADS"] = str(CONFIG.reranker_threads)
                    os.environ["MKL_NUM_THREADS"] = str(CONFIG.reranker_threads)

                logger.info(f"Loading reranker model: {CONFIG.reranker_model} on {device}...")

                # ONNX + DirectML: прямой ORT (через локальные артефакты), без Optimum
                if device == 'dml':
                    try:
                        from transformers import AutoTokenizer
                        local_dir = Path("models/onnx/bge-reranker-base")
                        model_path = local_dir / "model.onnx"
                        if not model_path.exists():
                            raise RuntimeError(f"ONNX model not found at {model_path}")
                        # Выбор провайдера на основе конфигурации
                        providers = ["CPUExecutionProvider"]
                        if CONFIG.onnx_provider in ("auto", "dml"):
                            providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                        global _ort_sess
                        _ort_sess = ort.InferenceSession(str(model_path), providers=providers)
                        from transformers import AutoTokenizer
                        global _ort_tokenizer
                        _ort_tokenizer = AutoTokenizer.from_pretrained(str(local_dir), use_fast=True)
                        logger.info("ONNX reranker initialized (direct ORT + DML)")
                    except Exception as e:
                        logger.warning(f"ONNX ORT reranker init failed, falling back to CPU FlagReranker: {e}")
                        _ort_model = None
                        _ort_tokenizer = None
                        _reranker = FlagReranker(CONFIG.reranker_model, use_fp16=False, device='cpu')
                else:
                    # CPU/CUDA путь
                    try:
                        _reranker = FlagReranker(CONFIG.reranker_model, use_fp16=False, device=device)
                    except Exception as e:
                        logger.warning(f"FlagReranker init failed on {device}, trying CrossEncoder CPU: {e}")
                        from sentence_transformers import CrossEncoder
                        _reranker = CrossEncoder("BAAI/bge-reranker-base")

                # Оптимизируем для GPU если доступно
                if device.startswith('cuda'):
                    _reranker = optimize_for_gpu(_reranker, device)
                    logger.info(f"Reranker optimized for GPU: {device}")

                logger.info("Reranker model loaded successfully")
    return _reranker


def rerank(query: str, candidates: list[dict], top_n: int = 10, batch_size: int | None = None, max_length: int | None = None) -> list[dict]:
    """Реализация bge-reranker-v2-m3 на CPU с пакетной обработкой.
    - batch_size: размер батча для ускорения токенизации/инференса
    - max_length: максимальная длина токенов документа (усечение текста)
    Возвращает top_n документов, отсортированных по релевантности к запросу.
    """
    if not candidates:
        return []
    reranker = _get_reranker()

    # Подготовка пар (с отсечением)
    def get_doc_text(c: dict) -> str:
        payload = (c.get("payload", {}) or {})
        text = payload.get("text") or payload.get("title") or ""
        if not text:
            return ""
        if max_length and isinstance(max_length, int) and max_length > 0:
            # Простое усечение по символам (чтобы не тянуть лишнее в токенайзер)
            return text[: max_length]
        return text

    pairs = [[query, get_doc_text(c)] for c in candidates]

    # Пакетная обработка
    bs = batch_size or getattr(CONFIG, "reranker_batch_size", 16)
    all_scores: list[float] = []
    try:
        # Если есть ONNX ORT сессия (DML)
        if _ort_sess is not None and _ort_tokenizer is not None:
            for i in range(0, len(pairs), bs):
                chunk = pairs[i : i + bs]
                texts_a = [a for a, _ in chunk]
                texts_b = [b for _, b in chunk]
                enc = _ort_tokenizer(texts_a, texts_b, padding=True, truncation=True, return_tensors="pt")
                feed = {}
                input_names = {i.name for i in _ort_sess.get_inputs()}
                if "input_ids" in input_names:
                    feed["input_ids"] = enc["input_ids"].cpu().numpy()
                if "attention_mask" in input_names:
                    feed["attention_mask"] = enc["attention_mask"].cpu().numpy()
                if "token_type_ids" in enc and "token_type_ids" in input_names:
                    feed["token_type_ids"] = enc["token_type_ids"].cpu().numpy()
                outputs = _ort_sess.run(None, feed)
                logits = torch.from_numpy(outputs[0]).squeeze(-1)
                scores = torch.sigmoid(logits).cpu().numpy().tolist()
                all_scores.extend([float(s) for s in scores])
        elif isinstance(reranker, CrossEncoder):
            for i in range(0, len(pairs), bs):
                chunk = pairs[i : i + bs]
                chunk_scores = reranker.predict(chunk, batch_size=bs)
                all_scores.extend([float(s) for s in chunk_scores])
        else:
            # FlagReranker
            for i in range(0, len(pairs), bs):
                chunk = pairs[i : i + bs]
                chunk_scores = reranker.compute_score(chunk, normalize=True)
                all_scores.extend([float(s) for s in chunk_scores])
    except Exception as e:
        logger.warning(f"Reranker batch scoring failed: {e}; falling back to single-batch")
        try:
            if isinstance(reranker, CrossEncoder):
                all_scores = [float(s) for s in reranker.predict(pairs, batch_size=bs)]
            else:
                all_scores = [float(s) for s in reranker.compute_score(pairs, normalize=True)]
        except Exception as e2:
            logger.error(f"Reranker scoring failed completely: {e2}")
            return candidates[:top_n]

    # Присваиваем и сортируем
    for i, s in enumerate(all_scores):
        candidates[i]["rerank_score"] = s
    candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return candidates[:top_n]
