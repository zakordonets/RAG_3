"""
Система кеширования результатов crawling для инкрементальных обновлений.
"""

from __future__ import annotations

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class PageCache:
    """Кешированная информация о странице."""
    url: str
    content_hash: str
    last_modified: str
    etag: Optional[str] = None
    title: Optional[str] = None
    page_type: str = "unknown"
    content_length: int = 0
    cached_at: str = ""
    html: str = ""
    text: str = ""

    def __post_init__(self):
        if not self.cached_at:
            self.cached_at = datetime.now(timezone.utc).isoformat()


class CrawlCache:
    """Управляет кешем результатов crawling."""

    def __init__(self, cache_dir: str = "cache/crawl"):
        """
        Инициализация кеша crawling.

        Args:
            cache_dir: Директория для хранения кеша
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.index_file = self.cache_dir / "index.json"
        self.pages_dir = self.cache_dir / "pages"
        self.pages_dir.mkdir(exist_ok=True)

        self._index: Dict[str, PageCache] = {}
        self._load_index()

        logger.info(f"Crawl cache initialized: {len(self._index)} cached pages")

    def _load_index(self):
        """Загружает индекс кеша."""
        if not self.index_file.exists():
            return

        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for url, page_data in data.items():
                self._index[url] = PageCache(**page_data)

            logger.debug(f"Loaded cache index: {len(self._index)} pages")
        except Exception as e:
            logger.warning(f"Failed to load cache index: {e}")

    def _save_index(self):
        """Сохраняет индекс кеша."""
        try:
            data = {url: asdict(page_cache) for url, page_cache in self._index.items()}

            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved cache index: {len(self._index)} pages")
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")

    def _get_page_file(self, url: str) -> Path:
        """Получает путь к файлу страницы."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.pages_dir / f"{url_hash}.json"

    def _compute_content_hash(self, content: str) -> str:
        """Вычисляет хеш контента."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def has_page(self, url: str) -> bool:
        """Проверяет, есть ли страница в кеше."""
        return url in self._index

    def get_page(self, url: str) -> Optional[PageCache]:
        """Получает страницу из кеша."""
        if url not in self._index:
            return None

        page_cache = self._index[url]
        page_file = self._get_page_file(url)

        if not page_file.exists():
            logger.warning(f"Cache file missing for {url}, removing from index")
            del self._index[url]
            return None

        try:
            with open(page_file, 'r', encoding='utf-8') as f:
                page_data = json.load(f)

            # Обновляем полные данные
            page_cache.html = page_data.get('html', '')
            page_cache.text = page_data.get('text', '')

            return page_cache
        except Exception as e:
            logger.error(f"Failed to load cached page {url}: {e}")
            return None

    def save_page(self, url: str, html: str, text: str = "",
                  etag: Optional[str] = None, title: Optional[str] = None,
                  page_type: str = "unknown") -> PageCache:
        """
        Сохраняет страницу в кеш.

        Args:
            url: URL страницы
            html: HTML контент
            text: Текстовый контент (опционально)
            etag: ETag заголовок (опционально)
            title: Заголовок страницы (опционально)
            page_type: Тип страницы

        Returns:
            Объект кешированной страницы
        """
        content_hash = self._compute_content_hash(html)

        page_cache = PageCache(
            url=url,
            content_hash=content_hash,
            last_modified=datetime.now(timezone.utc).isoformat(),
            etag=etag,
            title=title,
            page_type=page_type,
            content_length=len(html),
            html=html,
            text=text
        )

        # Сохраняем полные данные в отдельный файл
        page_file = self._get_page_file(url)
        page_data = {
            'html': html,
            'text': text,
            'metadata': asdict(page_cache)
        }

        try:
            with open(page_file, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, ensure_ascii=False, indent=2)

            # Обновляем индекс (без html/text для экономии памяти)
            index_cache = PageCache(**asdict(page_cache))
            index_cache.html = ""
            index_cache.text = ""
            self._index[url] = index_cache

            self._save_index()

            logger.debug(f"Cached page: {url} ({len(html)} chars)")
            return page_cache

        except Exception as e:
            logger.error(f"Failed to save page to cache {url}: {e}")
            raise

    def is_page_fresh(self, url: str, current_content: str) -> bool:
        """
        Проверяет, актуальна ли закешированная страница.

        Args:
            url: URL страницы
            current_content: Текущий контент для сравнения

        Returns:
            True если страница актуальна
        """
        if url not in self._index:
            return False

        page_cache = self._index[url]
        current_hash = self._compute_content_hash(current_content)

        return page_cache.content_hash == current_hash

    def get_cached_urls(self) -> Set[str]:
        """Возвращает множество всех закешированных URL."""
        return set(self._index.keys())

    def remove_page(self, url: str):
        """Удаляет страницу из кеша."""
        if url in self._index:
            del self._index[url]

            page_file = self._get_page_file(url)
            if page_file.exists():
                try:
                    page_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete cache file for {url}: {e}")

            self._save_index()
            logger.debug(f"Removed from cache: {url}")

    def cleanup_old_pages(self, valid_urls: Set[str]):
        """
        Удаляет из кеша страницы, которых нет в актуальном списке URL.

        Args:
            valid_urls: Множество актуальных URL
        """
        cached_urls = set(self._index.keys())
        to_remove = cached_urls - valid_urls

        if not to_remove:
            logger.info("No stale cache entries to remove")
            return

        logger.info(f"Removing {len(to_remove)} stale cache entries")

        for url in to_remove:
            self.remove_page(url)

    def get_cache_stats(self) -> Dict:
        """Возвращает статистику кеша."""
        total_pages = len(self._index)
        total_size = 0

        for page_file in self.pages_dir.glob("*.json"):
            try:
                total_size += page_file.stat().st_size
            except:
                continue

        return {
            "total_pages": total_pages,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir),
            "index_file": str(self.index_file)
        }

    def clear_cache(self):
        """Полностью очищает кеш."""
        logger.warning("Clearing entire crawl cache")

        # Удаляем все файлы страниц
        for page_file in self.pages_dir.glob("*.json"):
            try:
                page_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete {page_file}: {e}")

        # Очищаем индекс
        self._index.clear()

        # Удаляем файл индекса
        if self.index_file.exists():
            try:
                self.index_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete index file: {e}")

        logger.info("Crawl cache cleared")


# Глобальный экземпляр кеша
_crawl_cache: Optional[CrawlCache] = None


def get_crawl_cache() -> CrawlCache:
    """Получает глобальный экземпляр кеша crawling."""
    global _crawl_cache
    if _crawl_cache is None:
        _crawl_cache = CrawlCache()
    return _crawl_cache
