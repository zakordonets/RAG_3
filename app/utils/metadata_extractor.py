#!/usr/bin/env python3
"""
Единый экстрактор метаданных для всех типов контента.
Консолидирует функции из sources_registry.py, html_parser.py и jina_parser.py.
"""

import time
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from loguru import logger


class MetadataExtractor:
    """Единый экстрактор метаданных для всех типов контента"""

    def __init__(self):
        self.logger = logger.bind(component="MetadataExtractor")

    def extract_url_metadata(self, url: str) -> Dict[str, Any]:
        """
        Извлекает метаданные из URL для определения раздела и роли пользователя.

        Args:
            url: URL для анализа

        Returns:
            Словарь с метаданными
        """
        try:
            # Базовые поля
            metadata: Dict[str, Any] = {
                "url": url,
                "source": "url_metadata",
                "extracted_at": time.time(),
            }

            # Выделяем path для определения раздела/роли
            # Пример: https://domain.tld/docs/agent/routing -> section=agent
            try:
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.split('/') if p]
                section = None
                user_role = None

                if path_parts:
                    # Docusaurus обычно начинается с 'docs' или 'blog'
                    if path_parts[0] == 'docs':
                        if len(path_parts) > 1:
                            section = path_parts[1]
                            # Определяем роль пользователя по разделу
                            if section in ['agent', 'admin', 'supervisor', 'integrator']:
                                user_role = section.lower()  # Исправлено для совместимости с тестами
                            elif section == 'api':
                                user_role = 'integrator'  # Исправлено для совместимости с тестами
                            else:
                                user_role = 'all'
                    elif path_parts[0] == 'blog':
                        section = 'changelog'
                        user_role = 'all'  # Исправлено для совместимости с тестами
                    else:
                        section = path_parts[0]
                        user_role = 'all'  # Исправлено для совместимости с тестами

                if section:
                    metadata['section'] = section
                if user_role:
                    metadata['user_role'] = user_role

            except Exception as e:
                self.logger.warning(f"Ошибка парсинга URL {url}: {e}")

            # Определяем тип страницы по URL
            url_lower = url.lower()
            if 'api' in url_lower:
                metadata['page_type'] = 'api'
            elif 'faq' in url_lower:
                metadata['page_type'] = 'faq'
            elif 'blog' in url_lower or 'changelog' in url_lower:
                metadata['page_type'] = 'changelog'  # Исправлено для совместимости с тестами
            elif 'guide' in url_lower or 'docs' in url_lower:
                # Более детальное определение типа страницы
                if 'api' in url_lower:
                    metadata['page_type'] = 'api'
                elif 'admin' in url_lower:
                    metadata['page_type'] = 'admin'
                elif 'supervisor' in url_lower:
                    metadata['page_type'] = 'supervisor'
                elif 'agent' in url_lower:
                    metadata['page_type'] = 'agent'
                else:
                    metadata['page_type'] = 'guide'
            else:
                metadata['page_type'] = 'unknown'

            return metadata

        except Exception as e:
            self.logger.error(f"Ошибка извлечения метаданных из URL {url}: {e}")
            return {
                "url": url,
                "source": "url_metadata",
                "extracted_at": time.time(),
                "error": str(e)
            }

    def extract_html_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Извлекает метаданные из HTML контента.

        Args:
            soup: BeautifulSoup объект HTML
            url: URL страницы

        Returns:
            Словарь с метаданными
        """
        try:
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
                        permissions = [p.strip() for p in perms_text.split(',') if p.strip()]
                        if permissions:
                            data['permissions'] = permissions

            # Дополнительные метаданные
            data['url'] = url
            data['source'] = 'html_metadata'
            data['extracted_at'] = time.time()

            return data

        except Exception as e:
            self.logger.error(f"Ошибка извлечения HTML метаданных: {e}")
            return {
                "url": url,
                "source": "html_metadata",
                "extracted_at": time.time(),
                "error": str(e)
            }

    def extract_jina_metadata(self, lines: List[str]) -> Dict[str, Any]:
        """
        Извлекает метаданные из Jina Reader контента.

        Args:
            lines: Список строк контента

        Returns:
            Словарь с метаданными
        """
        try:
            metadata: Dict[str, Any] = {}

            for line in lines[:30]:  # Анализируем первые 30 строк
                s = line.strip()
                if s.startswith("URL Source:"):
                    url_source = s.split(":", 1)[1].strip()
                    metadata['url_source'] = url_source
                    # Также извлекаем метаданные из URL
                    url_metadata = self.extract_url_metadata(url_source)
                    metadata.update(url_metadata)
                elif s.startswith("Content Length:"):
                    try:
                        metadata['content_length'] = int(s.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif s.startswith("Language Detected:"):
                    metadata['language_detected'] = s.split(":", 1)[1].strip()
                elif s.startswith("Published Time:"):
                    metadata['published_time'] = s.split(":", 1)[1].strip()
                elif s.startswith("Images:"):
                    metadata['images_count'] = s.split(":", 1)[1].strip()
                elif s.startswith("Links:"):
                    metadata['links_count'] = s.split(":", 1)[1].strip()
                elif s.startswith("Title:"):
                    metadata['title'] = s.split(":", 1)[1].strip()

            # Дополнительные метаданные
            metadata['source'] = 'jina_metadata'
            metadata['extracted_at'] = time.time()

            return metadata

        except Exception as e:
            self.logger.error(f"Ошибка извлечения Jina метаданных: {e}")
            return {
                "source": "jina_metadata",
                "extracted_at": time.time(),
                "error": str(e)
            }

    def extract_comprehensive_metadata(self, content: str, url: str, content_type: str = "auto") -> Dict[str, Any]:
        """
        Извлекает комплексные метаданные из контента.

        Args:
            content: Контент для анализа
            url: URL страницы
            content_type: Тип контента (html, jina, auto)

        Returns:
            Словарь с комплексными метаданными
        """
        try:
            # Базовые метаданные из URL
            metadata = self.extract_url_metadata(url)

            # Определяем тип контента автоматически, если не указан
            if content_type == "auto":
                if content.startswith("Title:") or "URL Source:" in content:
                    content_type = "jina"
                elif "<html" in content.lower() or "<!doctype" in content.lower():
                    content_type = "html"
                else:
                    content_type = "text"

            # Извлекаем дополнительные метаданные в зависимости от типа
            if content_type == "html":
                try:
                    soup = BeautifulSoup(content, 'html.parser')
                    html_metadata = self.extract_html_metadata(soup, url)
                    metadata.update(html_metadata)
                except Exception as e:
                    self.logger.warning(f"Ошибка парсинга HTML: {e}")

            elif content_type == "jina":
                try:
                    lines = content.split('\n')
                    jina_metadata = self.extract_jina_metadata(lines)
                    metadata.update(jina_metadata)
                except Exception as e:
                    self.logger.warning(f"Ошибка парсинга Jina: {e}")

            # Общие метаданные для всех типов
            metadata['content_type'] = content_type
            metadata['content_length'] = len(content)
            metadata['word_count'] = len(content.split())

            # Определяем язык (простая эвристика)
            if re.search(r'[а-яё]', content, re.IGNORECASE):
                metadata['language'] = 'ru'
            elif re.search(r'[a-z]', content, re.IGNORECASE):
                metadata['language'] = 'en'
            else:
                metadata['language'] = 'unknown'

            return metadata

        except Exception as e:
            self.logger.error(f"Ошибка комплексного извлечения метаданных: {e}")
            return {
                "url": url,
                "source": "comprehensive_metadata",
                "extracted_at": time.time(),
                "error": str(e)
            }


# Глобальный экземпляр для обратной совместимости
_metadata_extractor = MetadataExtractor()

# Функции для обратной совместимости
def extract_url_metadata(url: str) -> Dict[str, Any]:
    """Извлекает метаданные из URL для определения раздела и роли пользователя."""
    return _metadata_extractor.extract_url_metadata(url)
