"""
Краулер для локальных папок с документами.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from .base_crawler import BaseCrawler, CrawlResult
from app.sources_registry import SourceConfig, SourceType


class LocalFolderCrawler(BaseCrawler):
    """Краулер для локальных папок с документами"""

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self.folder_path = Path(config.local_path) if config.local_path else None
        self.file_extensions = config.file_extensions or ['.md', '.txt', '.rst', '.html']

    def validate_config(self) -> bool:
        """Валидация конфигурации"""
        if not super().validate_config():
            return False

        if not self.config.local_path:
            self.logger.error("local_path is required for LocalFolderCrawler")
            return False

        # Обновляем folder_path на случай изменения local_path
        self.folder_path = Path(self.config.local_path)

        if not self.folder_path.exists():
            self.logger.error(f"Local path does not exist: {self.folder_path}")
            return False

        if not self.folder_path.is_dir():
            self.logger.error(f"Local path is not a directory: {self.folder_path}")
            return False

        return True

    def get_available_urls(self) -> List[str]:
        """Получить список файлов для обработки"""
        if not self.validate_config():
            return []

        files = []
        for ext in self.file_extensions:
            pattern = f"**/*{ext}"
            files.extend(self.folder_path.glob(pattern))

        # Преобразуем в URL-подобные строки
        urls = []
        for file_path in files:
            if file_path.is_file():
                # Создаем "URL" на основе относительного пути
                relative_path = file_path.relative_to(self.folder_path)
                url = f"file://{relative_path.as_posix()}"
                urls.append(url)

        self.logger.info(f"Found {len(urls)} files in {self.folder_path}")
        return urls

    def _read_file(self, file_path: Path) -> str:
        """Читает содержимое файла с правильной кодировкой"""
        # Проверяем, является ли файл текстовым по расширению
        text_extensions = {'.md', '.txt', '.rst', '.html', '.htm', '.xml', '.json', '.yaml', '.yml'}
        if file_path.suffix.lower() not in text_extensions:
            raise ValueError(f"File {file_path} is not a text file")

        try:
            # Пробуем UTF-8
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                # Пробуем Windows-1251
                with open(file_path, 'r', encoding='windows-1251') as f:
                    return f.read()
            except UnicodeDecodeError:
                # Пробуем latin-1 как fallback
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()

    def _extract_title_from_content(self, content: str, file_path: Path) -> str:
        """Извлекает заголовок из содержимого файла"""
        lines = content.split('\n')

        # Для Markdown файлов
        if file_path.suffix.lower() == '.md':
            for line in lines[:10]:  # Проверяем первые 10 строк
                line = line.strip()
                if line.startswith('# '):
                    return line[2:].strip()
                elif line.startswith('## '):
                    return line[3:].strip()

        # Для RST файлов
        elif file_path.suffix.lower() == '.rst':
            for line in lines[:10]:
                line = line.strip()
                if line and not line.startswith('=') and not line.startswith('-'):
                    return line

        # Для HTML файлов
        elif file_path.suffix.lower() == '.html':
            from bs4 import BeautifulSoup
            try:
                soup = BeautifulSoup(content, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    return title_tag.get_text(strip=True)
                h1_tag = soup.find('h1')
                if h1_tag:
                    return h1_tag.get_text(strip=True)
            except Exception:
                pass

        # Fallback: используем имя файла
        return file_path.stem.replace('_', ' ').replace('-', ' ').title()

    def _process_file(self, file_path: Path) -> CrawlResult:
        """Обрабатывает один файл"""
        try:
            content = self._read_file(file_path)
            title = self._extract_title_from_content(content, file_path)

            # Создаем "URL" для файла
            relative_path = file_path.relative_to(self.folder_path)
            url = f"file://{relative_path.as_posix()}"

            # Для HTML файлов извлекаем текст
            if file_path.suffix.lower() == '.html':
                from bs4 import BeautifulSoup
                try:
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True)
                except Exception:
                    text = content
            else:
                text = content

            return CrawlResult(
                url=url,
                html=content,
                text=text,
                title=title,
                metadata={
                    'file_path': str(file_path),
                    'file_size': file_path.stat().st_size,
                    'file_extension': file_path.suffix,
                }
            )

        except Exception as e:
            self.logger.warning(f"Failed to process {file_path}: {e}")
            return CrawlResult(
                url=f"file://{file_path}",
                html="",
                text="",
                title="",
                error=str(e)
            )

    def crawl(self, max_pages: Optional[int] = None) -> List[CrawlResult]:
        """Основной метод краулинга"""
        if not self.validate_config():
            return []

        # Получаем список файлов
        file_urls = self.get_available_urls()
        if not file_urls:
            self.logger.warning("No files found for processing")
            return []

        # Ограничиваем количество файлов
        if max_pages:
            file_urls = file_urls[:max_pages]

        self.logger.info(f"Processing {len(file_urls)} files from {self.folder_path}")

        results = []
        for url in file_urls:
            # Преобразуем URL обратно в путь
            file_path = self.folder_path / url.replace('file://', '')

            if file_path.exists() and file_path.is_file():
                result = self._process_file(file_path)
                results.append(result)

                if result.error:
                    self.logger.warning(f"Error processing {file_path}: {result.error}")

        successful = sum(1 for r in results if not r.error)
        self.logger.info(f"Processing completed: {successful}/{len(results)} files successful")

        return results
