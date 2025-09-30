"""
Универсальный загрузчик для различных источников данных.
Автоматически определяет тип контента и использует соответствующий парсер.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Optional, Union
from bs4 import BeautifulSoup
from loguru import logger

from .parsers_migration import (
    parse_jina_content,
    extract_url_metadata,
    parse_docusaurus_structure,
    parse_api_documentation,
    parse_release_notes,
    parse_faq_content,
    parse_guides
)


class UniversalLoader:
    """Универсальный загрузчик для различных типов контента."""

    def __init__(self):
        self.content_type_patterns = {
            'jina_reader': [
                r'^Title:',
                r'URL Source:',
                r'Markdown Content:'
            ],
            'html_docusaurus': [
                r'<nav class="theme-doc-breadcrumbs"',
                r'<article class="theme-doc-markdown"',
                r'<div class="theme-doc-sidebar'
            ],
            'html_generic': [
                r'<html',
                r'<!DOCTYPE html'
            ],
            'markdown': [
                r'^#{1,6}\s+',  # Заголовки markdown
                r'^\*\*.*\*\*$',  # Жирный текст
                r'^\*.*\*$'  # Курсив
            ]
        }

    def detect_content_type(self, content: str) -> str:
        """Определяет тип контента на основе его структуры."""
        if not content or not content.strip():
            return 'empty'

        content_lower = content.lower().strip()

        # Проверяем Jina Reader
        if self._matches_patterns(content, self.content_type_patterns['jina_reader']):
            return 'jina_reader'

        # Проверяем HTML Docusaurus
        if self._matches_patterns(content, self.content_type_patterns['html_docusaurus']):
            return 'html_docusaurus'

        # Проверяем обычный HTML
        if self._matches_patterns(content, self.content_type_patterns['html_generic']):
            return 'html_generic'

        # Проверяем Markdown
        lines = content.split('\n')[:10]  # Проверяем первые 10 строк
        markdown_lines = [line for line in lines if any(
            re.match(pattern, line.strip()) for pattern in self.content_type_patterns['markdown']
        )]
        if len(markdown_lines) >= 2:
            return 'markdown'

        # Если ничего не подошло, считаем обычным текстом
        return 'text'

    def _matches_patterns(self, content: str, patterns: list) -> bool:
        """Проверяет, соответствует ли контент хотя бы одному паттерну."""
        return any(re.search(pattern, content, re.MULTILINE) for pattern in patterns)

    def detect_page_type(self, url: str, content: str = None) -> str:
        """Определяет тип страницы на основе URL и контента."""
        url_lower = url.lower()

        # Паттерны URL для определения типа страницы
        # Классифицируем только ключевые типы; остальное считаем гайдами
        url_patterns = {
            'api': [r'/api/', r'/docs/api/'],
            'faq': [r'/faq', r'/help'],
            'changelog': [r'/blog/', r'/changelog', r'/release']
        }

        for page_type, patterns in url_patterns.items():
            if any(re.search(pattern, url_lower) for pattern in patterns):
                # Нормализуем имена типов к ожиданиям тестов
                if page_type == 'api':
                    return 'api-reference'
                if page_type == 'changelog':
                    return 'release-notes'
                return page_type

        # Дополнительная проверка по контенту
        if content:
            content_lower = content.lower()
            if 'api' in content_lower and ('endpoint' in content_lower or 'http' in content_lower):
                return 'api-reference'
            if 'faq' in content_lower or 'вопрос' in content_lower:
                return 'faq'

        return 'guide'  # По умолчанию считаем гайдом

    def load_content(self, url: str, content: str, strategy: str = 'auto') -> Dict[str, Any]:
        """
        Универсальная загрузка контента с автоматическим определением типа.

        Args:
            url: URL страницы
            content: Сырой контент
            strategy: Стратегия парсинга ('auto', 'jina', 'html', 'force_jina')

        Returns:
            Словарь с извлеченными данными
        """
        try:
            # Определяем тип контента
            if strategy == 'force_jina':
                content_type = 'jina_reader'
            elif strategy == 'auto':
                content_type = self.detect_content_type(content)
            else:
                content_type = strategy

            logger.debug(f"Определен тип контента: {content_type} для URL: {url}")

            # Извлекаем базовые метаданные
            result = {
                'url': url,
                'content_type': content_type,
                'strategy': strategy
            }

            # Парсим контент в зависимости от типа
            if content_type == 'jina_reader':
                parsed_data = self._parse_jina_content(content)
            elif content_type in ['html_docusaurus', 'html_generic']:
                parsed_data = self._parse_html_content(content, content_type)
            elif content_type == 'markdown':
                parsed_data = self._parse_markdown_content(content)
            else:
                parsed_data = self._parse_text_content(content)

            # Добавляем парсированные данные
            result.update(parsed_data)

            # Определяем тип страницы
            page_type = self.detect_page_type(url, result.get('content', ''))
            result['page_type'] = page_type

            # Извлекаем URL метаданные
            url_metadata = extract_url_metadata(url)
            result.update(url_metadata)

            # Применяем специфичный парсер для типа страницы
            if page_type in ['api', 'api-reference']:
                api_data = parse_api_documentation(content)
                result.update(api_data)
            elif page_type == 'faq':
                faq_data = parse_faq_content(content)
                result.update(faq_data)
            elif page_type in ['changelog', 'release-notes']:
                changelog_data = parse_release_notes(content)
                result.update(changelog_data)
            else:
                guide_data = parse_guides(content)
                result.update(guide_data)

            # Добавляем метаданные о загрузке
            # Сохраняем оригинальный content_length из метаданных, если он есть
            original_content_length = result.get('content_length')
            result.update({
                'loaded_at': self._get_timestamp(),
                'content_length': original_content_length if original_content_length is not None else len(content),
                'actual_content_length': len(content),  # Реальная длина контента
                'title': result.get('title', self._extract_title_from_url(url))
            })

            # Нормализация permissions: если отсутствует или пустой список — 'ALL'
            if 'permissions' not in result or (isinstance(result.get('permissions'), list) and not result.get('permissions')):
                result['permissions'] = 'ALL'

            logger.debug(f"Успешно загружен контент: {url} ({content_type})")
            return result

        except Exception as e:
            logger.error(f"Ошибка загрузки контента {url}: {e}")
            return self._create_error_result(url, str(e))

    def _parse_jina_content(self, content: str) -> Dict[str, Any]:
        """Парсинг контента от Jina Reader."""
        return parse_jina_content(content)

    def _parse_html_content(self, content: str, html_type: str) -> Dict[str, Any]:
        """Парсинг HTML контента."""
        soup = BeautifulSoup(content, "lxml")

        result = {}

        # Извлекаем заголовок
        title = None
        if html_type == 'html_docusaurus':
            h1 = soup.select_one('.theme-doc-markdown h1')
            if h1:
                title = h1.get_text(' ', strip=True)

        if not title:
            title_tag = soup.select_one('h1')
            if title_tag:
                title = title_tag.get_text(' ', strip=True)
            elif soup.title:
                title = soup.title.get_text(' ', strip=True)

        result['title'] = title or 'Untitled'

        # Извлекаем основной текст
        if html_type == 'html_docusaurus':
            main_content = soup.select_one('.theme-doc-markdown')
            if main_content:
                result['content'] = main_content.get_text(' ', strip=True)
            else:
                result['content'] = soup.get_text(' ', strip=True)
        else:
            result['content'] = soup.get_text(' ', strip=True)

        # Добавляем структурные метаданные для Docusaurus
        if html_type == 'html_docusaurus':
            docusaurus_metadata = parse_docusaurus_structure(str(soup))
            result.update(docusaurus_metadata)
            # Извлекаем Permissions из цитаты, если есть; по умолчанию 'ALL'
            try:
                quote = soup.find('blockquote')
                if quote:
                    text = quote.get_text(' ', strip=True)
                    m = re.search(r"Permissions:\s*(.+)$", text, re.IGNORECASE)
                    if m:
                        perms_raw = m.group(1)
                        perms = [p.strip().upper() for p in re.split(r"[,|]", perms_raw) if p.strip()]
                        # Нормализуем порядок: SUPERVISOR перед AGENT
                        priority = {"SUPERVISOR": 0, "AGENT": 1, "ADMIN": 2, "INTEGRATOR": 3}
                        perms.sort(key=lambda x: priority.get(x, 99))
                        result['permissions'] = perms
                if 'permissions' not in result:
                    result['permissions'] = 'ALL'
            except Exception:
                pass

        return result

    def _parse_markdown_content(self, content: str) -> Dict[str, Any]:
        """Парсинг Markdown контента."""
        lines = content.split('\n')

        # Извлекаем заголовок из первой строки H1
        title = 'Untitled'
        for line in lines[:10]:
            if line.strip().startswith('# '):
                title = line.strip()[2:].strip()
                break

        return {
            'title': title,
            'content': content
        }

    def _parse_text_content(self, content: str) -> Dict[str, Any]:
        """Парсинг обычного текстового контента."""
        lines = content.split('\n')

        # Извлекаем заголовок из первой непустой строки
        title = 'Untitled'
        for line in lines:
            if line.strip():
                title = line.strip()[:100]  # Ограничиваем длину
                break

        return {
            'title': title,
            'content': content
        }

    def _extract_title_from_url(self, url: str) -> str:
        """Извлекает заголовок из URL."""
        url_parts = url.split('/')
        if url_parts:
            last_part = url_parts[-1]
            if last_part:
                return last_part.replace('-', ' ').replace('_', ' ').title()
        return 'Untitled'

    def _get_timestamp(self) -> float:
        """Возвращает текущий timestamp."""
        import time
        return time.time()

    def _create_error_result(self, url: str, error: str) -> Dict[str, Any]:
        """Создает результат с ошибкой."""
        return {
            'url': url,
            'title': 'Error',
            'content': '',
            'error': error,
            'content_type': 'error',
            'loaded_at': self._get_timestamp()
        }

    def get_supported_strategies(self) -> list:
        """Возвращает список поддерживаемых стратегий."""
        return ['auto', 'jina', 'html', 'force_jina', 'html_docusaurus', 'markdown', 'text']

    def get_content_type_info(self) -> Dict[str, str]:
        """Возвращает информацию о поддерживаемых типах контента."""
        return {
            'jina_reader': 'Контент от Jina Reader API',
            'html_docusaurus': 'HTML страницы Docusaurus',
            'html_generic': 'Обычные HTML страницы',
            'markdown': 'Markdown документы',
            'text': 'Обычный текст',
            'error': 'Ошибка загрузки'
        }


# Глобальный экземпляр загрузчика
universal_loader = UniversalLoader()


def load_content_universal(url: str, content: str, strategy: str = 'auto') -> Dict[str, Any]:
    """
    Удобная функция для универсальной загрузки контента.

    Args:
        url: URL страницы
        content: Сырой контент
        strategy: Стратегия парсинга

    Returns:
        Словарь с извлеченными данными
    """
    return universal_loader.load_content(url, content, strategy)
