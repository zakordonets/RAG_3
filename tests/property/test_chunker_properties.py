from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
import sys

import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.chunking.universal_chunker import UniversalChunker


ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
LIST_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+.+$", re.MULTILINE)


@dataclass
class MarkdownDocument:
    text: str
    has_content: bool
    headings: set[str]
    list_lines: set[str]


def _normalize_line(line: str) -> str:
    return " ".join(line.strip().split())


def heading_strategy() -> st.SearchStrategy[str]:
    return st.builds(
        lambda level, title: f"{'#' * level} {title.strip()}",
        level=st.integers(min_value=1, max_value=3),
        title=st.text(alphabet=ALPHABET + " ", min_size=3, max_size=40).filter(str.strip),
    )


def paragraph_strategy() -> st.SearchStrategy[str]:
    return st.lists(
        st.text(alphabet=ALPHABET, min_size=1, max_size=12),
        min_size=3,
        max_size=8,
    ).map(lambda words: " ".join(words))


def list_block_strategy() -> st.SearchStrategy[str]:
    def build_list(items: list[str], marker: str) -> str:
        lines: list[str] = []
        for idx, item in enumerate(items, start=1):
            cleaned = item.strip()
            if not cleaned:
                cleaned = "placeholder"
            if marker == "ordered":
                lines.append(f"{idx}. {cleaned}")
            else:
                lines.append(f"{marker} {cleaned}")
        return "\n".join(lines)

    bullet_marker = st.sampled_from(["-", "*", "+"])
    ordered = st.just("ordered")

    return st.builds(
        build_list,
        items=st.lists(
            st.text(alphabet=ALPHABET + " ", min_size=1, max_size=30),
            min_size=1,
            max_size=6,
        ),
        marker=st.one_of(bullet_marker, ordered),
    )


def code_block_strategy() -> st.SearchStrategy[str]:
    def build_block(language: str, lines: list[str]) -> str:
        header = f"```{language}" if language else "```"
        safe_lines = [
            line.replace("```", "` ` `") or "pass"
            for line in lines
        ]
        return "\n".join([header, *safe_lines, "```"])

    return st.builds(
        build_block,
        language=st.sampled_from(["", "python", "bash", "json"]),
        lines=st.lists(
            st.text(alphabet=ALPHABET + " _():=,+-[]{}", min_size=1, max_size=40),
            min_size=1,
            max_size=6,
        ),
    )


@st.composite
def markdown_documents(draw: st.DrawFn) -> MarkdownDocument:
    block_strategies = st.one_of(
        heading_strategy(),
        paragraph_strategy(),
        list_block_strategy(),
        code_block_strategy(),
    )
    blocks = draw(
        st.lists(block_strategies, min_size=1, max_size=10)
    )
    text = "\n\n".join(blocks)
    assume(text.strip())

    headings = {match[1].strip() for match in re.findall(r"^(#+)\s*(.+)$", text, flags=re.MULTILINE)}
    list_lines = {_normalize_line(line) for line in LIST_PATTERN.findall(text)}

    return MarkdownDocument(
        text=text,
        has_content=bool(text.strip()),
        headings=headings,
        list_lines=list_lines,
    )


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(markdown_documents())
def test_chunker_heading_paths_reference_known_headings(document: MarkdownDocument) -> None:
    chunker = UniversalChunker(max_tokens=180, min_tokens=60, overlap_base=40)
    chunks = chunker.chunk(document.text, fmt="markdown", meta={"doc_id": "test-doc"})
    assert chunks, "Chunker should produce at least one chunk for non-empty markdown"

    for chunk in chunks:
        assert chunk.text.strip(), "Chunk text must not be empty"
        heading_path = chunk.heading_path
        if document.headings:
            assert all(
                heading in document.headings for heading in heading_path
            ), f"Heading path {heading_path} must reference headings from the source document"
        else:
            assert not heading_path, "Heading path must be empty when document has no headings"


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(markdown_documents())
def test_chunker_preserves_list_lines(document: MarkdownDocument) -> None:
    chunker = UniversalChunker(max_tokens=180, min_tokens=60, overlap_base=40)
    chunks = chunker.chunk(document.text, fmt="markdown", meta={"doc_id": "test-doc"})

    for chunk in chunks:
        chunk_list_lines = {_normalize_line(line) for line in LIST_PATTERN.findall(chunk.text)}
        assert chunk_list_lines <= document.list_lines, "Chunk should not introduce new list items"


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(markdown_documents())
def test_chunker_keeps_code_fences_balanced(document: MarkdownDocument) -> None:
    chunker = UniversalChunker(max_tokens=180, min_tokens=60, overlap_base=40)
    chunks = chunker.chunk(document.text, fmt="markdown", meta={"doc_id": "test-doc"})

    for chunk in chunks:
        fence_count = chunk.text.count("```")
        assert fence_count % 2 == 0, "Code fences must remain balanced inside each chunk"
