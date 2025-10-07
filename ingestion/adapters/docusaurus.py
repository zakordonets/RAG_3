"""
Адаптер для Docusaurus документации (файловая система)
"""

from pathlib import Path
from typing import Iterable, Dict, Any
from loguru import logger

from .base import SourceAdapter, RawDoc
from ingestion.crawlers.docusaurus_fs_crawler import crawl_docs
from ingestion.utils.docusaurus_utils import fs_to_url


class DocusaurusAdapter(SourceAdapter):
    """
    Адаптер для индексации Docusaurus документации из файловой системы.

    Использует существующий docusaurus_fs_crawler для рекурсивного обхода
    файлов .md/.mdx и преобразует их в RawDoc формат.
    """

    def __init__(
        self,
        docs_root: str,
        site_base_url: str = "https://docs-chatcenter.edna.ru",
        site_docs_prefix: str = "/docs",
        drop_prefix_all_levels: bool = True,
        max_pages: int = None
    ):
        """
        Инициализирует адаптер Docusaurus.

        Args:
            docs_root: Корневая директория с документацией
            site_base_url: Базовый URL сайта
            site_docs_prefix: Префикс для документации в URL
            drop_prefix_all_levels: Удалять числовые префиксы на всех уровнях
            max_pages: Максимальное количество страниц для обработки
        """
        self.docs_root = Path(docs_root)
        self.site_base_url = site_base_url
        self.max_pages = max_pages
        self.site_docs_prefix = site_docs_prefix
        self.drop_prefix_all_levels = drop_prefix_all_levels

        if not self.docs_root.exists():
            raise ValueError(f"Директория {docs_root} не существует")

    def iter_documents(self) -> Iterable[RawDoc]:
        """
        Возвращает поток сырых документов из Docusaurus файловой системы.

        Yields:
            RawDoc: Сырой документ с содержимым файла и метаданными
        """
        logger.info(f"Начинаем сканирование Docusaurus документации в {self.docs_root}")

        # Сначала подсчитываем общее количество файлов
        all_items = list(crawl_docs(
            docs_root=self.docs_root,
            site_base_url=self.site_base_url,
            site_docs_prefix=self.site_docs_prefix,
            drop_prefix_all_levels=self.drop_prefix_all_levels
        ))
        total_files = len(all_items)
        
        # Ограничиваем количество файлов если указан max_pages
        if self.max_pages and self.max_pages < total_files:
            all_items = all_items[:self.max_pages]
            logger.info(f"📊 Найдено {total_files} файлов, ограничиваем до {self.max_pages} для индексации")
        else:
            logger.info(f"📊 Найдено {total_files} файлов для индексации")

        # Теперь обрабатываем файлы с прогрессом
        actual_files = len(all_items)
        for file_idx, item in enumerate(all_items, 1):

            try:
                # Логируем прогресс каждые 10 файлов или на важных этапах
                if file_idx % 10 == 0 or file_idx <= 5 or file_idx > actual_files - 5:
                    logger.info(f"📄 Обрабатываем файл {file_idx}/{actual_files}: {item.abs_path.name}")

                # Читаем содержимое файла
                content_bytes = item.abs_path.read_bytes()

                # Формируем канонический URI
                uri = f"file://{item.abs_path}"

                # Собираем метаданные
                meta = {
                    "rel_path": item.rel_path,
                    "site_url": item.site_url,
                    "dir_meta": item.dir_meta,
                    "mtime": item.mtime,
                    "file_extension": item.abs_path.suffix,
                    "source": "docusaurus"
                }

                # Создаем RawDoc
                raw_doc = RawDoc(
                    uri=uri,
                    abs_path=item.abs_path,
                    bytes=content_bytes,
                    meta=meta
                )

                yield raw_doc

            except Exception as e:
                logger.error(f"Ошибка при обработке файла {item.abs_path}: {e}")
                continue

        logger.success(f"✅ Сканирование завершено: обработано {total_files} файлов")

        logger.info(f"Сканирование завершено. Всего файлов: {total_files}")

    def get_source_name(self) -> str:
        """Возвращает имя источника."""
        return "docusaurus"
