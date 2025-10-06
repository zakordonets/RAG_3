from __future__ import annotations

from typing import Dict, Any, List

from ingestion.processors.base import BaseParser, ProcessedPage


class JinaParser(BaseParser):
    """Оптимизированный парсер контента формата Jina Reader."""

    def parse(self, url: str, content: str) -> ProcessedPage:
        if not content:
            raise ValueError("Empty content")

        lines = content.split('\n')
        title = self._extract_title(lines)
        content_text = self._extract_content(lines)
        metadata = self._extract_metadata(lines)

        if not title:
            title = "Untitled"

        result: Dict[str, Any] = {
            'title': title,
            'content': content_text,
            **metadata
        }

        return ProcessedPage(
            url=url,
            title=result['title'],
            content=result['content'],
            page_type=self._detect_page_type(url),
            metadata=result
        )

    def _extract_title(self, lines: List[str]) -> str:
        for line in lines:
            if line.startswith("Title:"):
                title_part = line.split("Title:", 1)[1].strip()
                if "|" in title_part:
                    return title_part.split("|", 1)[0].strip()
                return title_part
        return ""

    def _extract_content(self, lines: List[str]) -> str:
        content_started = False
        content_lines: List[str] = []
        for line in lines:
            if line.startswith("Markdown Content:"):
                content_started = True
                continue
            if content_started:
                if line.startswith(("Title:", "URL Source:", "Published Time:")):
                    break
                content_lines.append(line)
        return '\n'.join(content_lines).strip()

    def _extract_metadata(self, lines: List[str]) -> Dict[str, Any]:
        from app.utils import MetadataExtractor
        extractor = MetadataExtractor()
        return extractor.extract_jina_metadata(lines)
