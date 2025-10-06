"""
Общие утилиты для тестов.
"""

import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock


class TestUtils:
    """Утилиты для тестов."""

    @staticmethod
    def create_temp_directory() -> Path:
        """Создает временную директорию для тестов."""
        return Path(tempfile.mkdtemp())

    @staticmethod
    def cleanup_temp_directory(path: Path) -> None:
        """Удаляет временную директорию."""
        if path.exists():
            shutil.rmtree(path)

    @staticmethod
    def create_test_files(directory: Path, files: Dict[str, str]) -> None:
        """Создает тестовые файлы в директории."""
        for filename, content in files.items():
            file_path = directory / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')

    @staticmethod
    def mock_requests_response(content: str = "", status_code: int = 200,
                             headers: Dict[str, str] = None) -> Mock:
        """Создает мок ответа requests."""
        mock_response = Mock()
        mock_response.text = content
        mock_response.content = content.encode('utf-8')
        mock_response.status_code = status_code
        mock_response.headers = headers or {}
        mock_response.json.return_value = {}
        return mock_response

    @staticmethod
    def mock_qdrant_client():
        """Создает мок Qdrant клиента."""
        mock_client = Mock()
        mock_client.upsert.return_value = True
        mock_client.search.return_value = []
        mock_client.scroll.return_value = ([], None)
        mock_client.get_collection.return_value = Mock()
        return mock_client

    @staticmethod
    def assert_metadata_structure(metadata: Dict[str, Any]) -> None:
        """Проверяет структуру метаданных."""
        required_fields = ['url', 'title', 'content_type']
        for field in required_fields:
            assert field in metadata, f"Отсутствует обязательное поле: {field}"

    @staticmethod
    def assert_chunk_structure(chunk: Dict[str, Any]) -> None:
        """Проверяет структуру чанка."""
        required_fields = ['text', 'metadata']
        for field in required_fields:
            assert field in chunk, f"Отсутствует обязательное поле: {field}"

        assert isinstance(chunk['text'], str), "Поле 'text' должно быть строкой"
        assert len(chunk['text']) > 0, "Поле 'text' не должно быть пустым"
        assert isinstance(chunk['metadata'], dict), "Поле 'metadata' должно быть словарем"


class MockDataFactory:
    """Фабрика мок-данных для тестов."""

    @staticmethod
    def create_page_data(url: str = "https://example.com",
                        title: str = "Тестовая страница",
                        content: str = "Тестовое содержимое") -> Dict[str, Any]:
        """Создает тестовые данные страницы."""
        return {
            'url': url,
            'title': title,
            'content': content,
            'html': f"<html><head><title>{title}</title></head><body>{content}</body></html>",
            'metadata': {
                'url': url,
                'title': title,
                'content_type': 'html',
                'page_type': 'guide'
            }
        }

    @staticmethod
    def create_crawl_result(url: str = "https://example.com",
                          title: str = "Тестовая страница",
                          content: str = "Тестовое содержимое") -> Mock:
        """Создает мок результата краулинга."""
        mock_result = Mock()
        mock_result.url = url
        mock_result.title = title
        mock_result.text = content
        mock_result.html = f"<html><head><title>{title}</title></head><body>{content}</body></html>"
        mock_result.metadata = {
            'url': url,
            'title': title,
            'content_type': 'html',
            'page_type': 'guide'
        }
        return mock_result

    @staticmethod
    def create_embedding_result(text: str = "Тестовый текст",
                              embedding: List[float] = None) -> Dict[str, Any]:
        """Создает результат эмбеддинга."""
        if embedding is None:
            embedding = [0.1] * 1024  # BGE-M3 размерность

        return {
            'text': text,
            'embedding': embedding,
            'metadata': {
                'text_length': len(text),
                'embedding_dim': len(embedding)
            }
        }
