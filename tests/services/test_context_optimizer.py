import pytest

from app.services.core.context_optimizer import (
    ContextOptimizer,
    extract_markdown_section,
)
from ..fixtures.data_samples import (
    MARKDOWN_WITH_CHANNELS,
    MARKDOWN_WITH_CHANNELS_AND_FALLBACK,
    MARKDOWN_WITH_LIST_PARAGRAPH,
)

pytestmark = pytest.mark.unit


def test_extract_markdown_section_returns_channels_block():
    markdown = MARKDOWN_WITH_CHANNELS.replace("Канал 1", "Канал A").replace("Канал 2", "Канал B")

    section = extract_markdown_section(markdown)

    assert section.startswith("## Каналы")
    assert "Канал A" in section
    assert "Канал B" in section
    assert "## Дополнительно" not in section


def test_optimize_context_list_intent_returns_channels_section():
    optimizer = ContextOptimizer()
    markdown = MARKDOWN_WITH_CHANNELS_AND_FALLBACK

    documents = [
        {"payload": {"title": "Тест", "text": markdown, "url": "https://example.com"}},
        {"payload": {"title": "Второй", "text": "## Каналы\n- Другой"}},
    ]

    result = optimizer.optimize_context("Какие каналы поддерживаются?", documents)

    assert len(result) == 1
    payload = result[0]["payload"]
    assert payload["list_mode"] is True
    assert payload["text"].startswith("## Каналы")
    assert "Канал 1" in payload["text"]
    assert "Прочее" not in payload["text"]


def test_optimize_context_preserves_list_markers_on_trim():
    optimizer = ContextOptimizer()
    markdown = MARKDOWN_WITH_LIST_PARAGRAPH * 3

    truncated = optimizer._truncate_by_paragraphs(markdown, max_chars=80)  # pylint: disable=protected-access

    assert "- один" in truncated
    assert "- два" in truncated
