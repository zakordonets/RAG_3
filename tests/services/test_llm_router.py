import importlib.util
import pathlib
import sys
from types import ModuleType, SimpleNamespace

import pytest

project_root = pathlib.Path(__file__).resolve().parents[2]
module_path = project_root / "app" / "services" / "llm_router.py"


def load_llm_router(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    stubs: dict[str, ModuleType] = {}

    if "requests" not in sys.modules:
        requests_stub = ModuleType("requests")

        def _raise_post(*_args, **_kwargs):  # pragma: no cover - safety guard
            raise RuntimeError("requests.post should not be called in tests")

        requests_stub.post = _raise_post  # type: ignore[attr-defined]
        stubs["requests"] = requests_stub

    if "telegramify_markdown" not in sys.modules:
        telegramify_stub = ModuleType("telegramify_markdown")
        telegramify_stub.markdownify = lambda text: text  # type: ignore[attr-defined]
        stubs["telegramify_markdown"] = telegramify_stub

    if "loguru" not in sys.modules:
        loguru_stub = ModuleType("loguru")

        class _Logger:
            def debug(self, *_args, **_kwargs):
                pass

            info = warning = error = debug

        loguru_stub.logger = _Logger()  # type: ignore[attr-defined]
        stubs["loguru"] = loguru_stub

    app_stub = ModuleType("app")
    app_stub.__path__ = []  # type: ignore[attr-defined]
    stubs.setdefault("app", app_stub)

    config_stub = ModuleType("app.config")
    config_stub.CONFIG = SimpleNamespace(  # type: ignore[attr-defined]
        default_llm="YANDEX",
        yandex_api_url="https://example.com",
        yandex_catalog_id="catalog",
        yandex_api_key="key",
        yandex_model="model",
        yandex_max_tokens=4000,
        deepseek_api_url="https://deepseek",
        deepseek_api_key="",
        deepseek_model="model",
        gpt5_api_url="https://gpt5",
        gpt5_api_key="",
        gpt5_model="model",
    )
    stubs["app.config"] = config_stub

    log_utils_stub = ModuleType("app.log_utils")
    log_utils_stub.write_debug_event = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
    stubs["app.log_utils"] = log_utils_stub

    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location("app.services.llm_router", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load llm_router module")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "app.services.llm_router", module)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_generate_answer_omits_null_url(monkeypatch):
    llm_router = load_llm_router(monkeypatch)
    captured_prompt = {}

    def fake_yandex_complete(prompt, max_tokens=800, temperature=None, top_p=None, system_prompt=None):
        captured_prompt["prompt"] = prompt
        return "stubbed response"

    def fake_format_for_telegram(text: str) -> str:
        return text

    monkeypatch.setattr(llm_router, "_yandex_complete", fake_yandex_complete)
    monkeypatch.setattr(llm_router, "_format_for_telegram", fake_format_for_telegram)
    monkeypatch.setattr(llm_router, "DEFAULT_LLM", "YANDEX")

    context = [
        {
            "payload": {
                "title": "Документ без ссылки",
                "text": "Содержимое документа",
            }
        }
    ]

    result = llm_router.generate_answer("Вопрос?", context)

    assert result == "stubbed response"
    assert "🔗 None" not in captured_prompt["prompt"]
