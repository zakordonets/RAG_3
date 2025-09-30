"""
Централизованная конфигурация источников данных для индексации.
Убирает хардкод URL-ов из пайплайна.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class SourceType(Enum):
    """Типы источников данных"""
    DOCS_SITE = "docs_site"
    API_DOCS = "api_docs"
    BLOG = "blog"
    FAQ = "faq"
    EXTERNAL = "external"


@dataclass
class SourceConfig:
    """Конфигурация источника данных"""
    name: str
    base_url: str
    source_type: SourceType
    strategy: str = "auto"
    use_cache: bool = True
    max_pages: int = None
    crawl_deny_prefixes: List[str] = None
    sitemap_path: str = "/sitemap.xml"
    seed_urls: List[str] = None
    metadata_patterns: Dict[str, Dict[str, str]] = None


class SourcesRegistry:
    """Реестр источников данных"""

    def __init__(self):
        self._sources: Dict[str, SourceConfig] = {}
        self._load_default_sources()

    def _load_default_sources(self):
        """Загружает источники по умолчанию"""
        # Edna Docs - основной источник
        self.register(SourceConfig(
            name="edna_docs",
            base_url="https://docs-chatcenter.edna.ru/",
            source_type=SourceType.DOCS_SITE,
            strategy="jina",
            use_cache=True,
            sitemap_path="/sitemap.xml",
            seed_urls=[
                "https://docs-chatcenter.edna.ru/",
                "https://docs-chatcenter.edna.ru/docs/start/",
                "https://docs-chatcenter.edna.ru/docs/agent/",
                "https://docs-chatcenter.edna.ru/docs/supervisor/",
                "https://docs-chatcenter.edna.ru/docs/admin/",
                "https://docs-chatcenter.edna.ru/docs/chat-bot/",
                "https://docs-chatcenter.edna.ru/docs/api/index/",
                "https://docs-chatcenter.edna.ru/docs/faq/",
                "https://docs-chatcenter.edna.ru/blog/",
            ],
            crawl_deny_prefixes=[
                "https://docs-chatcenter.edna.ru/api/",  # API endpoints, не документация
                "https://docs-chatcenter.edna.ru/admin/",  # Админ панель
                "https://docs-chatcenter.edna.ru/supervisor/",  # Панель супервайзера
            ],
            metadata_patterns={
                r'/docs/start/': {'section': 'start', 'user_role': 'all', 'page_type': 'guide'},
                r'/docs/agent/': {'section': 'agent', 'user_role': 'agent', 'page_type': 'guide'},
                r'/docs/supervisor/': {'section': 'supervisor', 'user_role': 'supervisor', 'page_type': 'guide'},
                r'/docs/admin/': {'section': 'admin', 'user_role': 'admin', 'page_type': 'guide'},
                r'/docs/api/': {'section': 'api', 'user_role': 'integrator', 'page_type': 'api'},
                r'/blog/': {'section': 'changelog', 'user_role': 'all', 'page_type': 'release_notes'},
                r'/faq': {'section': 'faq', 'user_role': 'all', 'page_type': 'faq'},
            }
        ))

        # Дополнительные источники можно добавить здесь
        # self.register(SourceConfig(...))

    def register(self, source: SourceConfig):
        """Регистрирует новый источник"""
        self._sources[source.name] = source

    def get(self, name: str) -> SourceConfig:
        """Получает конфигурацию источника по имени"""
        if name not in self._sources:
            raise ValueError(f"Source '{name}' not found. Available: {list(self._sources.keys())}")
        return self._sources[name]

    def list_all(self) -> List[str]:
        """Возвращает список всех зарегистрированных источников"""
        return list(self._sources.keys())

    def get_by_type(self, source_type: SourceType) -> List[SourceConfig]:
        """Возвращает источники определенного типа"""
        return [source for source in self._sources.values() if source.source_type == source_type]

    def get_all_urls(self) -> List[str]:
        """Возвращает все URL всех источников"""
        urls = []
        for source in self._sources.values():
            if source.seed_urls:
                urls.extend(source.seed_urls)
        return urls

    def get_sitemap_urls(self) -> List[str]:
        """Возвращает URL sitemap всех источников"""
        return [f"{source.base_url.rstrip('/')}{source.sitemap_path}"
                for source in self._sources.values()]


# Глобальный реестр
sources_registry = SourcesRegistry()


def get_source_config(name: str) -> SourceConfig:
    """Удобная функция для получения конфигурации источника"""
    return sources_registry.get(name)


def list_available_sources() -> List[str]:
    """Удобная функция для получения списка источников"""
    return sources_registry.list_all()


def get_all_crawl_urls() -> List[str]:
    """Удобная функция для получения всех URL для краулинга"""
    return sources_registry.get_all_urls()
