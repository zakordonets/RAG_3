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
        parsed = parser.parse(url, raw_content)

        # Обогащаем метаданные типом контента для дальнейшего использования
        if parsed.metadata is None:
            parsed.metadata = {}
        parsed.metadata.setdefault('content_type', content_type)

        return parsed

    def _detect_content_type(self, content: str, strategy: str) -> str:
        normalized_strategy = (strategy or '').strip().lower()

        if normalized_strategy in ('jina', 'jina_reader'):
            return 'jina'
        if normalized_strategy == 'markdown':
            return 'markdown'
        if normalized_strategy == 'html':
            return 'html'
        if normalized_strategy == 'auto':
            normalized_strategy = ''

        # Нормализуем контент, убирая лидирующие пробелы, БОМ и переносы строк
        normalized = (content or '').lstrip('\ufeff \n\r\t')
        normalized_lower = normalized.lower()

        if normalized.startswith("Title:") and "URL Source:" in normalized:
            return 'jina'
        if normalized_lower.startswith("<!doctype html") or normalized_lower.startswith("<html") or '<html' in normalized_lower:
            return 'html'
        if normalized.startswith("#"):
            return 'markdown'
        if normalized.startswith("---"):
            return 'markdown'
        if '<' not in normalized[:500] and '>' not in normalized[:500] and '\n' in normalized:
            return 'markdown'
        return 'html'
