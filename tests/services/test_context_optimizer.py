from app.services.core.context_optimizer import (
    ContextOptimizer,
    extract_markdown_section,
)


def test_extract_markdown_section_returns_channels_block():
    markdown = (
        "# Введение\n\n"
        "## Каналы\n"
        "- Канал A\n"
        "- Канал B\n\n"
        "## Дополнительно\n"
        "Текст про другое"
    )

    section = extract_markdown_section(markdown)

    assert section.startswith("## Каналы")
    assert "Канал A" in section
    assert "Канал B" in section
    assert "## Дополнительно" not in section


def test_optimize_context_list_intent_returns_channels_section():
    optimizer = ContextOptimizer()
    markdown = (
        "# Документ\n\n"
        "## Каналы\n"
        "- Канал 1\n"
        "- Канал 2\n\n"
        "## Прочее\n"
        "Непрофильный текст"
    )

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
    optimizer.max_context_tokens = 40
    doc = {
        "payload": {
            "title": "Листы",
            "text": "- один\n- два\n- три\n\nСледующий абзац с подробным описанием." * 3,
        }
    }

    result = optimizer.optimize_context("что такое", [doc])

    assert len(result) == 1
    text = result[0]["payload"]["text"]
    assert "- один" in text
    assert "- два" in text
