"""
Краулер для веб-сайтов (документация, блоги, внешние сайты).
"""

import time
import random
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from tqdm import tqdm

from .base_crawler import BaseCrawler, CrawlResult
from app.sources_registry import SourceConfig, SourceType


class WebsiteCrawler(BaseCrawler):
    """Краулер для веб-сайтов"""

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self.session = self._build_session()
        self.seen_urls = set()

    def _build_session(self) -> requests.Session:
        """Создает HTTP сессию с retry логикой"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        headers = {
            "User-Agent": self.get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        if self.config.custom_headers:
            headers.update(self.config.custom_headers)

        session.headers.update(headers)
        return session

    def get_available_urls(self) -> List[str]:
        """Получить список URL из sitemap или seed URLs"""
        urls = []

        # Пробуем получить URL из sitemap
        if self.config.sitemap_path:
            sitemap_urls = self._crawl_sitemap()
            if sitemap_urls:
                urls.extend(sitemap_urls)
                self.logger.info(f"Found {len(sitemap_urls)} URLs in sitemap")

        # Добавляем seed URLs если sitemap пуст
        if not urls and self.config.seed_urls:
            urls.extend(self.config.seed_urls)
            self.logger.info(f"Using {len(self.config.seed_urls)} seed URLs")

        return urls

    def _crawl_sitemap(self) -> List[str]:
        """Краулинг sitemap.xml"""
        sitemap_url = urljoin(self.config.base_url, self.config.sitemap_path)

        try:
            self.logger.info(f"Fetching sitemap: {sitemap_url}")
            resp = self.session.get(sitemap_url, timeout=self.get_timeout())
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, features="xml")
            urls = []

            for loc in soup.find_all("loc"):
                url = loc.get_text(strip=True)
                if not url:
                    continue

                # Фильтруем URL по домену
                if self._is_valid_url(url):
                    urls.append(url)

            return list(dict.fromkeys(urls))  # Убираем дубликаты

        except Exception as e:
            self.logger.warning(f"Sitemap crawl failed: {e}")
            return []

    def _is_valid_url(self, url: str) -> bool:
        """Проверяет, подходит ли URL для краулинга"""
        try:
            parsed = urlparse(url)
            base_parsed = urlparse(self.config.base_url)

            # Проверяем домен
            if parsed.netloc != base_parsed.netloc:
                return False

            # Проверяем deny prefixes
            if self.config.crawl_deny_prefixes:
                for prefix in self.config.crawl_deny_prefixes:
                    if url.startswith(prefix):
                        return False

            return True

        except Exception:
            return False

    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Извлекает ссылки из HTML"""
        soup = BeautifulSoup(html, "lxml")
        links = []

        # Селекторы для разных типов сайтов
        selectors = [
            'a[href]',
            '.menu a',
            '.nav a',
            '.sidebar a',
            '.pagination a',
        ]

        for selector in selectors:
            for a in soup.select(selector):
                href = a.get("href")
                if not href:
                    continue

                # Преобразуем относительные ссылки в абсолютные
                if href.startswith("/"):
                    href = urljoin(base_url, href)
                elif not href.startswith("http"):
                    href = urljoin(base_url, href)

                if self._is_valid_url(href):
                    links.append(href)

        return list(dict.fromkeys(links))

    def _fetch_page(self, url: str) -> CrawlResult:
        """Загружает одну страницу"""
        try:
            self.logger.debug(f"Fetching: {url}")
            resp = self.session.get(url, timeout=self.get_timeout())
            resp.raise_for_status()

            # Определяем кодировку
            if resp.encoding == 'ISO-8859-1':
                resp.encoding = 'utf-8'

            html = resp.text
            soup = BeautifulSoup(html, "lxml")

            # Извлекаем заголовок
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Извлекаем основной текст
            text = ""
            if self.config.source_type == SourceType.DOCS_SITE:
                # Для документационных сайтов ищем основной контент
                main_content = soup.select_one('.theme-doc-markdown, .markdown, main, article')
                if main_content:
                    text = main_content.get_text(separator=' ', strip=True)
                else:
                    text = soup.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)

            return CrawlResult(
                url=url,
                html=html,
                text=text,
                title=title,
                metadata={}
            )

        except Exception as e:
            self.logger.warning(f"Failed to fetch {url}: {e}")
            return CrawlResult(
                url=url,
                html="",
                text="",
                title="",
                error=str(e)
            )

    def crawl(self, max_pages: Optional[int] = None) -> List[CrawlResult]:
        """Основной метод краулинга"""
        if not self.validate_config():
            return []

        # Получаем список URL для краулинга
        urls = self.get_available_urls()
        if not urls:
            self.logger.warning("No URLs found for crawling")
            return []

        # Ограничиваем количество страниц
        if max_pages:
            urls = urls[:max_pages]

        self.logger.info(f"Starting crawl of {len(urls)} URLs")

        results = []
        with tqdm(total=len(urls), desc=f"Crawling {self.config.name}", unit="page") as pbar:
            for i, url in enumerate(urls):
                if url in self.seen_urls:
                    continue

                self.seen_urls.add(url)

                # Загружаем страницу
                result = self._fetch_page(url)
                results.append(result)

                if result.error:
                    self.logger.warning(f"Error crawling {url}: {result.error}")
                else:
                    # Извлекаем дополнительные ссылки для дальнейшего краулинга
                    if not max_pages:  # Только если не ограничены по количеству
                        new_links = self._extract_links(result.html, url)
                        for link in new_links:
                            if link not in self.seen_urls and len(self.seen_urls) < 1000:  # Лимит
                                urls.append(link)

                # Задержка между запросами
                delay = (self.get_delay_ms() + random.randint(0, 500)) / 1000.0
                time.sleep(delay)

                pbar.update(1)

        successful = sum(1 for r in results if not r.error)
        self.logger.info(f"Crawl completed: {successful}/{len(results)} pages successful")

        return results
