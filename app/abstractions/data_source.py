#!/usr/bin/env python3
"""
Abstract data source interfaces for extensible indexing system
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum


class PageType(Enum):
    """Enumeration of supported page types"""
    GUIDE = "guide"
    API = "api"
    FAQ = "faq"
    RELEASE_NOTES = "release_notes"
    BLOG = "blog"
    UNKNOWN = "unknown"


@dataclass
class Page:
    """Represents a single page/document from a data source"""
    url: str
    title: str
    content: str
    page_type: PageType
    metadata: Dict[str, Any]
    source: str
    language: str = "ru"
    last_modified: Optional[str] = None
    size_bytes: Optional[int] = None


@dataclass
class CrawlResult:
    """Result of a crawling operation"""
    pages: List[Page]
    total_pages: int
    successful_pages: int
    failed_pages: int
    errors: List[str]
    duration_seconds: float


@runtime_checkable
class DataSource(Protocol):
    """Protocol for data sources"""

    def fetch_pages(self, max_pages: Optional[int] = None) -> CrawlResult:
        """Fetch pages from the data source"""
        ...

    def classify_page(self, page: Page) -> PageType:
        """Classify page type based on URL and content"""
        ...

    def get_source_name(self) -> str:
        """Get human-readable name of the data source"""
        ...


class DataSourceBase(ABC):
    """Abstract base class for data sources"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validate_config()

    @abstractmethod
    def fetch_pages(self, max_pages: Optional[int] = None) -> CrawlResult:
        """Fetch pages from the data source"""
        pass

    @abstractmethod
    def classify_page(self, page: Page) -> PageType:
        """Classify page type based on URL and content"""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Get human-readable name of the data source"""
        pass

    def _validate_config(self) -> None:
        """Validate data source configuration"""
        pass

    def _create_page(
        self,
        url: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Page:
        """Helper method to create a Page object"""
        page_type = self.classify_page_by_url(url)
        return Page(
            url=url,
            title=title,
            content=content,
            page_type=page_type,
            metadata=metadata or {},
            source=self.get_source_name(),
            size_bytes=len(content.encode('utf-8'))
        )

    def classify_page_by_url(self, url: str) -> PageType:
        """Default URL-based page classification"""
        url_lower = url.lower()

        if "faq" in url_lower:
            return PageType.FAQ
        elif "api" in url_lower:
            return PageType.API
        elif any(keyword in url_lower for keyword in ["release", "changelog", "blog"]):
            return PageType.RELEASE_NOTES
        else:
            return PageType.GUIDE


class PluginManager:
    """Manager for data source plugins"""

    def __init__(self):
        self._sources: Dict[str, type[DataSourceBase]] = {}
        self._instances: Dict[str, DataSourceBase] = {}

    def register_source(self, name: str, source_class: type[DataSourceBase]) -> None:
        """Register a new data source class"""
        if not issubclass(source_class, DataSourceBase):
            raise TypeError(f"Source class must inherit from DataSourceBase")

        self._sources[name] = source_class
        print(f"Registered data source: {name}")

    def get_source(self, name: str, config: Dict[str, Any]) -> DataSourceBase:
        """Get an instance of a data source"""
        if name not in self._sources:
            raise ValueError(f"Unknown data source: {name}")

        # Create instance if not exists
        if name not in self._instances:
            self._instances[name] = self._sources[name](config)

        return self._instances[name]

    def list_sources(self) -> List[str]:
        """List all registered data sources"""
        return list(self._sources.keys())

    def unregister_source(self, name: str) -> None:
        """Unregister a data source"""
        if name in self._sources:
            del self._sources[name]
        if name in self._instances:
            del self._instances[name]


# Global plugin manager instance
plugin_manager = PluginManager()


def register_data_source(name: str):
    """Decorator for registering data sources"""
    def decorator(source_class: type[DataSourceBase]):
        plugin_manager.register_source(name, source_class)
        return source_class
    return decorator
