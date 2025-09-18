#!/usr/bin/env python3
import os
import time
from typing import List, Tuple

from loguru import logger

# Принудительно игнорируем глобальный ONNX_PROVIDER и управляем провайдерами в коде
os.environ.pop("ONNX_PROVIDER", None)

from transformers import AutoTokenizer
import onnxruntime as ort
from pathlib import Path

# Локальные артефакты
EMB_DIR = Path('models/onnx/bge-m3')
RR_DIR = Path('models/onnx/bge-reranker-base')


def make_texts(n: int) -> List[str]:
    base = [
        "Как настроить интеграцию с Telegram?",
        "Что такое RAG система?",
        "Как работает векторный поиск?",
        "Настройка Qdrant базы данных",
        "Конфигурация LLM провайдеров",
    ]
    out = []
    while len(out) < n:
        out.extend(base)
    return out[:n]


def bench_embeddings(provider: str, batch_sizes: List[int]) -> List[Tuple[int, float, float]]:
    model_path = (EMB_DIR / 'model.onnx')
    tok = AutoTokenizer.from_pretrained(str(EMB_DIR), use_fast=True)
    sess = ort.InferenceSession(str(model_path), providers=[provider, 'CPUExecutionProvider'])

    def encode(texts: List[str]) -> None:
        # mean-pooling как в проде
        import torch
        from torch.nn.functional import normalize
        inputs = tok(texts, padding=True, truncation=True, return_tensors='pt')
        feed = {}
        names = {i.name for i in sess.get_inputs()}
        if 'input_ids' in names:
            feed['input_ids'] = inputs['input_ids'].cpu().numpy()
        if 'attention_mask' in names:
            feed['attention_mask'] = inputs['attention_mask'].cpu().numpy()
        if 'token_type_ids' in inputs and 'token_type_ids' in names:
            feed['token_type_ids'] = inputs['token_type_ids'].cpu().numpy()
        outputs = sess.run(None, feed)
        last_hidden = torch.from_numpy(outputs[0])
        sent = (last_hidden * inputs['attention_mask'].unsqueeze(-1)).sum(1)
        sent = sent / (inputs['attention_mask'].sum(1).clamp(min=1e-9).unsqueeze(-1))
        _ = normalize(sent, p=2, dim=1).cpu().numpy()

    # прогрев
    encode(make_texts(8))
    results = []
    for bs in batch_sizes:
        texts = make_texts(bs)
        t0 = time.time()
        encode(texts)
        t = time.time() - t0
        results.append((bs, t, t/bs))
    return results


def bench_reranker(provider: str, batch_sizes: List[int]) -> List[Tuple[int, float, float]]:
    model_path = (RR_DIR / 'model.onnx')
    tok = AutoTokenizer.from_pretrained(str(RR_DIR), use_fast=True)
    sess = ort.InferenceSession(str(model_path), providers=[provider, 'CPUExecutionProvider'])

    def score(pairs: List[List[str]]) -> None:
        import torch
        inputs = tok([p[0] for p in pairs], [p[1] for p in pairs], padding=True, truncation=True, return_tensors='pt')
        feed = {}
        names = {i.name for i in sess.get_inputs()}
        if 'input_ids' in names:
            feed['input_ids'] = inputs['input_ids'].cpu().numpy()
        if 'attention_mask' in names:
            feed['attention_mask'] = inputs['attention_mask'].cpu().numpy()
        if 'token_type_ids' in inputs and 'token_type_ids' in names:
            feed['token_type_ids'] = inputs['token_type_ids'].cpu().numpy()
        logits = sess.run(None, feed)[0]
        _ = torch.sigmoid(torch.from_numpy(logits)).cpu().numpy()

    # прогрев
    score([["q", "d"]]*4)
    results = []
    query = "Как настроить интеграцию с Telegram?"
    for bs in batch_sizes:
        docs = make_texts(bs)
        pairs = [[query, d] for d in docs]
        t0 = time.time()
        score(pairs)
        t = time.time() - t0
        results.append((bs, t, t/bs))
    return results


def print_table(title: str, rows: List[Tuple[int, float, float]]):
    print(f"\n{title}")
    print("batch\tlatency_s\tper_item_s")
    for bs, lat, per in rows:
        print(f"{bs}\t{lat:.3f}\t{per:.4f}")


def main():
    batch_sizes = [4, 8, 16, 32, 64]
    providers = [('CPUExecutionProvider', 'CPU'), ('DmlExecutionProvider', 'DML')]

    for prov, label in providers:
        print(f"\n=== Embeddings [{label}] ===")
        emb = bench_embeddings(prov, batch_sizes)
        print_table("Embeddings", emb)

    for prov, label in providers:
        print(f"\n=== Reranker [{label}] ===")
        rr = bench_reranker(prov, batch_sizes)
        print_table("Reranker", rr)

    # Итоговая сводка ускорений по одному реперному батчу (например, 32)
    ref_bs = 32
    def pick(rows, bs):
        for b, lat, _ in rows:
            if b == bs:
                return lat
        return None

    emb_cpu = bench_embeddings('CPUExecutionProvider', [ref_bs])[0][1]
    emb_dml = bench_embeddings('DmlExecutionProvider', [ref_bs])[0][1]
    rr_cpu = bench_reranker('CPUExecutionProvider', [ref_bs])[0][1]
    rr_dml = bench_reranker('DmlExecutionProvider', [ref_bs])[0][1]

    print("\n=== Speedup (batch=32) ===")
    print(f"Embeddings DML speedup: {emb_cpu/emb_dml:.2f}x")
    print(f"Reranker DML speedup:   {rr_cpu/rr_dml:.2f}x")


if __name__ == '__main__':
    main()
