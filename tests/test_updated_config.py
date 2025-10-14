"""
Тесты для актуальной конфигурации приложения и реестра источников.

Ранее здесь проверялись вспомогательные функции ingestion.run, которые были
удалены в рамках рефакторинга. Теперь фокусируемся на реальном объекте CONFIG
и SourcesRegistry, которые используются сервисом.
"""

from __future__ import annotations

import pytest

from app.config import CONFIG, SourcesRegistry, SourceConfig, SourceType
from app.config.sources_config import extract_url_metadata

pytestmark = pytest.mark.unit


def test_config_contains_adaptive_chunking_settings():
    """CONFIG должен содержать параметры адаптивного чанкера, используемые пайплайном."""
    assert CONFIG.adaptive_medium_size > 0
    assert CONFIG.adaptive_long_size > 0
    assert CONFIG.adaptive_medium_overlap >= 0
    assert CONFIG.chunk_strategy in {"adaptive", "simple"}


def test_sources_registry_has_default_edna_source():
    """По умолчанию в реестре зарегистрирован источник edna_docs."""
    registry = SourcesRegistry()
    source = registry._sources["edna_docs"]  # noqa: SLF001
    assert source.base_url == "https://docs-chatcenter.edna.ru/"
    assert source.source_type == SourceType.DOCS_SITE
    assert "https://docs-chatcenter.edna.ru/docs/start/" in source.seed_urls
    assert source.strategy == "jina"


def test_sources_registry_register_custom_source():
    """Можно зарегистрировать новый источник с корректной конфигурацией."""
    registry = SourcesRegistry()
    custom = SourceConfig(
        name="local_docs",
        base_url="https://docs.example.com/",
        source_type=SourceType.DOCS_SITE,
        strategy="markdown",
        use_cache=False,
        seed_urls=["https://docs.example.com/docs/intro"],
    )
    registry.register(custom)
    retrieved = registry._sources["local_docs"]  # noqa: SLF001 - тестирует внутреннее состояние
    assert retrieved.strategy == "markdown"
    assert retrieved.use_cache is False


def test_sources_registry_validation_rejects_invalid_url():
    """Некорректный base_url приводит к ValueError."""
    registry = SourcesRegistry()
    with pytest.raises(ValueError):
        registry.register(
            SourceConfig(
                name="bad",
                base_url="ftp://invalid",
                source_type=SourceType.EXTERNAL,
            )
        )


@pytest.mark.parametrize(
    "url,expected_section",
    [
        ("https://docs-chatcenter.edna.ru/docs/agent/routing", "agent"),
        ("https://docs-chatcenter.edna.ru/docs/admin/setup", "admin"),
        ("https://docs-chatcenter.edna.ru/blog/release", "changelog"),
    ],
)
def test_extract_url_metadata_sections(url, expected_section):
    metadata = extract_url_metadata(url)
    assert metadata["section"] == expected_section
    assert metadata["url"] == url
