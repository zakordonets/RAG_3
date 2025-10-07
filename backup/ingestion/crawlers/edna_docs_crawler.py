"""
Специализированный краулер для документации edna docs.
Содержит специфичную логику для docs-chatcenter.edna.ru.
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
from app.config import SourceConfig, SourceType
from app.config import CONFIG


class EdnaDocsCrawler(BaseCrawler):
    """Специализированный краулер для документации edna docs"""

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
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; edna-docs-crawler/1.0; +https://docs-chatcenter.edna.ru/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        return session

    def _to_https(self, url: str) -> str:
        """Конвертирует http в https для edna docs"""
        if url.startswith("http://docs-chatcenter.edna.ru"):
            return url.replace("http://", "https://", 1)
        return url

    def _normalize_url(self, url: str) -> str:
        """Приводит URL к каноничному виду под портал edna docs.
        - Всегда https
        - /docs/api или /docs/api/ -> /docs/api/index
        - Удаляет завершающий слэш у /docs/api/index/
        """
        url = self._to_https(url)
        if url.startswith("https://docs-chatcenter.edna.ru"):
            if url.rstrip("/") == "https://docs-chatcenter.edna.ru/docs/api":
                return "https://docs-chatcenter.edna.ru/docs/api/index"
            if url == "https://docs-chatcenter.edna.ru/docs/api/index/":
                return "https://docs-chatcenter.edna.ru/docs/api/index"
        return url

    def _jina_reader_fetch(self, url: str, timeout: int) -> str:
        """Получает текстовую версию страницы через Jina Reader (r.jina.ai).
        Работает устойчиво против антибота, возвращает уже очищенный контент.
        """
        # r.jina.ai требует схему http в пути
        normalized = self._normalize_url(url)
        # отрезаем https:// и подставляем http:// после r.jina.ai
        if normalized.startswith("https://"):
            path = "http://" + normalized[len("https://"):]
        elif normalized.startswith("http://"):
            path = normalized
        else:
            path = "http://" + normalized
        reader_url = f"https://r.jina.ai/{path}"

        resp = self.session.get(reader_url, timeout=timeout)
        resp.raise_for_status()
        # Принудительно устанавливаем UTF-8 кодировку для правильного отображения русского текста
        resp.encoding = 'utf-8'
        return resp.text

    def _iter_links(self, html: str, base_url: str) -> List[str]:
        """Извлекает ссылки из HTML с учетом специфики edna docs"""
        soup = BeautifulSoup(html, "lxml")
        out: List[str] = []
        # Docusaurus: ссылки сайдбара и пагинации
        selectors = [
            '.theme-doc-sidebar-menu a.menu__link',
            '.pagination-nav__link',
            '.theme-doc-markdown a',
            'a',
        ]
        seen_local: set[str] = set()
        for sel in selectors:
            for a in soup.select(sel):
                href = a.get("href")
                if not href or href in seen_local:
                    continue
                seen_local.add(href)
                if href.startswith("http") and "docs-chatcenter.edna.ru" not in href:
                    continue
                if href.startswith("#"):
                    continue
                if href.startswith("/"):
                    href = f"https://docs-chatcenter.edna.ru{href}"
                href = self._normalize_url(href)
                if any(href.startswith(prefix) for prefix in CONFIG.crawl_deny_prefixes):
                    continue
                out.append(href)
        return list(dict.fromkeys(out))

    def _crawl_sitemap(self, base_url: str = "https://docs-chatcenter.edna.ru/") -> List[str]:
        """Получает список URL из sitemap.xml"""
        base = self._normalize_url(base_url)
        if not base.endswith("/"):
            base += "/"
        sm_url = base + "sitemap.xml"

        try:
            self.logger.info(f"GET {sm_url} [sitemap]")
            resp = self.session.get(sm_url, timeout=CONFIG.crawl_timeout_s)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, features="xml")
            urls: List[str] = []
            for loc in soup.find_all("loc"):
                u = loc.get_text(strip=True)
                if not u:
                    continue
                if "docs-chatcenter.edna.ru" not in u:
                    continue
                u = self._normalize_url(u)
                urls.append(u)
            return list(dict.fromkeys(urls))
        except Exception as e:
            self.logger.warning(f"sitemap failed: {type(e).__name__}: {e}")
            return []

    def _crawl_mkdocs_index(self, base_url: str = "https://docs-chatcenter.edna.ru/") -> List[CrawlResult]:
        """Если сайт собран на MkDocs, доступен search_index.json с готовыми текстами"""
        url = self._normalize_url(base_url)
        if not url.endswith("/"):
            url += "/"
        index_urls = [
            url + "search/search_index.json",
            url + "en/search/search_index.json",
        ]

        pages: List[CrawlResult] = []
        for idx_url in index_urls:
            try:
                self.logger.info(f"GET {idx_url} [mkdocs-index]")
                resp = self.session.get(idx_url, timeout=CONFIG.crawl_timeout_s)
                if resp.status_code != 200:
                    self.logger.warning(f"mkdocs index not found {idx_url} status={resp.status_code}")
                    continue
                data = resp.json()
                items = data.get("docs") or data.get("documents") or []
                if not items and isinstance(data, list):
                    items = data
                if not items:
                    self.logger.warning("mkdocs index: empty docs")
                    continue
                for it in items:
                    loc = it.get("location") or it.get("location_href") or it.get("url") or ""
                    title = it.get("title") or None
                    text = it.get("text") or it.get("content") or ""
                    if not loc:
                        continue
                    if loc.startswith("/"):
                        full = f"https://docs-chatcenter.edna.ru{loc}"
                    elif loc.startswith("http"):
                        full = loc
                    else:
                        full = url + loc
                    full = self._normalize_url(full)
                    # Сохраняем как текст, html заполним текстом (для совместимости)
                    pages.append(CrawlResult(
                        url=full,
                        html=text,
                        text=text,
                        title=title or "",
                        metadata={"content_strategy": "markdown"}
                    ))
                # если получили один валидный индекс — достаточно
                break
            except Exception as e:
                self.logger.warning(f"mkdocs index failed {idx_url}: {type(e).__name__}: {e}")

        # Удаляем дубликаты по URL, сохраняя порядок
        uniq = {}
        for p in pages:
            uniq.setdefault(p.url, p)
        return list(uniq.values())

    def get_available_urls(self) -> List[str]:
        """Получить список доступных URL для краулинга"""
        # Сначала пробуем sitemap
        urls = self._crawl_sitemap(self.config.base_url)
        if urls:
            return urls

        # Fallback к базовому URL
        return [self.config.base_url]

    def crawl(self, max_pages: Optional[int] = None, strategy: str = "jina", use_cache: bool = True, cleanup_cache: bool = False) -> List[CrawlResult]:
        """
        Основной метод краулинга с поддержкой кеширования и sitemap

        Args:
            max_pages: Максимальное количество страниц
            strategy: Стратегия получения контента (jina, http)
            use_cache: Использовать кеширование
            cleanup_cache: Очищать устаревшие записи из кеша
        """
        from ingestion.crawl_cache import get_crawl_cache

        # Сначала пробуем MkDocs index (самый быстрый способ)
        mkdocs_results = self._crawl_mkdocs_index(self.config.base_url)
        if mkdocs_results:
            self.logger.info(f"Found {len(mkdocs_results)} pages via MkDocs index")
            return mkdocs_results[:max_pages] if max_pages else mkdocs_results

        # Получаем список всех URL из sitemap
        all_urls = self._crawl_sitemap(self.config.base_url)
        if not all_urls:
            self.logger.warning("Sitemap пуст или недоступен, используем fallback к обычному crawling")
            return self._crawl_fallback(max_pages, strategy)

        # Ограничиваем список для обработки
        urls = all_urls[:max_pages] if max_pages else all_urls
        self.logger.info(f"Найдено {len(all_urls)} URL в sitemap, обрабатываем {len(urls)}")

        # Инициализируем кеш если нужно
        cache = get_crawl_cache() if use_cache else None
        pages: List[CrawlResult] = []

        if cache:
            # Очищаем устаревшие записи из кеша только если явно запрошено
            if cleanup_cache:
                cache.cleanup_old_pages(set(all_urls))
                self.logger.info("Очистка устаревших записей из кеша выполнена")

            # Проверяем, какие страницы уже есть в кеше
            cached_urls = cache.get_cached_urls()
            urls_to_fetch = set(urls) - cached_urls

            self.logger.info(f"Кеш содержит {len(cached_urls)} страниц, нужно загрузить {len(urls_to_fetch)} новых")

            # Загружаем закешированные страницы
            for url in cached_urls:
                if url in urls:  # Проверяем, что URL в списке для обработки
                    cached_page = cache.get_page(url)
                    if cached_page:
                        pages.append(CrawlResult(
                            url=url,
                            html=cached_page.html,
                            text=cached_page.text,
                            title=cached_page.title or "",
                            metadata={"cached": True, "content_strategy": getattr(cached_page, "content_strategy", "auto")}
                        ))
                        self.logger.debug(f"Loaded from cache: {url}")

                        # Ограничиваем количество страниц для тестирования
                        if max_pages and len(pages) >= max_pages:
                            self.logger.info(f"Достигнут лимит страниц ({max_pages}), останавливаем загрузку из кеша")
                            break

            remaining = (max_pages - len(pages)) if max_pages else None
            urls_to_process = [u for u in urls if u in urls_to_fetch]
            if remaining is not None:
                urls_to_process = urls_to_process[:max(remaining, 0)]
        else:
            urls_to_process = urls[:max_pages] if max_pages else urls
            self.logger.info("Кеширование отключено, загружаем все страницы")

        if not urls_to_process:
            self.logger.info("Все страницы загружены из кеша")
            return pages

        # Обрабатываем URL, которых нет в кеше
        self.logger.info(f"Начинаем crawling {len(urls_to_process)} страниц...")

        with tqdm(total=len(urls_to_process), desc="Crawling new pages", unit="page", disable=True) as pbar:
            for i, url in enumerate(urls_to_process, 1):
                # Ограничиваем количество страниц для тестирования
                if max_pages and len(pages) >= max_pages:
                    self.logger.info(f"Достигнуто ограничение page_limit={max_pages}, останавливаем crawling")
                    break

                try:
                    url = self._normalize_url(url)
                    timeout = CONFIG.crawl_timeout_s
                    pbar.set_description(f"Crawling ({i}/{len(urls_to_process)})")
                    self.logger.info(f"GET {url} [{i}/{len(urls_to_process)}] timeout={timeout}s strategy={strategy}")

                    html = ""
                    text = ""
                    title = None
                    content_strategy = "auto"

                    if strategy == "jina":
                        text = self._jina_reader_fetch(url, timeout=timeout)
                        html = text  # Для совместимости
                        content_strategy = "jina"
                    else:
                        # HTTP (https) с фолбэком на Jina
                        try:
                            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
                            resp.raise_for_status()
                            # если редиректнули на http, переиграем на https через normalize
                            final_url = resp.url
                            if str(final_url).startswith("http://docs-chatcenter.edna.ru"):
                                raise requests.exceptions.ConnectTimeout("downgraded to http, fallback")
                            html = resp.text
                            content_strategy = "html"
                            content_type = resp.headers.get("Content-Type", "")
                            self.logger.info(f"{resp.status_code} {url} content-type='{content_type}' bytes={len(html)}")
                        except Exception as e_http:
                            self.logger.warning(f"HTTP fetch failed for {url}: {type(e_http).__name__}: {e_http}. Trying Jina…")
                            try:
                                text = self._jina_reader_fetch(url, timeout=timeout)
                                html = text  # Для совместимости
                                content_strategy = "jina"
                            except Exception as e_jina:
                                self.logger.warning(f"Jina fetch failed for {url}: {type(e_jina).__name__}: {e_jina}")
                                # Не поднимаем исключение, просто пропускаем эту страницу
                                continue

                    # Определяем тип страницы для кеширования
                    page_type = "unknown"
                    if "api" in url.lower():
                        page_type = "api"
                    elif "faq" in url.lower():
                        page_type = "faq"
                    elif "guide" in url.lower() or "docs" in url.lower():
                        page_type = "guide"
                    elif "blog" in url.lower():
                        page_type = "blog"

                    # Сохраняем в кеш если включено
                    if cache and html:
                        try:
                            cache.save_page(url, html, text, title=title, page_type=page_type, content_strategy=content_strategy)
                            self.logger.debug(f"Cached: {url}")
                        except Exception as e:
                            self.logger.warning(f"Failed to cache {url}: {e}")

                    # Добавляем в результат
                    pages.append(CrawlResult(
                        url=url,
                        html=html,
                        text=text,
                        title=title or "",
                        metadata={"cached": False, "content_strategy": content_strategy}
                    ))

                except Exception as e:
                    self.logger.warning(f"Failed {url}: {type(e).__name__}: {e}")

                # вежливая задержка + джиттер
                delay = (CONFIG.crawl_delay_ms + random.randint(0, CONFIG.crawl_jitter_ms)) / 1000.0
                time.sleep(delay)
                pbar.update(1)

        # Статистика
        total_pages = len(pages)
        cached_pages = sum(1 for p in pages if p.metadata and p.metadata.get("cached", False))
        new_pages = total_pages - cached_pages

        self.logger.info(f"Crawling завершен: {total_pages} страниц ({cached_pages} из кеша, {new_pages} новых)")

        if cache:
            stats = cache.get_cache_stats()
            self.logger.info(f"Кеш содержит {stats['total_pages']} страниц, размер: {stats['total_size_mb']} MB")

        return pages

    def _crawl_fallback(self, max_pages: Optional[int] = None, strategy: str = "http") -> List[CrawlResult]:
        """Fallback к обычному crawling без sitemap"""
        seen: set[str] = set()
        queue: List[str] = [self.config.base_url]
        pages: List[CrawlResult] = []

        pbar = tqdm(total=0, desc="Crawling", disable=True)
        while queue:
            if max_pages and len(pages) >= max_pages:
                break
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                url = self._normalize_url(url)
                timeout = CONFIG.crawl_timeout_s
                self.logger.info(f"GET {url} timeout={timeout}s queue={len(queue)} seen={len(seen)} strategy={strategy}")

                if strategy == "jina":
                    text = self._jina_reader_fetch(url, timeout=timeout)
                    pages.append(CrawlResult(
                        url=url,
                        html=text,
                        text=text,
                        title="",
                        metadata={"content_strategy": "jina"}
                    ))
                else:
                    # HTTP (https) c фолбэком на Jina
                    try:
                        resp = self.session.get(url, timeout=timeout, allow_redirects=True)
                        resp.raise_for_status()
                        # если редиректнули на http, переиграем на https через normalize
                        final_url = resp.url
                        if str(final_url).startswith("http://docs-chatcenter.edna.ru"):
                            raise requests.exceptions.ConnectTimeout("downgraded to http, fallback")
                        html = resp.text
                        content_type = resp.headers.get("Content-Type", "")
                        self.logger.info(f"{resp.status_code} {url} content-type='{content_type}' bytes={len(html)}")
                        pages.append(CrawlResult(
                            url=url,
                            html=html,
                            text="",
                            title="",
                            metadata={"content_strategy": "html"}
                        ))
                    except Exception as e_http:
                        self.logger.warning(f"HTTP fetch failed for {url}: {type(e_http).__name__}: {e_http}. Trying Jina…")
                        try:
                            text = self._jina_reader_fetch(url, timeout=timeout)
                            pages.append(CrawlResult(
                                url=url,
                                html=text,
                                text=text,
                                title="",
                                metadata={"content_strategy": "jina"}
                            ))
                        except Exception as e_jina:
                            self.logger.warning(f"Jina fetch failed for {url}: {type(e_jina).__name__}: {e_jina}")
                            raise

                links = self._iter_links(pages[-1].html, url)
                self.logger.debug(f"EXTRACTED {len(links)} links from {url}")
                for l in links:
                    if l not in seen:
                        queue.append(l)
            except Exception as e:
                self.logger.warning(f"Failed {url}: {type(e).__name__}: {e}")
            # вежливая задержка + джиттер
            delay = (CONFIG.crawl_delay_ms + random.randint(0, CONFIG.crawl_jitter_ms)) / 1000.0
            time.sleep(delay)
            pbar.total = len(seen) + len(queue)
            pbar.update(1)

        pbar.close()
        return pages
