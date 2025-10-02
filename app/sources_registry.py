"""
Централизованный реестр источников данных.

Вынесен в отдельный модуль `app.sources_registry`, чтобы избежать конфликта
с модулем `app.config` (который является файлом, а не пакетом).
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum
import time
from urllib.parse import urlparse
from loguru import logger


class SourceType(Enum):
    """Типы источников данных"""
    DOCS_SITE = "docs_site"          # Документационный сайт (Docusaurus, MkDocs)
    API_DOCS = "api_docs"            # API документация (Swagger, OpenAPI)
    BLOG = "blog"                    # Блог или новости
    FAQ = "faq"                      # FAQ страницы
    EXTERNAL = "external"            # Внешний сайт
    LOCAL_FOLDER = "local_folder"    # Локальная папка с документами
    FILE_COLLECTION = "file_collection"  # Коллекция файлов (PDF, DOC, MD)
    GIT_REPOSITORY = "git_repository"    # Git репозиторий с документами
    CONFLUENCE = "confluence"        # Confluence wiki
    NOTION = "notion"               # Notion workspace


@dataclass
class SourceConfig:
    """Конфигурация источника данных"""
    name: str
    base_url: str
    source_type: SourceType
    strategy: str = "auto"
    use_cache: bool = True
    max_pages: int | None = None
    crawl_deny_prefixes: List[str] | None = None
    sitemap_path: str = "/sitemap.xml"
    seed_urls: List[str] | None = None
    metadata_patterns: Dict[str, Dict[str, str]] | None = None
    
    # Дополнительные поля для разных типов источников
    local_path: str | None = None                    # Путь к локальной папке
    file_extensions: List[str] | None = None         # Расширения файлов для обработки
    git_url: str | None = None                      # URL Git репозитория
    git_branch: str = "main"                         # Ветка Git репозитория
    confluence_space: str | None = None             # Space в Confluence
    notion_database_id: str | None = None           # ID базы данных в Notion
    api_key: str | None = None                      # API ключ для внешних сервисов
    custom_headers: Dict[str, str] | None = None    # Кастомные заголовки
    crawl_delay_ms: int = 1000                       # Задержка между запросами (мс)
    timeout_s: int = 30                              # Таймаут запросов (сек)
    user_agent: str | None = None                   # User-Agent для запросов


class SourcesRegistry:
    """Реестр источников данных"""

    def __init__(self):
        self._sources: Dict[str, SourceConfig] = {}
        self._load_default_sources()

    def _load_default_sources(self):
        """Загружает источники по умолчанию"""
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
                "https://docs-chatcenter.edna.ru/api/",
                "https://docs-chatcenter.edna.ru/admin/",
                "https://docs-chatcenter.edna.ru/supervisor/",
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

    def register(self, source: SourceConfig):
        """Регистрирует источник данных с валидацией конфигурации."""
        self._validate_source_config(source)
        self._sources[source.name] = source

    def _validate_source_config(self, source: SourceConfig) -> None:
        """Валидирует конфигурацию источника данных."""
        # Проверяем обязательные поля
        if not source.name or not source.name.strip():
            raise ValueError("Source name cannot be empty")

        if not source.base_url or not source.base_url.strip():
            raise ValueError("Base URL cannot be empty")

        # Проверяем корректность URL
        if not source.base_url.startswith(('http://', 'https://')):
            raise ValueError(f"Base URL must start with http:// or https://: {source.base_url}")

        # Проверяем корректность стратегии
        valid_strategies = ['auto', 'jina', 'html', 'markdown', 'http']
        if source.strategy not in valid_strategies:
            raise ValueError(f"Invalid strategy '{source.strategy}'. Valid options: {valid_strategies}")

        # Проверяем max_pages
        if source.max_pages is not None and source.max_pages <= 0:
            raise ValueError("max_pages must be positive or None")

        # Проверяем sitemap_path
        if not source.sitemap_path.startswith('/'):
            raise ValueError("sitemap_path must start with '/'")

        # Проверяем seed_urls
        if source.seed_urls:
            for url in source.seed_urls:
                if not url.startswith(('http://', 'https://')):
                    raise ValueError(f"Seed URL must start with http:// or https://: {url}")

        # Проверяем crawl_deny_prefixes
        if source.crawl_deny_prefixes:
            for prefix in source.crawl_deny_prefixes:
                if not prefix.startswith(('http://', 'https://')):
                    raise ValueError(f"Crawl deny prefix must start with http:// or https://: {prefix}")

        # Проверяем metadata_patterns
        if source.metadata_patterns:
            for pattern, metadata in source.metadata_patterns.items():
                if not isinstance(pattern, str) or not pattern.strip():
                    raise ValueError("Metadata pattern must be a non-empty string")
                if not isinstance(metadata, dict):
                    raise ValueError("Metadata must be a dictionary")


def extract_url_metadata(url: str) -> Dict[str, Any]:
    """Извлекает метаданные из URL для определения раздела и роли пользователя."""
    try:
        # Базовые поля
        metadata: Dict[str, Any] = {
            "url": url,
            "source": "url_metadata",
            "extracted_at": time.time(),
        }

        # Выделяем path для определения раздела/роли
        # Пример: https://domain.tld/docs/agent/routing -> section=agent
        try:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            section = None
            if path_parts:
                # Docusaurus обычно начинается с 'docs' или 'blog'
                if path_parts[0] == 'docs':
                    if len(path_parts) > 1:
                        section = path_parts[1]
                elif path_parts[0] == 'blog':
                    section = 'changelog'
                else:
                    section = path_parts[0]
            if section:
                metadata['section'] = section
            # user_role по умолчанию выводим из section, если совпадает
            role_candidates = {"agent", "admin", "supervisor", "integrator"}
            if section in role_candidates:
                metadata['user_role'] = section
            elif section == 'api':
                metadata['user_role'] = 'integrator'
            elif section in {'changelog', 'blog', 'start'}:
                metadata['user_role'] = 'all'
            else:
                metadata['user_role'] = 'unspecified'
        except Exception:
            metadata['user_role'] = 'unspecified'

        return metadata
    except Exception as e:
        logger.warning(f"Error extracting URL metadata for {url}: {e}")
        return {"url": url}

    def get(self, name: str) -> SourceConfig:
        if name not in self._sources:
            raise ValueError(f"Source '{name}' not found. Available: {list(self._sources.keys())}")
        return self._sources[name]

    def list_all(self) -> List[str]:
        return list(self._sources.keys())

    def get_all_urls(self) -> List[str]:
        urls: List[str] = []
        for source in self._sources.values():
            if source.seed_urls:
                urls.extend(source.seed_urls)
        return urls


# Глобальный реестр и удобные функции
sources_registry = SourcesRegistry()


def get_source_config(name: str) -> SourceConfig:
    return sources_registry.get(name)


def list_available_sources() -> List[str]:
    return sources_registry.list_all()


def get_all_crawl_urls() -> List[str]:
    return sources_registry.get_all_urls()
