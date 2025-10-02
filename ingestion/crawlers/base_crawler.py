"""
Базовый класс для краулеров разных типов источников данных.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger

from app.sources_registry import SourceConfig


@dataclass
class CrawlResult:
    """Результат краулинга одной страницы"""
    url: str
    html: str
    text: str = ""
    title: str = ""
    metadata: Dict[str, Any] = None
    cached: bool = False
    error: str = None


class BaseCrawler(ABC):
    """Базовый класс для краулеров"""

    def __init__(self, config: SourceConfig):
        self.config = config
        self.logger = logger.bind(crawler=config.name)

    @abstractmethod
    def crawl(self, max_pages: Optional[int] = None) -> List[CrawlResult]:
        """Основной метод краулинга"""
        pass

    @abstractmethod
    def get_available_urls(self) -> List[str]:
        """Получить список доступных URL для краулинга"""
        pass

    def validate_config(self) -> bool:
        """Валидация конфигурации источника"""
        if not self.config.base_url:
            self.logger.error("base_url is required")
            return False
        return True

    def get_user_agent(self) -> str:
        """Получить User-Agent для запросов"""
        if self.config.user_agent:
            return self.config.user_agent
        return f"Mozilla/5.0 (compatible; {self.config.name}-crawler/1.0; +{self.config.base_url})"

    def get_timeout(self) -> int:
        """Получить таймаут для запросов"""
        return self.config.timeout_s

    def get_delay_ms(self) -> int:
        """Получить задержку между запросами"""
        return self.config.crawl_delay_ms
