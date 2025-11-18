import tempfile
from pathlib import Path

from app.retrieval.theme_router import ThemesProvider, route_query, Theme
from app.retrieval import ThemeRoutingResult


def _make_temp_themes(tmp_path: Path) -> Path:
    cfg = """
themes:
  sdk_android:
    display_name: "SDK для Android"
    domain: "sdk_docs"
    section: "sdk"
    platform: "android"
    role: "integrator"
  user_admin:
    display_name: "АРМ администратора"
    domain: "chatcenter_user_docs"
    section: "admin"
    role: "administrator"
"""
    config_path = tmp_path / "themes.yaml"
    config_path.write_text(cfg, encoding="utf-8")
    return config_path


def test_themes_provider_loads(tmp_path: Path):
    cfg_path = _make_temp_themes(tmp_path)
    provider = ThemesProvider(config_path=cfg_path)
    themes = provider.list_themes()
    assert len(themes) == 2
    assert provider.get_theme("sdk_android").platform == "android"


def test_route_query_selects_sdk_theme(tmp_path: Path, monkeypatch):
    cfg_path = _make_temp_themes(tmp_path)
    provider = ThemesProvider(config_path=cfg_path)
    monkeypatch.setattr("app.retrieval.theme_router.THEMES_PROVIDER", provider)

    result = route_query("как подключить sdk android", user_metadata=None)
    assert isinstance(result, dict)
    assert result["primary_theme"] == "sdk_android"
    assert result["requires_disambiguation"] is False
