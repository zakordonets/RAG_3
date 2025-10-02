#!/usr/bin/env python3
"""
Скрипт очистки коллекции Qdrant и её пересоздания с актуальной схемой.

Запуск:
  python scripts/clear_collection.py
"""

from __future__ import annotations

import sys
import os
import time
from typing import Optional

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from app.config import CONFIG


def backup_points(limit: int = 10000) -> Optional[list]:
    """Делает простой бэкап первых N точек (payload без векторов)."""
    try:
        client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)
        points, _ = client.scroll(
            collection_name=CONFIG.qdrant_collection,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return points
    except Exception:
        return None


def clear_collection() -> None:
    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    # Удаляем коллекцию, если есть
    try:
        if client.collection_exists(CONFIG.qdrant_collection):
            client.delete_collection(CONFIG.qdrant_collection)
    except Exception:
        pass

    # Пересоздаем с актуальной схемой через существующий инициализатор
    # Используем scripts.init_qdrant.main()
    from scripts.init_qdrant import main as create_collection

    # Небольшая пауза чтобы сервер успел применить удаление
    time.sleep(0.5)
    create_collection()


if __name__ == "__main__":
    # Опциональный простой бэкап (в память)
    _ = backup_points(limit=1000)
    clear_collection()
    print(f"Collection '{CONFIG.qdrant_collection}' cleared and recreated at {CONFIG.qdrant_url}")
