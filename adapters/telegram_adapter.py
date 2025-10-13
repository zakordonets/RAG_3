from __future__ import annotations

import html
import re
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore[import-untyped]
from loguru import logger
from mistletoe import markdown  # type: ignore[import-untyped]

from app.config import CONFIG

BOT_TOKEN = CONFIG.telegram_bot_token
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DEFAULT_LIMIT = 4096

_DEFAULT_ALLOWED_TAGS = {
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ins",
    "s",
    "strike",
    "del",
    "a",
    "code",
    "pre",
    "blockquote",
}
_DEFAULT_ALLOWED_ATTRS = {"a": {"href"}}
_ALLOWED_PROTOCOLS = {"http", "https"}


def _allowed_tags() -> set[str]:
    if CONFIG.telegram_html_allowlist:
        raw_tags = [tag.strip() for tag in CONFIG.telegram_html_allowlist.split(",") if tag.strip()]
        return set(raw_tags)
    return set(_DEFAULT_ALLOWED_TAGS)


def _sanitize_html_fragment(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "lxml")
    allowed_tags = _allowed_tags()
    allowed_attrs = _DEFAULT_ALLOWED_ATTRS

    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
            continue

        attrs = dict(tag.attrs)
        if not attrs:
            continue

        for attr in list(attrs.keys()):
            if tag.name not in allowed_attrs or attr not in allowed_attrs[tag.name]:
                del tag.attrs[attr]
                continue

            value = attrs[attr]
            if tag.name == "a":
                if isinstance(value, list):
                    value = value[0] if value else ""
                parsed = urlparse(value)
                if parsed.scheme.lower() not in _ALLOWED_PROTOCOLS:
                    logger.warning(f"Dropping non-http(s) link: {value}")
                    del tag.attrs[attr]

    # Replace <br> and <br/> tags with newlines (Telegram doesn't support <br>)
    if soup.body:
        sanitized = soup.body.decode_contents()
    else:
        sanitized = str(soup)
    sanitized = sanitized.replace("<br/>", "\n").replace("<br>", "\n")
    return sanitized


def _render_blockquote(tag: Tag) -> str:
    inner = "".join(_render_node(child) for child in tag.children)
    return f"<blockquote>{inner}</blockquote>"


def _render_heading(tag: Tag) -> str:
    inner = "".join(_render_node(child) for child in tag.children)
    # Ensure trailing newline
    return f"<b>{inner}</b>\n"


def _render_list(tag: Tag, ordered: bool) -> str:
    lines: List[str] = []
    for index, item in enumerate(tag.find_all("li", recursive=False), start=1):
        line = _render_list_item(item, prefix=f"{index}. " if ordered else "• ")
        if line:
            lines.append(line)
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _render_list_item(tag: Tag, prefix: str) -> str:
    parts: List[str] = []
    for child in tag.children:
        rendered = _render_node(child)
        if not rendered:
            continue
        parts.append(rendered)

    line = "".join(parts).strip()
    if not line:
        return ""
    return f"{html.escape(prefix)}{line}"


def _render_table(tag: Tag) -> str:
    rows: List[str] = []
    for row in tag.find_all("tr", recursive=False):
        cells: List[str] = []
        for cell in row.find_all(["th", "td"], recursive=False):
            cell_content = "".join(_render_node(child) for child in cell.children)
            cells.append(cell_content.strip())
        if cells:
            rows.append(" | ".join(cells))
    if not rows:
        return ""
    return "\n".join(rows) + "\n"


def _render_paragraph(tag: Tag) -> str:
    inner = "".join(_render_node(child) for child in tag.children)
    stripped = inner.strip()
    if not stripped:
        return ""
    return f"{stripped}\n"


def _render_node(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return html.escape(str(node))

    name = node.name
    if not name:
        return ""

    if name in ("strong", "b"):
        inner = "".join(_render_node(child) for child in node.children)
        return f"<strong>{inner}</strong>"
    if name in ("em", "i"):
        inner = "".join(_render_node(child) for child in node.children)
        return f"<em>{inner}</em>"
    if name in ("u", "ins"):
        inner = "".join(_render_node(child) for child in node.children)
        return f"<u>{inner}</u>"
    if name in ("s", "strike", "del"):
        inner = "".join(_render_node(child) for child in node.children)
        return f"<s>{inner}</s>"
    if name == "a":
        href = node.get("href", "")
        inner = "".join(_render_node(child) for child in node.children) or html.escape(href)
        escaped_href = html.escape(href, quote=True)
        return f'<a href="{escaped_href}">{inner}</a>'
    if name == "code":
        inner = "".join(_render_node(child) for child in node.children)
        return f"<code>{inner}</code>"
    if name == "pre":
        inner = "".join(_render_node(child) for child in node.children)
        return f"<pre>{inner}</pre>"
    if name == "blockquote":
        return _render_blockquote(node)
    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return _render_heading(node)
    if name == "ul":
        return _render_list(node, ordered=False)
    if name == "ol":
        return _render_list(node, ordered=True)
    if name == "li":
        return _render_list_item(node, prefix="• ")
    if name == "table":
        return _render_table(node)
    if name in ("tbody", "thead"):
        return "".join(_render_node(child) for child in node.children)
    if name == "tr":
        return "\n".join(_render_node(child) for child in node.children if _render_node(child))
    if name in ("th", "td"):
        return "".join(_render_node(child) for child in node.children)
    if name == "p":
        return _render_paragraph(node)
    if name == "br":
        return "\n"

    # Unsupported tag: render children recursively without the tag
    return "".join(_render_node(child) for child in node.children)


def _markdown_to_html(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    raw_html = markdown(markdown_text)
    soup = BeautifulSoup(raw_html, "lxml")
    rendered = "".join(_render_node(child) for child in soup.body.contents) if soup.body else "".join(
        _render_node(child) for child in soup.contents
    )

    # Collapse multiple consecutive newlines to at most two to avoid runaway length
    rendered = re.sub(r"(\n){3,}", "\n\n", rendered)
    return rendered.strip()


def _normalize_sources(sources: Optional[Iterable[dict]]) -> List[dict]:
    normalized = []
    if not sources:
        return normalized
    for source in sources:
        if not isinstance(source, dict):
            continue
        title = str(source.get("title") or "").strip()
        url = str(source.get("url") or "").strip()
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme.lower() not in _ALLOWED_PROTOCOLS:
            logger.warning(f"Skipping non-http(s) source link: {url}")
            continue
        normalized.append({"title": title or "Источник", "url": url})
        if len(normalized) == 5:
            break
    return normalized


def _append_sources_block(html_body: str, sources: List[dict]) -> str:
    if not sources:
        return html_body

    parts = [html_body] if html_body else []
    if html_body and not html_body.endswith("\n"):
        parts.append("\n")
    parts.append("<b>Источники:</b>\n")

    for index, source in enumerate(sources, start=1):
        title = html.escape(source.get("title", "Источник"))
        url = html.escape(source.get("url", ""))
        parts.append(f'{index}. <a href="{url}">{title}</a>\n')

    return "".join(parts)


def _collect_links(html_fragment: str) -> List[str]:
    soup = BeautifulSoup(html_fragment, "lxml")
    links = []
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if href:
            links.append(href)
    return links


def render_html(answer_markdown: str, sources: list[dict]) -> str:
    body = _markdown_to_html(answer_markdown or "")
    normalized_sources = _normalize_sources(sources)
    with_sources = _append_sources_block(body, normalized_sources)
    sanitized = _sanitize_html_fragment(with_sources)
    whitelisted_links = {src["url"] for src in normalized_sources}
    extras = [href for href in _collect_links(sanitized) if href not in whitelisted_links]
    logger.info(
        f"TelegramAdapter.render_html: len={len(sanitized)}, sources={len(normalized_sources)}, "
        f"extra_links={len(extras)}"
    )
    if extras:
        logger.warning(f"Found links outside whitelist: {extras}")
    return sanitized


def split_for_telegram(html_text: str, limit: int = DEFAULT_LIMIT) -> List[str]:
    if not html_text:
        return [""]

    if len(html_text) <= limit:
        logger.info(f"TelegramAdapter.split: single chunk len={len(html_text)}")
        return [html_text]

    blocks = html_text.split("\n\n")
    parts: List[str] = []
    current = ""

    def flush_current():
        nonlocal current
        if current:
            parts.append(current)
            current = ""

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        candidate = f"{current}\n\n{block}" if current else block

        if len(candidate) <= limit:
            current = candidate
            continue

        flush_current()

        if len(block) <= limit:
            current = block
            continue

        # Need to split block by single newlines or hard length
        segments = block.split("\n")
        segment_buffer = ""
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            candidate_segment = f"{segment_buffer}\n{segment}" if segment_buffer else segment
            if len(candidate_segment) <= limit:
                segment_buffer = candidate_segment
                continue
            if segment_buffer:
                parts.append(segment_buffer)
            if len(segment) <= limit:
                segment_buffer = segment
                continue
            # Fallback hard split
            for idx in range(0, len(segment), limit):
                parts.append(segment[idx : idx + limit])
            segment_buffer = ""
        if segment_buffer:
            parts.append(segment_buffer)
        current = ""

    flush_current()
    logger.info(f"TelegramAdapter.split: parts={len(parts)}, limit={limit}")
    return parts


def send(chat_id: str, html_parts: List[str], reply_markup: Optional[dict] = None) -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Telegram bot token is not configured")

    total_len = sum(len(part) for part in html_parts)
    logger.info(
        f"TelegramAdapter.send: chat_id={chat_id}, total_len={total_len}, parts={len(html_parts)}, "
        f"reply_markup={'yes' if reply_markup else 'no'}"
    )

    total_parts = len(html_parts)

    for index, part in enumerate(html_parts, start=1):
        payload: dict = {
            "chat_id": chat_id,
            "text": part,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup and index == total_parts:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=30)
        except Exception as exc:
            logger.error(f"TelegramAdapter.send: request failed part={index}/{len(html_parts)} error={exc}")
            raise

        if response.status_code != 200:
            body = response.text[:300]
            logger.error(
                f"TelegramAdapter.send: Telegram error part={index}/{len(html_parts)} "
                f"status={response.status_code} body={body}"
            )
            try:
                data = response.json()
            except Exception:
                data = {}
            code = data.get("error_code") if isinstance(data, dict) else None
            description = data.get("description") if isinstance(data, dict) else None
            logger.error(
                f"TelegramAdapter.send: error_code={code}, description={description}, "
                f"html_preview={part[:300]}"
            )
            response.raise_for_status()
        else:
            logger.debug(
                f"TelegramAdapter.send: part={index}/{len(html_parts)} "
                f"len={len(part)} sent successfully"
            )
