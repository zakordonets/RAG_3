from __future__ import annotations

import hashlib
from typing import Dict, Any, OrderedDict
from collections import OrderedDict

from bs4 import BeautifulSoup

from ingestion.processors.base import BaseParser, ProcessedPage


class HTMLParser(BaseParser):
    """HTML парсер c кешированием BeautifulSoup."""

    def __init__(self, max_cache_size: int = 100) -> None:
        super().__init__()
        self._soup_cache: OrderedDict[str, BeautifulSoup] = OrderedDict()
        self._max_cache_size = max_cache_size

    def parse(self, url: str, content: str) -> ProcessedPage:
        soup = self._get_soup(content)

        title = self._extract_title(soup) or "Untitled"
        content_text = self._extract_content(soup)
        metadata = self._extract_metadata(soup, url)

        result: Dict[str, Any] = {
            'title': title,
            'content': content_text,
            **metadata
        }

        return ProcessedPage(
            url=url,
            title=result['title'],
            content=result['content'],
            page_type=self._detect_page_type(url),
            metadata=result
        )

    def _get_soup(self, content: str) -> BeautifulSoup:
        key = hashlib.md5(content.encode('utf-8')).hexdigest()

        # Проверяем кеш
        if key in self._soup_cache:
            # Перемещаем в конец (самый недавно использованный)
            soup = self._soup_cache.pop(key)
            self._soup_cache[key] = soup
            return soup

        # Создаем новый объект
        soup = BeautifulSoup(content, "lxml")

        # Добавляем в кеш с проверкой размера
        self._soup_cache[key] = soup

        # Очищаем кеш если превышен лимит
        if len(self._soup_cache) > self._max_cache_size:
            # Удаляем самый старый элемент (первый в OrderedDict)
            self._soup_cache.popitem(last=False)

        return soup

    def clear_cache(self) -> None:
        """Очищает кеш BeautifulSoup объектов."""
        self._soup_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кеша."""
        return {
            "cache_size": len(self._soup_cache),
            "max_cache_size": self._max_cache_size,
            "cache_usage_percent": (len(self._soup_cache) / self._max_cache_size) * 100
        }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        h1 = soup.select_one('.theme-doc-markdown h1')
        if h1:
            return h1.get_text(' ', strip=True)
        if soup.title:
            return soup.title.get_text(strip=True)
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        main = soup.select_one('.theme-doc-markdown')
        if main:
            return self._text_from_element(main)
        return self._text_from_element(soup)

    def _text_from_element(self, element) -> str:
        parts: list[str] = []
        # Извлекаем все заголовки h1, h2, h3
        for h in element.find_all(['h1', 'h2', 'h3']):
            txt = h.get_text(' ', strip=True)
            if txt:
                parts.append(txt)
        # Извлекаем параграфы и списки
        for node in element.find_all(['p', 'li']):
            txt = node.get_text(' ', strip=True)
            if txt:
                parts.append(txt)
        return "\n\n".join(parts)

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        # Хлебные крошки
        crumbs = [a.get_text(' ', strip=True) for a in soup.select('.theme-doc-breadcrumbs a')]
        if crumbs:
            data['breadcrumb_path'] = crumbs

        # Описание страницы
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get('content'):
            data['meta_description'] = meta_desc['content']
        else:
            data['meta_description'] = ""

        # Заголовки секций
        headers = [h.get_text(' ', strip=True) for h in soup.select('.theme-doc-markdown h2, .theme-doc-markdown h3')]
        if headers:
            data['section_headers'] = headers

        # Разрешения, если встретятся в тексте
        # Ищем блоки с "Permissions:"
        for strong in soup.find_all('strong'):
            text = strong.get_text(' ', strip=True)
            if 'Permissions' in text:
                # Берем следующий текстовый узел после strong
                next_sibling = strong.next_sibling
                if next_sibling:
                    perms_text = next_sibling.strip()
                    # Парсим разрешения
                    perms = [p.strip().upper() for p in perms_text.replace(',', ' ').split() if p.isalpha()]
                    if perms:
                        data['permissions'] = sorted(set(perms))
                break

        return data
