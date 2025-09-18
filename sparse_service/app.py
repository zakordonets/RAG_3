from __future__ import annotations

import os
from fastapi import FastAPI
from pydantic import BaseModel
from FlagEmbedding import BGEM3FlagModel
from typing import Any

try:
    import numpy as np  # noqa: F401
    from scipy.sparse import csr_matrix  # type: ignore
except Exception:
    csr_matrix = None  # type: ignore


class EmbedRequest(BaseModel):
    text: str


MODEL_NAME = os.getenv("SPARSE_MODEL", "BAAI/bge-m3")
DEVICE = os.getenv("SPARSE_DEVICE", "cpu")
# Windows: отключаем симлинки в кэше HF, иначе требуются админ-права/Developer Mode
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

app = FastAPI(title="Sparse Embedding Service (BGE-M3)")
model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, device=DEVICE)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "device": DEVICE}


@app.post("/embed")
def embed(req: EmbedRequest) -> dict:
    """Возвращает sparse-вектор в формате {indices: [...], values: [...]}.
    Поддерживает разные форматы ответа BGEM3FlagModel.encode.
    """
    out: Any = model.encode([req.text], return_dense=False, return_sparse=True)
    # Возможные варианты out:
    # 1) {"sparse_vecs": [{"indices": [...], "values": [...]}]}
    # 2) {"sparse": csr_matrix}
    # 3) {"sparse_vecs": {"indices": [...], "values": [...]}}  # единичный

    # Case 1: list под ключом sparse_vecs
    if isinstance(out, dict) and "sparse_vecs" in out:
        sv = out["sparse_vecs"]
        if isinstance(sv, list) and sv:
            sv0 = sv[0]
            if isinstance(sv0, dict) and "indices" in sv0 and "values" in sv0:
                return {"indices": sv0["indices"], "values": sv0["values"]}
        if isinstance(sv, dict) and "indices" in sv and "values" in sv:
            return {"indices": sv["indices"], "values": sv["values"]}

    # Case 2: scipy csr_matrix под ключом sparse
    if isinstance(out, dict) and "sparse" in out and csr_matrix is not None:
        sm = out["sparse"]
        if isinstance(sm, csr_matrix):
            sm = sm.tocsr()
            # Один документ → одна строка CSR
            row = sm.getrow(0)
            return {"indices": row.indices.tolist(), "values": row.data.astype(float).tolist()}

    # Fallback: пустой sparse
    return {"indices": [], "values": []}


