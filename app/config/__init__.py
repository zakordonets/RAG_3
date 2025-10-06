"""
Единая система конфигурации RAG-системы.
"""

from .app_config import AppConfig, CONFIG
from .sources_config import SourceType, SourceConfig, SourcesRegistry, get_source_config, get_all_crawl_urls

__all__ = [
    'AppConfig',
    'CONFIG',
    'SourceType',
    'SourceConfig',
    'SourcesRegistry',
    'get_source_config',
    'get_all_crawl_urls',
]
