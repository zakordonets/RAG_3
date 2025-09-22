from __future__ import annotations

from app import create_app
from app.metrics import get_metrics_collector
import os

app = create_app()

# Инициализируем metrics collector только в рабочем процессе и если явно разрешено
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" and os.getenv("START_METRICS_SERVER", "true").lower() == "true":
    metrics_collector = get_metrics_collector()

if __name__ == "__main__":
    # For local debug run (use gunicorn/uvicorn in production)
    app.run(host="127.0.0.1", port=9000, debug=True)
