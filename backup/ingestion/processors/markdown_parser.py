from __future__ import annotations

import re
from ingestion.processors.base import BaseParser, ProcessedPage


class MarkdownParser(BaseParser):
    """Парсер Markdown контента (упрощенный)."""

    def parse(self, url: str, content: str) -> ProcessedPage:
        lines = content.split('\n')
        title = self._extract_title(lines) or "Untitled"
        cleaned = self._clean_markdown(content)

        metadata = {}

        return ProcessedPage(
            url=url,
            title=title,
            content=cleaned,
            page_type=self._detect_page_type(url),
            metadata=metadata
        )

    def _extract_title(self, lines: list[str]) -> str:
        for line in lines:
            if line.startswith('# '):
                return line[2:].strip()
        return ""

    def _clean_markdown(self, content: str) -> str:
        # Заголовки
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)
        # Жирный/курсив
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
        content = re.sub(r'\*(.*?)\*', r'\1', content)
        # Ссылки
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        return content.strip()
