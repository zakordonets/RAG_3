from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class ProcessedPage:
    """Упрощенная структура обработанной страницы (без legacy совместимости)."""
    url: str
    title: str
    content: str  # Всегда 'content'
    page_type: str
    metadata: Dict[str, Any]

    def __post_init__(self) -> None:
        # Нормализуем контент
        if not self.content:
            self.content = ""
        
        # Обрезаем контент до разумного минимума, но не выбрасываем ошибку
        content_stripped = self.content.strip()
        if len(content_stripped) < 10:
            # Логируем предупреждение, но не останавливаем пайплайн
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Short content for {self.url}: {len(content_stripped)} chars, keeping as is")
        
        if not self.title:
            self.title = self._extract_title_from_url()

    def _extract_title_from_url(self) -> str:
        import re
        path = self.url.split('/')[-1]
        return re.sub(r'[_-]', ' ', path).title()


class BaseParser(ABC):
    """Базовый класс для всех парсеров с интеграцией page_type через DataSourceBase."""

    def __init__(self) -> None:
        self._page_type_classifier = None

    def _get_page_type_classifier(self):
        if self._page_type_classifier is None:
            from app.abstractions.data_source import DataSourceBase  # lazy import
            # Временный класс, чтобы использовать classify_page_by_url
            self._page_type_classifier = type('TempSource', (DataSourceBase,), {
                '__abstractmethods__': frozenset(),
                'fetch_pages': lambda self, max_pages=None: None,
                'classify_page': lambda self, page: None,
                'get_source_name': lambda self: 'temp'
            })({})
        return self._page_type_classifier

    def _detect_page_type(self, url: str, content: str | None = None) -> str:
        classifier = self._get_page_type_classifier()
        page_type = classifier.classify_page_by_url(url)
        return page_type.value

    @abstractmethod
    def parse(self, url: str, content: str) -> ProcessedPage:
        """Парсит контент и возвращает ProcessedPage."""
        raise NotImplementedError

