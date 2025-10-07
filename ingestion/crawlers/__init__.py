"""
Пакет краулеров для различных типов источников данных.
"""

# Импортируем только то, что осталось после очистки
from .docusaurus_fs_crawler import crawl_docs, CrawlerItem

__all__ = [
    'crawl_docs',
    'CrawlerItem',
]
