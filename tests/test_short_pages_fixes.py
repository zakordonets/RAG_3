#!/usr/bin/env python3
"""
Юнит-тесты для сценариев с очень коротким контентом в новом ingestion пайплайне.

После миграции на Parser/BaseNormalizer/UniversalChunker необходимо убедиться,
что обработка коротких документов остаётся безопасной и не приводит к
исключениям. Тесты проверяют Markdown, HTML и текстовые кейсы.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from ingestion.adapters.base import ParsedDoc, RawDoc
from ingestion.normalizers.base import BaseNormalizer, Parser
from ingestion.pipeline.chunker import UnifiedChunkerStep

pytestmark = pytest.mark.unit


class TestShortContentProcessing:
    """Проверяем устойчивость пайплайна к короткому или пустому содержимому."""

    def setup_method(self) -> None:
        self.parser = Parser()
        self.normalizer = BaseNormalizer()
        self.chunker = UnifiedChunkerStep(max_tokens=128, min_tokens=32, overlap_base=16)

    def test_parser_handles_very_short_markdown(self):
        raw = RawDoc(uri="file:///tmp/short.md", bytes=b"# T\n\nHi", meta={"source": "test"})
        parsed = self.parser.process(raw)
        assert parsed.format == "markdown"
        assert parsed.text == "# T\n\nHi"

    def test_parser_handles_empty_text(self):
        raw = RawDoc(uri="file:///tmp/empty.md", bytes=b"", meta={"source": "test"})
        parsed = self.parser.process(raw)
        assert parsed.format in {"text", "markdown"}
        assert parsed.text == ""

    def test_base_normalizer_does_not_strip_everything(self):
        parsed = ParsedDoc(text="  Hello  ", format="text", metadata={"source": "test"})
        normalized = self.normalizer.process(parsed)
        assert normalized.text == "Hello"
        assert normalized.metadata["normalized"] is True

    def test_chunker_returns_empty_list_for_blank_text(self):
        parsed = ParsedDoc(
            text="",
            format="markdown",
            metadata={"canonical_url": "https://example.com/blank"},
        )
        assert self.chunker.process(parsed) == []

    def test_chunker_creates_single_chunk_for_short_text(self):
        parsed = ParsedDoc(
            text="Короткий текст без структуры.",
            format="text",
            metadata={"canonical_url": "https://example.com/short", "source": "test"},
        )
        chunks = self.chunker.process(parsed)
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk["payload"]["chunk_index"] == 0
        assert chunk["payload"]["chunking_strategy"] in {"universal", "fallback"}

    def test_html_parsing_with_short_content(self):
        html = "<html><body><h1>H</h1><p>Hi</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        parsed = ParsedDoc(
            text=text,
            format="html",
            metadata={"canonical_url": "https://example.com/html", "source": "test"},
        )
        chunks = self.chunker.process(parsed)
        assert len(chunks) == 1
        assert "H" in chunks[0]["text"]

    def test_pipeline_chain_on_short_markdown(self):
        """Полный мини-пайплайн: RawDoc -> Parser -> Normalizer -> Chunker."""
        raw = RawDoc(uri="file:///tmp/doc.md", bytes=b"# H\nMini", meta={"source": "test"})
        parsed = self.parser.process(raw)
        normalized = self.normalizer.process(parsed)
        chunks = self.chunker.process(normalized)
        assert len(chunks) == 1
        assert chunks[0]["payload"]["doc_id"]
