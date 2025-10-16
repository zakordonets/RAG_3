import pytest

from adapters.telegram_adapter import render_html, split_for_telegram
from ..fixtures.data_samples import MARKDOWN_WITH_CODE_AND_ANGLES, REFERENCE_URLS
from ..fixtures.factories import make_source

pytestmark = pytest.mark.unit


def test_render_html_renders_markdown_and_sources():
    markdown = MARKDOWN_WITH_CODE_AND_ANGLES
    sources = [make_source()]

    html = render_html(markdown, sources)

    assert "<b>Заголовок</b>" in html
    assert "&lt;скобками&gt;" in html
    assert "<pre><code>" in html and "print('ok')" in html
    assert "<b>Источники:</b>" in html
    assert f'<a href="{REFERENCE_URLS["doc_source"]}"' in html
    assert f'<a href="{REFERENCE_URLS["evil"]}"' in html
    assert "<p>" not in html


def test_split_for_telegram_respects_limit():
    segment = "Секция" * 20
    long_html = "<br>".join([segment] * 120)

    parts = split_for_telegram(long_html, limit=4096)

    assert len(parts) >= 2
    assert all(len(part) <= 4096 for part in parts)
