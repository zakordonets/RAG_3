"""
Фабрика краулеров для создания подходящего краулера на основе конфигурации источника.
"""

from typing import Type, Dict
from loguru import logger

from app.sources_registry import SourceConfig, SourceType
from .base_crawler import BaseCrawler
from .website_crawler import WebsiteCrawler
from .local_folder_crawler import LocalFolderCrawler


class CrawlerFactory:
    """Фабрика для создания краулеров"""

    # Реестр доступных краулеров
    _crawlers: Dict[SourceType, Type[BaseCrawler]] = {
        SourceType.DOCS_SITE: WebsiteCrawler,
        SourceType.API_DOCS: WebsiteCrawler,
        SourceType.BLOG: WebsiteCrawler,
        SourceType.FAQ: WebsiteCrawler,
        SourceType.EXTERNAL: WebsiteCrawler,
        SourceType.LOCAL_FOLDER: LocalFolderCrawler,
        SourceType.FILE_COLLECTION: LocalFolderCrawler,
        # TODO: Добавить краулеры для других типов
        # SourceType.GIT_REPOSITORY: GitCrawler,
        # SourceType.CONFLUENCE: ConfluenceCrawler,
        # SourceType.NOTION: NotionCrawler,
    }

    @classmethod
    def create_crawler(cls, config: SourceConfig) -> BaseCrawler:
        """
        Создает подходящий краулер на основе конфигурации источника.

        Args:
            config: Конфигурация источника данных

        Returns:
            Экземпляр краулера

        Raises:
            ValueError: Если тип источника не поддерживается
        """
        if config.source_type not in cls._crawlers:
            supported_types = list(cls._crawlers.keys())
            raise ValueError(
                f"Unsupported source type: {config.source_type}. "
                f"Supported types: {supported_types}"
            )

        crawler_class = cls._crawlers[config.source_type]
        logger.info(f"Creating {crawler_class.__name__} for source '{config.name}'")

        return crawler_class(config)

    @classmethod
    def register_crawler(cls, source_type: SourceType, crawler_class: Type[BaseCrawler]) -> None:
        """
        Регистрирует новый краулер для типа источника.

        Args:
            source_type: Тип источника данных
            crawler_class: Класс краулера
        """
        if not issubclass(crawler_class, BaseCrawler):
            raise TypeError(f"Crawler class must inherit from BaseCrawler")

        cls._crawlers[source_type] = crawler_class
        logger.info(f"Registered crawler {crawler_class.__name__} for {source_type}")

    @classmethod
    def get_supported_types(cls) -> list[SourceType]:
        """Возвращает список поддерживаемых типов источников"""
        return list(cls._crawlers.keys())

    @classmethod
    def is_supported(cls, source_type: SourceType) -> bool:
        """Проверяет, поддерживается ли тип источника"""
        return source_type in cls._crawlers
