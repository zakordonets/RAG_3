from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, List
import sys
from pathlib import Path

import pytest
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.infrastructure.caching import CacheManager
from app.services.core import llm_router
from app.retrieval import retrieval


@contextmanager
def capture_log_messages(level: str = "DEBUG") -> Callable[[], List[str]]:
    messages: List[str] = []
    handler_id = logger.add(messages.append, format="{message}", level=level)
    try:
        yield lambda: messages
    finally:
        logger.remove(handler_id)


def test_hybrid_search_handles_qdrant_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingClient:
        def search(self, *args, **kwargs):
            raise TimeoutError("qdrant timeout")

    monkeypatch.setattr(retrieval, "client", FailingClient())

    with capture_log_messages(level="ERROR") as get_logs:
        result = retrieval.hybrid_search([0.0, 1.0, 0.0], {"indices": [], "values": []}, k=2)

    assert result == []
    assert any("Dense search failed" in message for message in get_logs()), "Timeout should be logged"


def test_cache_manager_falls_back_on_redis_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    cache_manager = CacheManager()

    class FailingRedis:
        def get(self, key: str) -> None:
            raise TimeoutError("redis get failure")

        def setex(self, key: str, ttl: int, value: str) -> None:
            raise TimeoutError("redis set failure")

    cache_manager.redis_client = FailingRedis()

    with capture_log_messages(level="WARNING") as get_logs:
        assert cache_manager.get("missing") is None
        cache_manager.set("key", {"value": 1}, ttl=60)

    warnings = get_logs()
    assert any("Cache get error" in message for message in warnings)
    assert any("Cache set error" in message for message in warnings)


def test_llm_router_falls_back_to_next_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_provider(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(llm_router, "_yandex_complete", failing_provider)
    monkeypatch.setattr(llm_router, "_gpt5_complete", failing_provider)
    monkeypatch.setattr(llm_router, "_deepseek_complete", lambda *args, **kwargs: "rescued answer")
    monkeypatch.setattr(llm_router, "write_debug_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(llm_router, "DEFAULT_LLM", "YANDEX", raising=False)

    with capture_log_messages(level="WARNING") as get_logs:
        result = llm_router.generate_answer("question", context=[])

    assert result["meta"]["provider"] == "DEEPSEEK"
    assert result["answer_markdown"] == "rescued answer"
    warnings = get_logs()
    assert any("provider YANDEX failed" in message for message in warnings)
    assert any("provider GPT5 failed" in message for message in warnings)


def test_llm_router_reports_total_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_provider(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(llm_router, "_yandex_complete", failing_provider)
    monkeypatch.setattr(llm_router, "_gpt5_complete", failing_provider)
    monkeypatch.setattr(llm_router, "_deepseek_complete", failing_provider)
    monkeypatch.setattr(llm_router, "write_debug_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(llm_router, "DEFAULT_LLM", "YANDEX", raising=False)

    with capture_log_messages(level="ERROR") as get_logs:
        result = llm_router.generate_answer("question", context=[])

    assert result["meta"].get("error") == "all_providers_failed"
    assert "провайдеры LLM недоступны" in result["answer_markdown"]
    errors = get_logs()
    assert any("all providers failed" in message.lower() for message in errors)
