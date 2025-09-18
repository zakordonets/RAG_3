from __future__ import annotations

from app import create_app

app = create_app()

if __name__ == "__main__":
    # For local debug run (use gunicorn/uvicorn in production)
    app.run(host="127.0.0.1", port=9000, debug=True)


