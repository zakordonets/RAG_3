from __future__ import annotations

from typing import Dict, Any

from ingestion.processors.base import ProcessedPage
from ingestion.processors.jina_parser import JinaParser
from ingestion.processors.html_parser import HTMLParser
from ingestion.processors.markdown_parser import MarkdownParser


class ContentProcessor:
    """Единая точка обработки контента со специализированными парсерами."""

    def __init__(self) -> None:
        self.parsers = {
            'jina': JinaParser(),
            'jina_reader': JinaParser(),
            'html': HTMLParser(),
            'markdown': MarkdownParser(),
        }

    def process(self, raw_content: str, url: str, strategy: str = "auto") -> ProcessedPage:
        content_type = self._detect_content_type(raw_content, strategy)
        parser = self.parsers.get(content_type, self.parsers['html'])
        return parser.parse(url, raw_content)

    def _detect_content_type(self, content: str, strategy: str) -> str:
        if strategy in ('jina', 'jina_reader'):
            return 'jina'
        
        # Нормализуем контент, убирая лидирующие пробелы, БОМ и переносы строк
        normalized = content.lstrip('\ufeff \n\r\t')
        
        if normalized.startswith("Title:") and "URL Source:" in normalized:
            return 'jina'
        if normalized.startswith("<!DOCTYPE html") or normalized.startswith("<html"):
            return 'html'
        if normalized.startswith("#"):
            return 'markdown'
        return 'html'
