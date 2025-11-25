from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from app.config import CONFIG


def _get_log_file_path() -> Path:
    log_dir = Path(CONFIG.query_log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"query_interactions_{date_str}.json"
    return log_dir / filename


def log_query_interaction(payload: Dict[str, Any]) -> None:
    """
    Записывает взаимодействие по запросу в JSON-лог.

    Args:
        payload: JSON-сериализуемый словарь с данными запроса.
    """
    if not CONFIG.query_log_enabled:
        return

    file_path = _get_log_file_path()
    try:
        json_line = json.dumps(payload, ensure_ascii=False)
        with file_path.open("a", encoding="utf-8") as f:
            f.write(json_line + "\n")
    except Exception as exc:
        logger.warning(f"Failed to write query log: {exc}")
