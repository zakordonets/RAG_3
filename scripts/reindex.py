#!/usr/bin/env python3
"""
Скрипт переиндексации с BGE-M3 unified embeddings.

Использование:
  python scripts/reindex.py                    # стандартная переиндексация
  python scripts/reindex.py --sparse          # с включенными sparse vectors
  python scripts/reindex.py --backend=hybrid  # принудительно hybrid backend
"""

import argparse
import os
import sys
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.config import CONFIG
from ingestion.pipeline import crawl_and_index


def main():
    parser = argparse.ArgumentParser(description="Переиндексация с BGE-M3 unified embeddings")
    parser.add_argument("--sparse", action="store_true", help="Включить sparse vectors (рекомендуется)")
    parser.add_argument("--backend", choices=["auto", "onnx", "bge", "hybrid"],
                       default="auto", help="Выбор backend для эмбеддингов")
    parser.add_argument("--batch-size", type=int, default=16, help="Размер батча для обработки")
    parser.add_argument("--max-length", type=int, default=1024, help="Максимальная длина документов")

    args = parser.parse_args()

    # Устанавливаем переменные окружения
    if args.sparse:
        os.environ["USE_SPARSE"] = "true"
    if args.backend != "auto":
        os.environ["EMBEDDINGS_BACKEND"] = args.backend
    os.environ["EMBEDDING_BATCH_SIZE"] = str(args.batch_size)
    os.environ["EMBEDDING_MAX_LENGTH_DOC"] = str(args.max_length)

    logger.info("🚀 Запуск переиндексации с BGE-M3 unified embeddings...")

    # Показываем текущую конфигурацию
    logger.info(f"Конфигурация эмбеддингов:")
    logger.info(f"  EMBEDDINGS_BACKEND: {CONFIG.embeddings_backend}")
    logger.info(f"  EMBEDDING_DEVICE: {CONFIG.embedding_device}")
    logger.info(f"  USE_SPARSE: {CONFIG.use_sparse}")
    logger.info(f"  EMBEDDING_MAX_LENGTH_DOC: {CONFIG.embedding_max_length_doc}")
    logger.info(f"  EMBEDDING_BATCH_SIZE: {CONFIG.embedding_batch_size}")

    # Определяем оптимальную стратегию
    from app.services.bge_embeddings import _get_optimal_backend_strategy
    optimal_backend = _get_optimal_backend_strategy()
    logger.info(f"  Оптимальная стратегия: {optimal_backend}")

    # Предупреждение о времени выполнения
    logger.warning("⚠️  Переиндексация может занять 10-30 минут в зависимости от размера документации")
    logger.info("💡 Для отмены используйте Ctrl+C")

    try:
        stats = crawl_and_index(incremental=False)
        logger.success(f"✅ Переиндексация завершена!")
        logger.success(f"📊 Статистика: {stats['pages']} страниц, {stats['chunks']} чанков")

        # Проверяем результат
        from qdrant_client import QdrantClient
        client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        logger.success(f"🎯 Итого в базе: {collection_info.points_count} векторов")

    except KeyboardInterrupt:
        logger.warning("⚠️  Переиндексация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Ошибка переиндексации: {e}")
        raise


if __name__ == "__main__":
    main()
