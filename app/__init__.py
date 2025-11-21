from __future__ import annotations

import os
from flask import Flask
from flask_cors import CORS
from loguru import logger

try:
    from flasgger import Swagger
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Swagger = None
    logger.warning("Flasgger not installed; Swagger UI will be disabled.")

from .config import CONFIG
from .utils.logging_config import configure_logging  # Включаем простое логирование


def create_app() -> Flask:
    app = Flask(__name__)

    # Bind selected config values (optional, services import CONFIG directly)
    app.config["QDRANT_URL"] = CONFIG.qdrant_url
    app.config["QDRANT_API_KEY"] = CONFIG.qdrant_api_key
    app.config["DEFAULT_LLM"] = CONFIG.default_llm

    CORS(app)

    # Blueprints
    from .routes.chat import bp as chat_bp
    from .routes.admin import bp as admin_bp
    from .routes.quality import bp as quality_bp

    app.register_blueprint(chat_bp, url_prefix="/v1/chat")
    app.register_blueprint(admin_bp, url_prefix="/v1/admin")
    app.register_blueprint(quality_bp, url_prefix="/v1/admin/quality")

    # Swagger/OpenAPI конфигурация (v4.3.0)
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec_1",
                "route": "/apispec_1.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs"
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "edna Chat Center RAG API",
            "description": "API для RAG-системы технической поддержки edna Chat Center. "
                          "Система использует гибридный поиск (dense + sparse), "
                          "LLM роутинг с fallback и RAGAS систему оценки качества.",
            "contact": {
                "name": "API Support",
                "url": "https://docs-chatcenter.edna.ru"
            },
            "version": "4.3.0"
        },
        "host": "localhost:9000",
        "basePath": "/",
        "schemes": ["http", "https"],
        "tags": [
            {
                "name": "Chat",
                "description": "Основные операции чата"
            },
            {
                "name": "Admin",
                "description": "Административные функции"
            },
            {
                "name": "Quality",
                "description": "Система оценки качества (RAGAS)"
            }
        ]
    }

    if Swagger is not None:
        Swagger(app, config=swagger_config, template=swagger_template)
    else:
        logger.info("Skipping Swagger initialization (flasgger module unavailable).")

    # Прогреваем эмбеддеры и связанные модели только в рабочем процессе (без родителя reloader)
    if os.environ.get("WERKZEUG_RUN_MAIN") != "false" and os.environ.get("SKIP_EMBEDDING_WARMUP") != "1":
        try:
            from app.services.core.embeddings import warmup_embeddings

            warmup_embeddings()
        except Exception as exc:
            logger.warning(f"Embedding warmup skipped due to error: {exc}")
    return app
