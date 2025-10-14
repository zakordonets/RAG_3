"""
Тесты обновлённого пайплайна загрузки/нормализации контента.

Исторически здесь проверялся старый `UniversalLoader`. После крупного
рефакторинга ingestion-пайплайн построен вокруг Parser → Normalizer →
UniversalChunker и специализированного обработчика markdown. Тесты
адаптированы под новую архитектуру и покрывают ключевые сценарии:

* определение формата документа;
* обработка markdown через `process_markdown`;
* извлечение метаданных из URL;
* базовый прогон через `UnifiedChunkerStep`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.adapters.base import ParsedDoc, RawDoc
from ingestion.normalizers.base import BaseNormalizer, Parser
from ingestion.pipeline.chunker import UnifiedChunkerStep
from ingestion.processors.docusaurus_markdown_processor import process_markdown
from app.config.sources_config import extract_url_metadata

pytestmark = pytest.mark.integration


class TestParserDetection:
    """Проверяем, что Parser корректно определяет формат документа."""

    def setup_method(self) -> None:
        self.parser = Parser()

    def test_detects_markdown_by_extension(self):
        raw = RawDoc(uri="file:///tmp/doc.md", bytes=b"# Title\n\nContent", meta={})
        parsed = self.parser.process(raw)
        assert parsed.format == "markdown"
        assert parsed.metadata["uri"].endswith("doc.md")

    def test_detects_html_by_signature(self):
        raw = RawDoc(uri="file:///tmp/page.html", bytes=b"<!DOCTYPE html><html><body>Hi</body></html>", meta={})
        parsed = self.parser.process(raw)
        assert parsed.format == "html"
        assert "Hi" in parsed.text

    def test_falls_back_to_text(self):
        raw = RawDoc(uri="file:///tmp/readme.txt", bytes=b"plain text content", meta={})
        parsed = self.parser.process(raw)
        assert parsed.format == "text"
        assert parsed.text == "plain text content"


class TestProcessMarkdown:
    """Тесты для обработчика Docusaurus markdown."""

    def test_process_markdown_extracts_metadata_and_chunks(self):
        raw_text = """---
title: "Настройка виджета"
category: "АРМ_adm"
---

# Настройка виджета

Описание функций.
"""
        dir_meta = {
            "labels": "Администратор|Widgets",
            "breadcrumbs": "Docs > Admin > Widgets",
            "current_label": "Widgets",
        }
        doc_meta, chunks = process_markdown(
            raw_text,
            abs_path=Path("/docs/admin/widget.md"),
            rel_path="docs/admin/widget.md",
            site_url="https://docs.example.com/docs/admin/widget",
            dir_meta=dir_meta,
            default_category="UNSPECIFIED",
        )

        assert doc_meta["title"] == "Настройка виджета"
        assert doc_meta["category"] == "АРМ_adm"
        assert doc_meta["group_labels"] == ["Администратор", "Widgets"]
        assert doc_meta["groups_path"] == ["Docs", "Admin", "Widgets"]
        assert len(chunks) >= 1
        assert all(chunk.payload["source"] == "docusaurus" for chunk in chunks)

    def test_process_markdown_without_frontmatter_uses_defaults(self):
        raw_text = "# Без фронтматтера\n\nКонтент без указания category."
        doc_meta, chunks = process_markdown(
            raw_text,
            abs_path=Path("/docs/agent/overview.md"),
            rel_path="docs/agent/overview.md",
            site_url="https://docs.example.com/docs/agent/overview",
            dir_meta={},
        )

        assert doc_meta["title"] == "overview"
        assert doc_meta["category"] == "UNSPECIFIED"
        assert doc_meta["group_labels"] == []
        assert doc_meta["groups_path"] == []
        assert len(chunks) >= 1


class TestUrlMetadataExtraction:
    """Извлечение метаданных из URL в новом SourcesRegistry."""

    @pytest.mark.parametrize(
        "url,expected_section,expected_role",
        [
            ("https://docs-chatcenter.edna.ru/docs/agent/routing", "agent", "agent"),
            ("https://docs-chatcenter.edna.ru/docs/api/messages", "api", "integrator"),
            ("https://docs-chatcenter.edna.ru/blog/release-6.15", "changelog", "all"),
        ],
    )
    def test_extract_url_metadata_assigns_section_and_role(self, url, expected_section, expected_role):
        metadata = extract_url_metadata(url)
        assert metadata["section"] == expected_section
        assert metadata["user_role"] == expected_role
        assert metadata["url"] == url


class TestUnifiedChunkerStep:
    """Проверяем, что шаг пайплайна корректно формирует чанки из ParsedDoc."""

    def test_chunker_creates_fallback_for_empty_text(self):
        chunker = UnifiedChunkerStep()
        parsed = ParsedDoc(
            text="",
            format="markdown",
            frontmatter=None,
            metadata={"canonical_url": "https://example.com/docs/empty"},
        )
        chunks = chunker.process(parsed)
        assert chunks == []

    def test_chunker_creates_structured_chunks(self):
        chunker = UnifiedChunkerStep(max_tokens=200, min_tokens=50, overlap_base=20)
        parsed = ParsedDoc(
            text="# Заголовок\n\n" + "Это текст раздела. " * 80,
            format="markdown",
            frontmatter={"title": "Документ"},
            metadata={
                "canonical_url": "https://example.com/docs/guide",
                "source": "test",
                "content_type": "markdown",
                "title": "Документ",
            },
        )
        chunks = chunker.process(parsed)
        assert len(chunks) >= 1
        first_chunk = chunks[0]
        assert "text" in first_chunk and "payload" in first_chunk
        assert first_chunk["payload"]["chunk_index"] == 0
        assert first_chunk["payload"]["format"] == "markdown"
        assert first_chunk["payload"]["chunking_strategy"] == "universal"


class TestBaseNormalizer:
    """Убеждаемся, что базовый нормализатор чистит текст без потери содержания."""

    def test_normalizer_trims_extra_whitespace(self):
        doc = ParsedDoc(
            text="  Строка 1   \n\n\nСтрока 2  ",
            format="text",
            metadata={"source": "test"},
        )
        normalizer = BaseNormalizer()
        normalized = normalizer.process(doc)
        lines = normalized.text.splitlines()
        assert lines[0].strip() == "Строка 1"
        assert lines[-1].strip() == "Строка 2"
        assert normalized.metadata["normalized"] is True
        assert normalized.metadata["normalizer"] == "base"
