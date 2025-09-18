#!/usr/bin/env python3
import time
from typing import List, Tuple, Dict

from loguru import logger

# Локальные импорты
from app.services.embeddings import embed_dense_batch
from app.services.rerank import _ort_tokenizer as rr_tok_ref, _ort_sess as rr_sess_ref


def _make_texts(n: int) -> List[str]:
    base = [
        "Как настроить интеграцию с Telegram?",
        "Что такое RAG система?",
        "Как работает векторный поиск?",
        "Настройка Qdrant базы данных",
        "Конфигурация LLM провайдеров",
    ]
    texts: List[str] = []
    while len(texts) < n:
        texts.extend(base)
    return texts[:n]


def _pairs_from_texts(query: str, docs: List[str]) -> List[List[str]]:
    return [[query, d] for d in docs]


def bench_embeddings(batch_sizes: List[int]) -> List[Tuple[int, float, float]]:
    results = []
    # прогрев
    _ = embed_dense_batch(_make_texts(8))
    for bs in batch_sizes:
        texts = _make_texts(bs)
        t0 = time.time()
        _ = embed_dense_batch(texts)
        t1 = time.time() - t0
        results.append((bs, t1, t1/bs))
    return results


def bench_reranker(batch_sizes: List[int]) -> List[Tuple[int, float, float]]:
    # прямой ORT в реранкере уже инициализируется лениво при первом вызове rerank,
    # здесь мы намеренно дергаем внутренние ссылки, чтобы не менять API
    import onnxruntime as ort
    from transformers import AutoTokenizer
    from pathlib import Path
    # инициализация при необходимости
    if rr_sess_ref is None:
        from app.services.rerank import _get_reranker  # noqa: F401  # триггер инициализации
        pass
    # если все равно None, рантайм инициализирует при первом использовании через rerank
    from app.services.rerank import rerank

    results = []
    query = "Как настроить интеграцию с Telegram?"
    for bs in batch_sizes:
        docs = _make_texts(bs)
        pairs = _pairs_from_texts(query, docs)
        t0 = time.time()
        _ = rerank(query, [{"payload": {"text": d}} for d in docs], top_n=min(3, bs))
        t1 = time.time() - t0
        results.append((bs, t1, t1/bs))
    return results


def main():
    batch_sizes = [4, 8, 16, 32, 64, 128]

    print("\n=== Embeddings (ORT, текущее устройство) ===")
    emb = bench_embeddings(batch_sizes)
    print("batch\tlatency_s\tper_item_s")
    for bs, lat, per in emb:
        print(f"{bs}\t{lat:.3f}\t{per:.4f}")

    print("\n=== Reranker (ORT, текущее устройство) ===")
    rr = bench_reranker(batch_sizes[:-1])  # разумно ограничим до 64
    print("batch\tlatency_s\tper_item_s")
    for bs, lat, per in rr:
        print(f"{bs}\t{lat:.3f}\t{per:.4f}")

    print("\nNote: Сравнение CPU vs DML можно получить, временно переустановив провайдер (onnxruntime CPU) или выключив DML провайдер, затем повторив запуск.")


if __name__ == "__main__":
    main()
