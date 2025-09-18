#!/usr/bin/env python3
import os
from pathlib import Path
from loguru import logger

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def export_embedder() -> None:
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from transformers import AutoTokenizer
    model_id = 'BAAI/bge-m3'
    out_dir = Path('models/onnx/bge-m3')
    ensure_dir(out_dir)
    logger.info('Exporting embeddings model to ONNX...')
    model = ORTModelForFeatureExtraction.from_pretrained(model_id, export=True)
    tok = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    model.save_pretrained(str(out_dir))
    tok.save_pretrained(str(out_dir))
    logger.info('Embeddings ONNX exported to %s', out_dir)

def export_reranker() -> None:
    from optimum.onnxruntime import ORTModelForSequenceClassification
    from transformers import AutoTokenizer
    model_id = 'BAAI/bge-reranker-base'
    out_dir = Path('models/onnx/bge-reranker-base')
    ensure_dir(out_dir)
    logger.info('Exporting reranker model to ONNX...')
    model = ORTModelForSequenceClassification.from_pretrained(model_id, export=True)
    tok = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    model.save_pretrained(str(out_dir))
    tok.save_pretrained(str(out_dir))
    logger.info('Reranker ONNX exported to %s', out_dir)

if __name__ == '__main__':
    export_embedder()
    export_reranker()
    print('✅ ONNX экспорт завершен')
