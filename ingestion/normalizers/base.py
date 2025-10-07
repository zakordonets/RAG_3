"""
Базовые нормализаторы для единого пайплайна
"""

import re
from typing import Dict, Any, Optional
from loguru import logger

from ingestion.adapters.base import PipelineStep, ParsedDoc


class BaseNormalizer(PipelineStep):
    """
    Базовый нормализатор с общими правилами очистки.

    Применяет универсальные правила очистки, которые подходят
    для всех типов документов.
    """

    def __init__(self):
        # Общие правила очистки
        self.rules = [
            self._normalize_whitespace,
            self._remove_empty_lines,
            self._clean_encoding_issues,
            self._normalize_quotes
        ]

    def process(self, data: ParsedDoc) -> ParsedDoc:
        """
        Применяет базовые правила нормализации к документу.

        Args:
            data: Парсированный документ

        Returns:
            Нормализованный документ
        """
        if not isinstance(data, ParsedDoc):
            logger.warning(f"BaseNormalizer получил не ParsedDoc: {type(data)}")
            return data

        # Применяем все правила нормализации
        normalized_text = data.text
        for rule in self.rules:
            normalized_text = rule(normalized_text)

        # Создаем новый ParsedDoc с нормализованным текстом
        result = ParsedDoc(
            text=normalized_text,
            format=data.format,
            frontmatter=data.frontmatter,
            dom=data.dom,
            metadata=data.metadata.copy()
        )

        # Добавляем информацию о нормализации
        result.metadata["normalized"] = True
        result.metadata["normalizer"] = "base"

        return result

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "base_normalizer"

    def _normalize_whitespace(self, text: str) -> str:
        """Нормализует пробельные символы."""
        # Заменяем множественные пробелы на одинарные
        text = re.sub(r'[ \t]+', ' ', text)
        # Заменяем множественные переносы строк на двойные
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _remove_empty_lines(self, text: str) -> str:
        """Удаляет избыточные пустые строки."""
        lines = text.split('\n')
        # Удаляем пустые строки в начале и конце
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)

    def _clean_encoding_issues(self, text: str) -> str:
        """Исправляет проблемы с кодировкой."""
        try:
            # Проверяем, что текст корректно кодируется в UTF-8
            text.encode('utf-8')
            return text
        except UnicodeEncodeError:
            # Исправляем проблемные символы
            return text.encode('utf-8', errors='ignore').decode('utf-8')

    def _normalize_quotes(self, text: str) -> str:
        """Нормализует кавычки."""
        # Заменяем "умные" кавычки на обычные
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        return text


class Parser(PipelineStep):
    """
    Парсер для преобразования RawDoc в ParsedDoc.

    Определяет формат документа и применяет соответствующий парсер.
    """

    def __init__(self):
        self.parsers = {
            "markdown": self._parse_markdown,
            "html": self._parse_html,
            "text": self._parse_text
        }

    def process(self, data) -> ParsedDoc:
        """
        Парсит сырой документ в структурированный формат.

        Args:
            data: RawDoc с сырыми данными

        Returns:
            ParsedDoc с парсированным содержимым
        """
        from ingestion.adapters.base import RawDoc

        if not isinstance(data, RawDoc):
            logger.warning(f"Parser получил не RawDoc: {type(data)}")
            return data

        # Определяем формат документа
        doc_format = self._detect_format(data)

        # Парсим содержимое
        if doc_format in self.parsers:
            parsed_content = self.parsers[doc_format](data)
        else:
            logger.warning(f"Неизвестный формат документа: {doc_format}")
            parsed_content = self._parse_text(data)

        return parsed_content

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "parser"

    def _detect_format(self, raw_doc) -> str:
        """Определяет формат документа по URI и содержимому."""
        uri = raw_doc.uri.lower()
        content = raw_doc.bytes.decode('utf-8', errors='ignore')

        # По расширению файла
        if uri.endswith('.md') or uri.endswith('.mdx'):
            return "markdown"
        elif uri.endswith('.html') or uri.endswith('.htm'):
            return "html"

        # По содержимому
        if content.strip().startswith('<!DOCTYPE') or '<html' in content.lower():
            return "html"
        elif content.strip().startswith('#') or '```' in content:
            return "markdown"

        return "text"

    def _parse_markdown(self, raw_doc) -> ParsedDoc:
        """Парсит Markdown документ."""
        content = raw_doc.bytes.decode('utf-8', errors='ignore')

        # Извлекаем frontmatter
        frontmatter = self._extract_frontmatter(content)
        if frontmatter:
            # Удаляем frontmatter из основного текста
            content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

        return ParsedDoc(
            text=content.strip(),
            format="markdown",
            frontmatter=frontmatter,
            metadata={
                "source": raw_doc.meta.get("source", "unknown"),
                "uri": raw_doc.uri,
                "file_extension": raw_doc.meta.get("file_extension", ""),
                # Копируем все метаданные из raw_doc.meta
                **raw_doc.meta
            }
        )

    def _parse_html(self, raw_doc) -> ParsedDoc:
        """Парсит HTML документ."""
        content = raw_doc.bytes.decode('utf-8', errors='ignore')

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')

            # Извлекаем текст
            text = soup.get_text(separator='\n', strip=True)

            # Извлекаем заголовок
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

            return ParsedDoc(
                text=text,
                format="html",
                dom=soup,
                metadata={
                    "source": raw_doc.meta.get("source", "unknown"),
                    "uri": raw_doc.uri,
                    "title": title,
                    "content_type": "text/html"
                }
            )
        except ImportError:
            logger.warning("BeautifulSoup не установлен, используем простой парсинг HTML")
            # Простое извлечение текста без BeautifulSoup
            text = re.sub(r'<[^>]+>', '', content)
            return ParsedDoc(
                text=text.strip(),
                format="html",
                metadata={
                    "source": raw_doc.meta.get("source", "unknown"),
                    "uri": raw_doc.uri
                }
            )

    def _parse_text(self, raw_doc) -> ParsedDoc:
        """Парсит текстовый документ."""
        content = raw_doc.bytes.decode('utf-8', errors='ignore')

        return ParsedDoc(
            text=content.strip(),
            format="text",
            metadata={
                "source": raw_doc.meta.get("source", "unknown"),
                "uri": raw_doc.uri
            }
        )

    def _extract_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Извлекает YAML frontmatter из Markdown."""
        import yaml

        # Ищем frontmatter в начале документа
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if not frontmatter_match:
            return None

        try:
            frontmatter_content = frontmatter_match.group(1)
            return yaml.safe_load(frontmatter_content) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Ошибка парсинга frontmatter: {e}")
            return None
