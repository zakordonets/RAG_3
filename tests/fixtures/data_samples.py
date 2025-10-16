"""Literal samples reused across tests to avoid ad-hoc duplication."""

from __future__ import annotations

# Common reference URLs used throughout the suite.
REFERENCE_URLS: dict[str, str] = {
    "guide": "https://example.org/docs/start/overview",
    "api": "https://example.org/docs/api/messages",
    "faq": "https://example.org/faq",
    "changelog": "https://example.org/blog/release-6-16",
    "admin": "https://example.org/docs/admin/widget",
    "supervisor": "https://example.org/docs/supervisor/threadcontrol",
    "agent": "https://example.org/docs/agent/routing",
    "doc_source": "https://doc.example",
    "allowed": "https://allowed.example.com/path",
    "evil": "https://evil.example",
}

# Canonical markdown snippets.
MARKDOWN_SIMPLE: str = "# Heading\n\nPage contents.\n"

MARKDOWN_WITH_CHANNELS: str = (
    "# Введение\n\n"
    "## Каналы\n"
    "- Канал 1\n"
    "- Канал 2\n\n"
    "## Дополнительно\n"
    "Непрофильный текст"
)

MARKDOWN_WITH_CHANNELS_AND_FALLBACK: str = (
    "# Документ\n\n"
    "## Каналы\n"
    "- Канал 1\n"
    "- Канал 2\n\n"
    "## Прочее\n"
    "Непрофильный текст"
)

MARKDOWN_WITH_LIST_PARAGRAPH: str = (
    "- один\n- два\n- три\n\nСледующий абзац с подробным описанием."
)

MARKDOWN_WITH_CODE_AND_ANGLES: str = (
    "### Заголовок\n\n"
    "Текст с <скобками> и ссылкой без whitelista [ссылка](https://evil.example).\n\n"
    "```\nprint('ok')\n```"
)

# HTML sample used in ingestion/parsing tests.
HTML_SAMPLE: str = """<!DOCTYPE html>
<html>
<head>
    <title>Demo Page</title>
</head>
<body>
    <h1>Heading</h1>
    <p>Page contents.</p>
</body>
</html>"""

# Template for Jina Reader-like payloads and default literal.
JINA_READER_TEMPLATE: str = """Title: {title}
URL Source: {url}
Content Length: {length}
Language Detected: {language}
Published Time: {published}
Images: {images}
Links: {links}
Markdown Content:

{content}
"""

DEFAULT_JINA_CONTENT: str = JINA_READER_TEMPLATE.format(
    title="Demo Page",
    url=REFERENCE_URLS["guide"],
    length=2456,
    language="English",
    published="2024-07-24T10:30:00Z",
    images=3,
    links=12,
    content=MARKDOWN_SIMPLE.strip(),
)

# Canonical chunk payload skeleton reused across indexing tests.
BASE_CHUNK_PAYLOAD: dict[str, str | int] = {
    "chunk_id": "doc-0#0",
    "title": "Demo Page",
    "category": "GENERAL",
    "source": "tests",
    "content_type": "markdown",
}

# Context payload used to ensure URL-less entries stay stable.
BASE_CONTEXT_PAYLOAD: dict[str, str] = {
    "title": "Документ без ссылки",
    "text": "Содержимое документа",
}

# Typical source entry for rendering tests.
DEFAULT_SOURCE: dict[str, str] = {
    "title": "Док",
    "url": REFERENCE_URLS["doc_source"],
}

__all__ = [
    "REFERENCE_URLS",
    "MARKDOWN_SIMPLE",
    "MARKDOWN_WITH_CHANNELS",
    "MARKDOWN_WITH_CHANNELS_AND_FALLBACK",
    "MARKDOWN_WITH_LIST_PARAGRAPH",
    "MARKDOWN_WITH_CODE_AND_ANGLES",
    "HTML_SAMPLE",
    "JINA_READER_TEMPLATE",
    "DEFAULT_JINA_CONTENT",
    "BASE_CHUNK_PAYLOAD",
    "BASE_CONTEXT_PAYLOAD",
    "DEFAULT_SOURCE",
]
