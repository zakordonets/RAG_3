"""
Адаптер для веб-сайтов (HTTP/HTML)
"""

import time
from typing import Iterable, List, Dict, Any
from loguru import logger
import requests
from urllib.parse import urljoin, urlparse

from .base import SourceAdapter, RawDoc


class WebsiteAdapter(SourceAdapter):
    """
    Адаптер для индексации веб-сайтов через HTTP запросы.

    Поддерживает как простые HTTP запросы, так и рендеринг через Playwright
    для JavaScript-heavy сайтов.
    """

    def __init__(
        self,
        seed_urls: List[str],
        base_url: str = None,
        render_js: bool = False,
        max_pages: int = None,
        timeout: int = 30,
        headers: Dict[str, str] = None
    ):
        """
        Инициализирует адаптер веб-сайта.

        Args:
            seed_urls: Список начальных URL для обхода
            base_url: Базовый URL для относительных ссылок
            render_js: Использовать Playwright для рендеринга JS
            max_pages: Максимальное количество страниц
            timeout: Таймаут для HTTP запросов
            headers: Дополнительные HTTP заголовки
        """
        self.seed_urls = seed_urls
        self.base_url = base_url
        self.render_js = render_js
        self.max_pages = max_pages
        self.timeout = timeout
        self.headers = headers or {}

        # Стандартные заголовки
        self.headers.setdefault("User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    def iter_documents(self) -> Iterable[RawDoc]:
        """
        Возвращает поток сырых документов с веб-сайта.

        Yields:
            RawDoc: Сырой документ с HTML содержимым
        """
        logger.info(f"Начинаем сканирование веб-сайта. Seed URLs: {len(self.seed_urls)}")

        processed_urls = set()
        urls_to_process = list(self.seed_urls)
        pages_processed = 0

        while urls_to_process and (not self.max_pages or pages_processed < self.max_pages):
            current_url = urls_to_process.pop(0)

            if current_url in processed_urls:
                continue

            processed_urls.add(current_url)

            try:
                # Получаем содержимое страницы
                if self.render_js:
                    content_bytes = self._fetch_with_playwright(current_url)
                else:
                    content_bytes = self._fetch_with_requests(current_url)

                # Создаем RawDoc
                raw_doc = RawDoc(
                    uri=current_url,
                    bytes=content_bytes,
                    meta={
                        "source": "website",
                        "base_url": self.base_url,
                        "render_js": self.render_js,
                        "content_type": "text/html"
                    }
                )

                yield raw_doc
                pages_processed += 1

                # Извлекаем новые ссылки для обхода (если нужно)
                if not self.max_pages or pages_processed < self.max_pages:
                    new_urls = self._extract_links(content_bytes, current_url)
                    for new_url in new_urls:
                        if new_url not in processed_urls and new_url not in urls_to_process:
                            urls_to_process.append(new_url)

                if pages_processed % 10 == 0:
                    logger.info(f"Обработано страниц: {pages_processed}")

            except Exception as e:
                logger.error(f"Ошибка при обработке URL {current_url}: {e}")
                continue

        logger.info(f"Сканирование завершено. Всего страниц: {pages_processed}")

    def _fetch_with_requests(self, url: str) -> bytes:
        """Получает содержимое страницы через requests."""
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def _fetch_with_playwright(self, url: str) -> bytes:
        """Получает содержимое страницы через Playwright (для JS рендеринга)."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url, wait_until="networkidle")
                content = page.content()
                browser.close()
                return content.encode('utf-8')
        except ImportError:
            logger.warning("Playwright не установлен, используем requests")
            return self._fetch_with_requests(url)

    def _extract_links(self, content: bytes, base_url: str) -> List[str]:
        """Извлекает ссылки из HTML для дальнейшего обхода."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(content, 'html.parser')
            links = []

            for link in soup.find_all('a', href=True):
                href = link['href']
                absolute_url = urljoin(base_url, href)

                # Фильтруем только релевантные ссылки
                if self._is_valid_url(absolute_url, base_url):
                    links.append(absolute_url)

            return links[:20]  # Ограничиваем количество новых ссылок

        except ImportError:
            logger.warning("BeautifulSoup не установлен, пропускаем извлечение ссылок")
            return []

    def _is_valid_url(self, url: str, base_url: str) -> bool:
        """Проверяет, является ли URL валидным для обхода."""
        try:
            parsed = urlparse(url)
            base_parsed = urlparse(base_url)

            # Только HTTP/HTTPS
            if parsed.scheme not in ['http', 'https']:
                return False

            # Только тот же домен (если указан base_url)
            if self.base_url and parsed.netloc != base_parsed.netloc:
                return False

            # Исключаем файлы и служебные URL
            excluded_extensions = ['.pdf', '.doc', '.docx', '.zip', '.tar.gz']
            if any(url.lower().endswith(ext) for ext in excluded_extensions):
                return False

            return True

        except Exception:
            return False

    def get_source_name(self) -> str:
        """Возвращает имя источника."""
        return "website"
