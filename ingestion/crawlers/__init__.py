"""
Пакет краулеров для различных типов источников данных.
"""

from .base_crawler import BaseCrawler, CrawlResult
from .website_crawler import WebsiteCrawler
from .local_folder_crawler import LocalFolderCrawler
from .crawler_factory import CrawlerFactory

__all__ = [
    'BaseCrawler',
    'CrawlResult', 
    'WebsiteCrawler',
    'LocalFolderCrawler',
    'CrawlerFactory',
]
