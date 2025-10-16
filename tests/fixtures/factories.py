"""Factory helpers wrapping literal samples to keep tests concise."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from .data_samples import (
    BASE_CHUNK_PAYLOAD,
    BASE_CONTEXT_PAYLOAD,
    DEFAULT_JINA_CONTENT,
    DEFAULT_SOURCE,
    HTML_SAMPLE,
    JINA_READER_TEMPLATE,
    MARKDOWN_SIMPLE,
    REFERENCE_URLS,
)


def clone_sample(sample: Any) -> Any:
    """Return a deep copy of the provided sample to avoid accidental mutation."""
    return deepcopy(sample)


def make_markdown_content(
    title: str = "Heading",
    body: str = "Page contents.",
    include_subheading: bool = True,
) -> str:
    """Compose a markdown snippet with optional subheading section."""
    lines: list[str] = [f"# {title}", "", body]
    if include_subheading:
        lines += ["", "## Subheading", "", "More contents."]
    return "\n".join(lines) + "\n"


def make_html_content(
    title: str = "Demo Page",
    body: str = "<h1>Heading</h1><p>Page contents.</p>",
) -> str:
    """Compose a minimal HTML document."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
</head>
<body>
    {body}
</body>
</html>"""


def make_jina_content(
    title: str = "Demo Page",
    url: str = REFERENCE_URLS["guide"],
    content: str = MARKDOWN_SIMPLE.strip(),
    length: int = 2456,
    language: str = "English",
    published: str = "2024-07-24T10:30:00Z",
    images: int = 3,
    links: int = 12,
) -> str:
    """Compose a text blob mimicking Jina Reader output."""
    return JINA_READER_TEMPLATE.format(
        title=title,
        url=url,
        length=length,
        language=language,
        published=published,
        images=images,
        links=links,
        content=content,
    )


def make_context_document(
    title: str = BASE_CONTEXT_PAYLOAD["title"],
    text: str = BASE_CONTEXT_PAYLOAD["text"],
    url: str | None = None,
    payload_extra: Mapping[str, Any] | None = None,
    doc_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a context entry compatible with LLM router expectations."""
    payload: dict[str, Any] = {"title": title, "text": text}
    if url is not None:
        payload["url"] = url
    if payload_extra:
        payload.update(deepcopy(payload_extra))
    document = {"payload": payload}
    if doc_extra:
        document.update(deepcopy(doc_extra))
    return document


def make_source(
    title: str = DEFAULT_SOURCE["title"],
    url: str = DEFAULT_SOURCE["url"],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a source dictionary used in answer rendering."""
    source = {"title": title, "url": url}
    if extra:
        source.update(deepcopy(extra))
    return source


def make_chunk_payload(
    chunk_id: str | None = BASE_CHUNK_PAYLOAD["chunk_id"],
    *,
    index: int | None = None,
    total: int | None = None,
    url: str | None = None,
    title: str | None = None,
    text: str | None = None,
    extras: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a chunk payload with optional metadata."""
    payload: dict[str, Any] = {}
    if chunk_id is not None:
        payload["chunk_id"] = chunk_id
    if index is not None:
        payload["chunk_index"] = index
    if total is not None:
        payload["total_chunks"] = total
    if url is not None:
        payload["canonical_url"] = url
    if title is not None:
        payload["title"] = title
    if text is not None:
        payload["text"] = text
    if extras:
        payload.update(deepcopy(extras))
    return payload


def make_chunk(
    text: str = "Test content",
    chunk_id: str | None = BASE_CHUNK_PAYLOAD["chunk_id"],
    *,
    index: int | None = None,
    total: int | None = None,
    payload_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a chunk dictionary compatible with ingestion pipeline tests."""
    payload = make_chunk_payload(
        chunk_id,
        index=index,
        total=total,
        extras=payload_extra,
    )
    return {"text": text, "payload": payload}


def make_chunks_from_texts(
    texts: Iterable[str],
    *,
    chunk_id_prefix: str = "doc",
    start_index: int = 0,
    payload_extra: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build a sequence of chunks from raw texts assigning incremental indexes."""
    texts_list = list(texts)
    total = len(texts_list)
    chunks: list[dict[str, Any]] = []
    for offset, text in enumerate(texts_list, start=start_index):
        chunk_id = f"{chunk_id_prefix}{offset}#{offset - start_index}"
        chunk = make_chunk(
            text=text,
            chunk_id=chunk_id,
            index=offset,
            total=total,
            payload_extra=payload_extra,
        )
        chunks.append(chunk)
    return chunks


__all__ = [
    "clone_sample",
    "make_chunk",
    "make_chunk_payload",
    "make_chunks_from_texts",
    "make_context_document",
    "make_html_content",
    "make_jina_content",
    "make_markdown_content",
    "make_source",
    "REFERENCE_URLS",
    "HTML_SAMPLE",
    "DEFAULT_JINA_CONTENT",
]
