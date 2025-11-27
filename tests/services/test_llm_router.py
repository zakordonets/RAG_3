import importlib.util
import pathlib
import sys
from types import ModuleType, SimpleNamespace

import pytest

from ..fixtures.data_samples import REFERENCE_URLS
from ..fixtures.factories import make_context_document, make_source

pytestmark = pytest.mark.unit

project_root = pathlib.Path(__file__).resolve().parents[2]
module_path = project_root / "app" / "services" / "core" / "llm_router.py"


def load_llm_router(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    stubs: dict[str, ModuleType] = {}

    if "requests" not in sys.modules:
        requests_stub = ModuleType("requests")

        def _raise_post(*_args, **_kwargs):  # pragma: no cover - safety guard
            raise RuntimeError("requests.post should not be called in tests")

        requests_stub.post = _raise_post  # type: ignore[attr-defined]
        stubs["requests"] = requests_stub

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
        core_outputs_format="markdown",
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
        gigachat_client_id="id",
        gigachat_client_secret="secret",
        gigachat_scope="GIGACHAT_API_PERS",
        gigachat_model="GigaChat:latest",
        gigachat_timeout=60,
        gigachat_api_url="https://gigachat",
        gigachat_auth_url="https://ngw",
        gigachat_verify_ssl=True,
        connectors_telegram_format="HTML",
        telegram_html_allowlist="",
    )
    stubs["app.config"] = config_stub

    utils_stub = ModuleType("app.utils")
    utils_stub.write_debug_event = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
    stubs["app.utils"] = utils_stub

    gigachat_stub = ModuleType("app.services.core.gigachat_client")

    class _FakeGigaChat:
        def chat_completion(self, *_args, **_kwargs):
            return "stubbed response"

    gigachat_stub.get_gigachat_client = lambda: _FakeGigaChat()  # type: ignore[attr-defined]
    stubs["app.services.core.gigachat_client"] = gigachat_stub

    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location("app.services.core.llm_router", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load llm_router module")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "app.services.core.llm_router", module)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_generate_answer_omits_null_url(monkeypatch):
    llm_router = load_llm_router(monkeypatch)
    captured_prompt = {}

    def fake_yandex_complete(prompt, max_tokens=800, temperature=None, top_p=None, system_prompt=None):
        captured_prompt["prompt"] = prompt
        return "stubbed response"

    def fake_deepseek_complete(prompt, max_tokens=800, temperature=None, top_p=None, system_prompt=None):
        captured_prompt["prompt"] = prompt
        return "stubbed response"

    def fake_gpt5_complete(prompt, max_tokens=800, temperature=None, top_p=None, system_prompt=None):
        captured_prompt["prompt"] = prompt
        return "stubbed response"

    monkeypatch.setattr(llm_router, "_yandex_complete", fake_yandex_complete)
    monkeypatch.setattr(llm_router, "_deepseek_complete", fake_deepseek_complete)
    monkeypatch.setattr(llm_router, "_gpt5_complete", fake_gpt5_complete)
    monkeypatch.setattr(llm_router, "DEFAULT_LLM", "YANDEX")

    context = [
        make_context_document(
            title="Документ без ссылки",
            text="Содержимое документа",
            url=None,
        )
    ]

    result = llm_router.generate_answer("Вопрос?", context)

    assert isinstance(result, dict)
    assert result["answer_markdown"] == "stubbed response"
    assert result["sources"] == []
    assert result["meta"]["provider"] == "YANDEX"

    if "prompt" in captured_prompt:
        assert "None" not in captured_prompt["prompt"]


def test_apply_url_whitelist_filters_links(monkeypatch):
    llm_router = load_llm_router(monkeypatch)

    sources = [make_source(title="Ok", url=REFERENCE_URLS["allowed"])]
    text = (
        f"Смотрите [док]({REFERENCE_URLS['allowed']}) и [фейк](https://bad.example.com). "
        f"Также есть {REFERENCE_URLS['evil']}"
    )

    sanitized = llm_router.apply_url_whitelist(text, sources)

    assert REFERENCE_URLS["allowed"] in sanitized
    assert "https://bad.example.com" not in sanitized
    assert REFERENCE_URLS["evil"] not in sanitized
    assert "[фейк]" not in sanitized
