from __future__ import annotations

import os
from flask import Flask
from flask_cors import CORS
from .config import CONFIG


def create_app() -> Flask:
    app = Flask(__name__)

    # Bind selected config values (optional, services import CONFIG directly)
    app.config["QDRANT_URL"] = CONFIG.qdrant_url
    app.config["QDRANT_API_KEY"] = CONFIG.qdrant_api_key
    app.config["OLLAMA_URL"] = CONFIG.ollama_url
    app.config["DEFAULT_LLM"] = CONFIG.default_llm

    CORS(app)

    # Blueprints
    from .routes.chat import bp as chat_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(chat_bp, url_prefix="/v1/chat")
    app.register_blueprint(admin_bp, url_prefix="/v1/admin")

    # Swagger/OpenAPI отключен (Flasgger удалён по требованию)

    return app
