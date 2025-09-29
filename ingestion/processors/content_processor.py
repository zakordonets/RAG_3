from __future__ import annotations

from typing import Dict, Any

from ingestion.processors.base import ProcessedPage
from ingestion.universal_loader import load_content_universal


class ContentProcessor:
    """Временный процессор: оборачивает universal_loader и нормализует в ProcessedPage.

    На следующих этапах сюда будут интегрированы специализированные парсеры
    (JinaParser, HTMLParser, MarkdownParser) и кеширование.
    """

    def process(self, url: str, raw_content: str, strategy: str = "auto") -> ProcessedPage:
        loaded: Dict[str, Any] = load_content_universal(url, raw_content, strategy)

        # Извлекаем унифицированные поля
        title = loaded.get("title") or ""
        content = loaded.get("content") or ""
        page_type = loaded.get("page_type") or "guide"

        # Собираем метаданные (все, кроме базовых полей)
        metadata: Dict[str, Any] = {}
        for k, v in loaded.items():
            if k not in {"title", "content", "page_type"} and v is not None:
                metadata[k] = v

        return ProcessedPage(
            url=url,
            title=title,
            content=content,
            page_type=page_type,
            metadata=metadata,
        )


