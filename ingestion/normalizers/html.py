"""
HTML-специфичные нормализаторы
"""

import re
from typing import Dict, Any, Optional
from loguru import logger

from .base import BaseNormalizer
from ingestion.adapters.base import PipelineStep, ParsedDoc


class HtmlNormalizer(PipelineStep):
    """
    Нормализатор для HTML документов.

    Применяет специфичные для HTML правила:
    - Очистка HTML тегов
    - Удаление скриптов и стилей
    - Извлечение основного контента
    - Нормализация ссылок
    """

    def __init__(self):
        """Инициализирует HTML нормализатор."""
        self.base_normalizer = BaseNormalizer()

    def process(self, data: ParsedDoc) -> ParsedDoc:
        """
        Применяет HTML-специфичные правила нормализации.

        Args:
            data: Парсированный документ

        Returns:
            Нормализованный документ
        """
        if not isinstance(data, ParsedDoc):
            logger.warning(f"HtmlNormalizer получил не ParsedDoc: {type(data)}")
            return data

        # Сначала применяем базовую нормализацию
        normalized = self.base_normalizer.process(data)

        # Применяем HTML-специфичные правила
        html_text = self._apply_html_rules(normalized.text, normalized.dom)

        # Обновляем метаданные
        updated_metadata = self._process_html_metadata(normalized)

        # Создаем результат
        result = ParsedDoc(
            text=html_text,
            format=normalized.format,
            frontmatter=normalized.frontmatter,
            dom=normalized.dom,
            metadata=updated_metadata
        )

        return result

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "html_normalizer"

    def _apply_html_rules(self, text: str, dom: Optional[Any] = None) -> str:
        """Применяет HTML-специфичные правила очистки."""
        if dom is not None:
            # Используем BeautifulSoup для продвинутой очистки
            return self._clean_with_bs4(dom)
        else:
            # Простая очистка с помощью regex
            return self._clean_with_regex(text)

    def _clean_with_bs4(self, soup) -> str:
        """Очистка HTML с помощью BeautifulSoup."""
        try:
            # Удаляем скрипты и стили
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()

            # Извлекаем основной контент
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)

            # Нормализуем ссылки
            text = self._normalize_links(text)

            return text

        except Exception as e:
            logger.warning(f"Ошибка при очистке HTML с BeautifulSoup: {e}")
            return self._clean_with_regex(str(soup))

    def _clean_with_regex(self, html_text: str) -> str:
        """Простая очистка HTML с помощью regex."""
        # Удаляем скрипты и стили
        html_text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL | re.IGNORECASE)

        # Удаляем навигацию и служебные элементы
        html_text = re.sub(r'<nav[^>]*>.*?</nav>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r'<header[^>]*>.*?</header>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r'<footer[^>]*>.*?</footer>', '', html_text, flags=re.DOTALL | re.IGNORECASE)

        # Удаляем все HTML теги
        text = re.sub(r'<[^>]+>', '', html_text)

        # Нормализуем пробелы
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)

        return text.strip()

    def _normalize_links(self, text: str) -> str:
        """Нормализует ссылки в тексте."""
        # Заменяем [текст](url) на "текст (см. url)"
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (см. \2)', text)

        # Заменяем HTML ссылки на текст
        text = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', r'\2 (см. \1)', text)

        return text

    def _process_html_metadata(self, parsed_doc: ParsedDoc) -> Dict[str, Any]:
        """Обрабатывает метаданные HTML документа."""
        metadata = parsed_doc.metadata.copy()

        # Добавляем информацию о нормализации
        metadata["normalized"] = True
        metadata["normalizer"] = "html"

        # Определяем тип контента
        metadata["content_type"] = "html_document"

        # Извлекаем дополнительную информацию из DOM
        if parsed_doc.dom is not None:
            try:
                soup = parsed_doc.dom

                # Извлекаем мета-теги
                meta_description = soup.find('meta', attrs={'name': 'description'})
                if meta_description:
                    metadata["description"] = meta_description.get('content', '')

                meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                if meta_keywords:
                    metadata["keywords"] = meta_keywords.get('content', '')

                # Определяем язык документа
                html_tag = soup.find('html')
                if html_tag and html_tag.get('lang'):
                    metadata["lang"] = html_tag.get('lang')

            except Exception as e:
                logger.warning(f"Ошибка при извлечении метаданных из DOM: {e}")

        return metadata


class ContentExtractor(PipelineStep):
    """
    Экстрактор основного контента из HTML документов.

    Использует эвристики для извлечения основного контента,
    исключая навигацию, рекламу и другие служебные элементы.
    """

    def __init__(self):
        """Инициализирует экстрактор контента."""
        pass

    def process(self, data: ParsedDoc) -> ParsedDoc:
        """
        Извлекает основной контент из HTML документа.

        Args:
            data: Парсированный документ

        Returns:
            Документ с извлеченным контентом
        """
        if not isinstance(data, ParsedDoc) or data.format != "html":
            return data

        # Извлекаем основной контент
        main_content = self._extract_main_content(data.dom, data.text)

        # Создаем результат
        result = ParsedDoc(
            text=main_content,
            format=data.format,
            frontmatter=data.frontmatter,
            dom=data.dom,
            metadata=data.metadata.copy()
        )

        # Добавляем информацию об извлечении
        result.metadata["content_extracted"] = True
        result.metadata["extractor"] = "content_extractor"

        return result

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "content_extractor"

    def _extract_main_content(self, dom: Optional[Any], fallback_text: str) -> str:
        """Извлекает основной контент из DOM."""
        if dom is None:
            return fallback_text

        try:
            # Приоритетные селекторы для основного контента
            content_selectors = [
                'main',
                'article',
                '[role="main"]',
                '.content',
                '.main-content',
                '#content',
                '#main',
                '.post-content',
                '.entry-content'
            ]

            for selector in content_selectors:
                element = dom.select_one(selector)
                if element:
                    text = element.get_text(separator='\n', strip=True)
                    if len(text) > 100:  # Минимальная длина контента
                        return text

            # Если не нашли основной контент, используем body
            body = dom.find('body')
            if body:
                return body.get_text(separator='\n', strip=True)

            return fallback_text

        except Exception as e:
            logger.warning(f"Ошибка при извлечении контента: {e}")
            return fallback_text
