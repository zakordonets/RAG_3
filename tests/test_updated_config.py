"""
Тесты для актуальной конфигурации приложения и основной схемы ingestion.

Покрываем три аспекта:
1. CONFIG (AppConfig) содержит ожидаемые параметры адаптивного чанкера.
2. ingestion/config.yaml описывает ключевые источники (chatcenter docs + SDK docs).
3. Утилита извлечения метаданных из URL возвращает корректные section/role.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.config import CONFIG
from app.utils import extract_url_metadata
from ingestion.run import load_sources_from_config

pytestmark = pytest.mark.unit


def test_config_contains_adaptive_chunking_settings():
    """CONFIG должен содержать параметры адаптивного чанкера, используемые пайплайном."""
    assert CONFIG.adaptive_medium_size > 0
    assert CONFIG.adaptive_long_size > 0
    assert CONFIG.adaptive_medium_overlap >= 0
    assert CONFIG.chunk_strategy in {"adaptive", "simple"}


def test_default_ingestion_config_includes_required_sources():
    """
    ingestion/config.yaml должен описывать базовые источники:
    - пользовательскую документацию ChatCenter;
    - SDK документацию.
    """
    config_path = Path("ingestion/config.yaml")
    assert config_path.exists()

    sources = load_sources_from_config(str(config_path))
    source_names = {src["name"] for src in sources}

    assert "docusaurus" in source_names
    assert "docusaurus_sdk" in source_names

    sdk_source = next(src for src in sources if src["name"] == "docusaurus_sdk")
    cfg = sdk_source.get("config", {})
    top_level_meta = cfg.get("top_level_meta", {})
    metadata = cfg.get("metadata", {})
    assert "android" in top_level_meta and "ios" in top_level_meta
    assert all(entry.get("product") == "sdk" for entry in top_level_meta.values())
    assert metadata.get("domain") == "sdk_docs"
    assert metadata.get("platform_by_dir")


@pytest.mark.parametrize(
    "url,expected_section,expected_role",
    [
        ("https://docs-chatcenter.edna.ru/docs/agent/routing", "agent", "agent"),
        ("https://docs-chatcenter.edna.ru/docs/api/messages", "api", "integrator"),
        ("https://docs-chatcenter.edna.ru/blog/release-6.15", "changelog", "all"),
    ],
)
def test_extract_url_metadata_sections(url: str, expected_section: str, expected_role: str):
    metadata = extract_url_metadata(url)
    assert metadata["section"] == expected_section
    assert metadata["user_role"] == expected_role
    assert metadata["url"] == url
