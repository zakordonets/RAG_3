from __future__ import annotations

from typing import Any, Dict
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from flask import Flask

from app import create_app
from app.routes import admin as admin_routes
from app.routes import chat as chat_routes
from app.routes import quality as quality_routes


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    app: Flask = create_app()
    app.config.update(TESTING=True)

    def fake_validate_query_data(payload: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, list[str]]]:
        errors: Dict[str, list[str]] = {}
        result: Dict[str, Any] = {}

        message = str(payload.get("message", "")).strip()
        if message:
            result["message"] = message
        else:
            errors.setdefault("message", []).append("Field is required")

        channel = str(payload.get("channel", "telegram")).strip() or "telegram"
        result["channel"] = channel

        chat_id_raw = str(payload.get("chat_id", "")).strip()
        if chat_id_raw:
            result["chat_id"] = chat_id_raw
        else:
            errors.setdefault("chat_id", []).append("Field is required")

        return result, errors

    def fake_validate_request(*, user_id: str, message: str, channel: str, chat_id: str) -> Dict[str, Any]:
        return {
            "is_valid": True,
            "sanitized_message": message,
            "warnings": [],
            "errors": [],
        }

    def fake_handle_query(channel: str, chat_id: str, message: str) -> Dict[str, Any]:
        return {
            "answer": "stub markdown",
            "answer_markdown": "stub markdown",
            "sources": [{"title": "Doc", "url": "https://site.example.com/doc"}],
            "meta": {"provider": "DEEPSEEK"},
            "channel": channel,
            "chat_id": chat_id,
            "processing_time": 0.42,
            "interaction_id": "interaction-123",
        }

    class ConfigStub:
        docs_root = "/tmp/docs"
        site_base_url = "https://example.com"
        site_docs_prefix = "/docs"
        qdrant_collection = "test_collection"
        chunk_max_tokens = 600
        chunk_min_tokens = 200

    config_stub = ConfigStub()

    def fake_run_unified_indexing(**_: Any) -> Dict[str, Any]:
        return {
            "stats": {
                "processed_docs": 3,
                "failed_docs": 0,
                "total_docs": 3,
                "duration": 1.23,
            }
        }

    def fake_get_metrics_summary() -> Dict[str, Any]:
        return {
            "queries_total": 7,
            "queries_by_channel": {"telegram": 4, "web": 2, "api": 1},
            "queries_by_status": {"success": 6, "error": 1},
            "avg_query_duration": 1.5,
            "avg_embedding_duration": 0.3,
            "avg_search_duration": 0.2,
            "avg_llm_duration": 0.8,
            "cache_hit_rate": 0.75,
            "errors_total": 1,
        }

    async def fake_get_quality_statistics(days: int) -> Dict[str, Any]:
        return {
            "period_days": days,
            "total_interactions": 12,
            "avg_ragas_score": 0.72,
            "avg_faithfulness": 0.81,
            "avg_answer_relevancy": 0.75,
            "avg_context_precision": 0.7,
            "avg_combined_score": 0.74,
            "total_feedback": 5,
            "positive_feedback": 4,
            "negative_feedback": 1,
        }

    monkeypatch.setattr(chat_routes, "validate_query_data", fake_validate_query_data)
    monkeypatch.setattr(chat_routes, "validate_request", fake_validate_request)
    monkeypatch.setattr(chat_routes, "handle_query", fake_handle_query)
    monkeypatch.setattr(admin_routes, "run_unified_indexing", fake_run_unified_indexing)
    monkeypatch.setattr(admin_routes, "get_metrics_summary", fake_get_metrics_summary)
    monkeypatch.setattr(quality_routes.quality_manager, "get_quality_statistics", fake_get_quality_statistics)
    monkeypatch.setattr(admin_routes, "CONFIG", config_stub, raising=False)

    from app.config import app_config

    monkeypatch.setattr(app_config, "CONFIG", config_stub, raising=False)

    return app.test_client()


def test_chat_query_contract_success(app_client: Any) -> None:
    response = app_client.post(
        "/v1/chat/query",
        json={"message": "How to start?", "channel": "web", "chat_id": "user-1"},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert isinstance(body, dict)
    assert body["answer_markdown"] == "stub markdown"
    assert body["meta"]["provider"] == "DEEPSEEK"
    assert isinstance(body["sources"], list)
    assert isinstance(body["processing_time"], (int, float))
    assert body["channel"] == "web"
    assert body["chat_id"] == "user-1"


def test_chat_query_contract_validation_error(app_client: Any) -> None:
    response = app_client.post(
        "/v1/chat/query",
        json={"channel": "web", "chat_id": ""},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"] == "validation_failed"
    assert "message" in body["details"]
    assert "chat_id" in body["details"]


def test_admin_reindex_contract_success(app_client: Any) -> None:
    response = app_client.post("/v1/admin/reindex", json={"force_full": True})
    body = response.get_json()

    assert response.status_code == 200
    assert body["status"] == "done"
    assert body["force_full"] is True
    assert "stats" in body
    assert body["stats"]["processed_docs"] == 3
    assert isinstance(body["stats"]["duration"], (int, float))


def test_admin_metrics_contract_success(app_client: Any) -> None:
    response = app_client.get("/v1/admin/metrics")
    body = response.get_json()

    assert response.status_code == 200
    assert body["queries_total"] == 7
    assert set(body["queries_by_channel"].keys()) == {"telegram", "web", "api"}
    assert body["cache_hit_rate"] == pytest.approx(0.75)


def test_quality_stats_contract_success(app_client: Any) -> None:
    response = app_client.get("/v1/admin/quality/stats?days=7")
    body = response.get_json()

    assert response.status_code == 200
    assert body["period_days"] == 7
    assert body["total_interactions"] == 12
    assert 0.0 <= body["avg_ragas_score"] <= 1.0
    assert body["positive_feedback"] == 4
    assert body["negative_feedback"] == 1
