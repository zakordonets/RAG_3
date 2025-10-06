from __future__ import annotations

import json
import os
import time
from typing import Any, Dict


def _ensure_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def write_debug_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Пишет диагностическое событие в файл JSONL (по одному объекту в строке).

    Файлы: logs/diagnostics/<YYYY-MM-DD>.jsonl
    """
    logs_dir = os.path.join("logs", "diagnostics")
    _ensure_dir(logs_dir)

    date_str = time.strftime("%Y-%m-%d")
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    out_path = os.path.join(logs_dir, f"{date_str}.jsonl")

    record = {
        "ts": ts,
        "event": event_type,
        **payload,
    }
    try:
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Логирование на диск не критично; игнорируем ошибки записи
        pass
