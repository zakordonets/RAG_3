from __future__ import annotations

"""
Временный миграционный слой для функций из ingestion/parsers.py.
Удалить после полной миграции потребителей на новый ContentProcessor.
"""

import time
from typing import Dict, Any
from loguru import logger


def extract_url_metadata(url: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ заглушка: возвращает базовые метаданные по URL.

    В прежней реализации использовалась логика из parsers.py. Здесь оставляем
    тонкую совместимость, чтобы не ломать текущие импортёры до полного перехода.
    """
    try:
        return {
            "url": url,
            "source": "migrated",
            "extracted_at": time.time(),
        }
    except Exception as e:
        logger.warning(f"Migration fallback for extract_url_metadata({url}): {e}")
        return {"url": url}


