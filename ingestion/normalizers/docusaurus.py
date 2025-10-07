"""
Docusaurus-специфичные нормализаторы
"""

import re
from typing import Dict, Any
from loguru import logger

from .base import BaseNormalizer
from ingestion.adapters.base import PipelineStep, ParsedDoc
from ingestion.utils.docusaurus_utils import clean, replace_contentref


class DocusaurusNormalizer(PipelineStep):
    """
    Нормализатор для Docusaurus документации.

    Применяет специфичные для Docusaurus правила:
    - Очистка JSX, imports, admonitions
    - Замена ContentRef на абсолютные ссылки
    - Обработка frontmatter
    - Нормализация путей и категорий
    """

    def __init__(self, site_base_url: str = "https://docs-chatcenter.edna.ru"):
        """
        Инициализирует Docusaurus нормализатор.

        Args:
            site_base_url: Базовый URL сайта для построения абсолютных ссылок
        """
        self.site_base_url = site_base_url
        self.base_normalizer = BaseNormalizer()

    def process(self, data: ParsedDoc) -> ParsedDoc:
        """
        Применяет Docusaurus-специфичные правила нормализации.

        Args:
            data: Парсированный документ

        Returns:
            Нормализованный документ
        """
        if not isinstance(data, ParsedDoc):
            logger.warning(f"DocusaurusNormalizer получил не ParsedDoc: {type(data)}")
            return data

        # Сначала применяем базовую нормализацию
        normalized = self.base_normalizer.process(data)

        # Применяем Docusaurus-специфичные правила
        docusaurus_text = self._apply_docusaurus_rules(normalized.text)

        # Обновляем метаданные
        updated_metadata = self._process_docusaurus_metadata(normalized)

        # Создаем результат
        result = ParsedDoc(
            text=docusaurus_text,
            format=normalized.format,
            frontmatter=normalized.frontmatter,
            dom=normalized.dom,
            metadata=updated_metadata
        )

        return result

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "docusaurus_normalizer"

    def _apply_docusaurus_rules(self, text: str) -> str:
        """Применяет Docusaurus-специфичные правила очистки."""
        # 1. Очистка JSX, imports, admonitions
        cleaned_text = clean(text)

        # 2. Замена ContentRef на абсолютные ссылки
        if self.site_base_url:
            cleaned_text = replace_contentref(cleaned_text, self.site_base_url)

        return cleaned_text

    def _process_docusaurus_metadata(self, parsed_doc: ParsedDoc) -> Dict[str, Any]:
        """Обрабатывает метаданные Docusaurus документа."""
        metadata = parsed_doc.metadata.copy()

        # Добавляем информацию о нормализации
        metadata["normalized"] = True
        metadata["normalizer"] = "docusaurus"
        metadata["site_base_url"] = self.site_base_url

        # Сохраняем site_url из исходных метаданных
        if "site_url" in parsed_doc.metadata:
            metadata["site_url"] = parsed_doc.metadata["site_url"]

        # Обрабатываем frontmatter
        if parsed_doc.frontmatter:
            frontmatter = parsed_doc.frontmatter

            # Извлекаем категорию
            if "category" in frontmatter:
                metadata["category"] = frontmatter["category"]

            # Извлекаем заголовок
            if "title" in frontmatter:
                metadata["title"] = frontmatter["title"]

            # Извлекаем другие поля
            for field in ["sidebar_position", "description", "tags"]:
                if field in frontmatter:
                    metadata[field] = frontmatter[field]

        # Обрабатываем dir_meta из исходных метаданных
        if "dir_meta" in metadata:
            dir_meta = metadata["dir_meta"]

            # Извлекаем группы и пути
            if "groups_path" in dir_meta:
                metadata["groups_path"] = dir_meta["groups_path"]

            if "group_labels" in dir_meta:
                metadata["group_labels"] = dir_meta["group_labels"]

        # Определяем тип контента
        if parsed_doc.format == "markdown":
            metadata["content_type"] = "docusaurus_markdown"
        else:
            metadata["content_type"] = "docusaurus_mdx"

        return metadata


class URLMapper(PipelineStep):
    """
    Маппер URL для Docusaurus документов.

    Преобразует файловые пути в канонические URL сайта.
    """

    def __init__(
        self,
        site_base_url: str = "https://docs-chatcenter.edna.ru",
        site_docs_prefix: str = "/docs",
        drop_prefix_all_levels: bool = True
    ):
        """
        Инициализирует URL маппер.

        Args:
            site_base_url: Базовый URL сайта
            site_docs_prefix: Префикс для документации
            drop_prefix_all_levels: Удалять числовые префиксы на всех уровнях
        """
        self.site_base_url = site_base_url
        self.site_docs_prefix = site_docs_prefix
        self.drop_prefix_all_levels = drop_prefix_all_levels

    def process(self, data: ParsedDoc) -> ParsedDoc:
        """
        Применяет маппинг URL к документу.

        Args:
            data: Парсированный документ

        Returns:
            Документ с обновленными URL
        """
        if not isinstance(data, ParsedDoc):
            logger.warning(f"URLMapper получил не ParsedDoc: {type(data)}")
            return data

        # Обновляем метаданные с каноническим URL
        updated_metadata = data.metadata.copy()

        # Если есть site_url в метаданных, используем его
        if "site_url" in updated_metadata and updated_metadata["site_url"]:
            canonical_url = updated_metadata["site_url"]
        else:
            # Строим правильный URL на основе site_url из метаданных
            # Используем site_url который уже правильно сформирован в адаптере
            site_url = updated_metadata.get("site_url", "")
            if site_url:
                canonical_url = site_url
            else:
                # Fallback: используем базовый URL
                canonical_url = f"{self.site_base_url}{self.site_docs_prefix}"

        updated_metadata["canonical_url"] = canonical_url
        updated_metadata["doc_id"] = canonical_url  # Устанавливаем doc_id как canonical_url
        updated_metadata["url_mapped"] = True

        # Создаем результат
        result = ParsedDoc(
            text=data.text,
            format=data.format,
            frontmatter=data.frontmatter,
            dom=data.dom,
            metadata=updated_metadata
        )

        return result

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "url_mapper"
