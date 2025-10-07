"""
Тесты для адаптеров источников данных
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from ingestion.adapters.docusaurus import DocusaurusAdapter
from ingestion.adapters.website import WebsiteAdapter
from ingestion.adapters.base import RawDoc


class TestDocusaurusAdapter:
    """Тесты для DocusaurusAdapter"""

    def test_docusaurus_adapter_creation(self):
        """Тест создания DocusaurusAdapter"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()

            adapter = DocusaurusAdapter(
                docs_root=str(docs_dir),
                site_base_url="https://test.com",
                site_docs_prefix="/docs"
            )

            assert adapter.docs_root == docs_dir
            assert adapter.site_base_url == "https://test.com"
            assert adapter.site_docs_prefix == "/docs"
            assert adapter.get_source_name() == "docusaurus"

    def test_docusaurus_adapter_nonexistent_dir(self):
        """Тест создания адаптера с несуществующей директорией"""
        with pytest.raises(ValueError, match="Директория .* не существует"):
            DocusaurusAdapter("/nonexistent/path")

    def test_docusaurus_adapter_iter_documents_empty(self):
        """Тест итерации по пустой директории"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()

            adapter = DocusaurusAdapter(str(docs_dir))
            documents = list(adapter.iter_documents())

            assert len(documents) == 0

    def test_docusaurus_adapter_iter_documents_with_files(self):
        """Тест итерации по директории с файлами"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()

            # Создаем тестовые файлы
            (docs_dir / "test1.md").write_text("# Test Document 1")
            (docs_dir / "test2.mdx").write_text("# Test Document 2")
            (docs_dir / "test3.txt").write_text("Not a markdown file")

            # Создаем _category_.json
            (docs_dir / "_category_.json").write_text('{"label": "Test Category"}')

            adapter = DocusaurusAdapter(str(docs_dir))
            documents = list(adapter.iter_documents())

            # Должны быть только .md и .mdx файлы
            assert len(documents) == 2

            for doc in documents:
                assert isinstance(doc, RawDoc)
                assert doc.uri.startswith("file://")
                assert doc.abs_path is not None
                assert doc.bytes is not None
                assert doc.meta["source"] == "docusaurus"
                assert doc.meta["file_extension"] in [".md", ".mdx"]

    def test_docusaurus_adapter_metadata(self):
        """Тест метаданных в RawDoc"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()

            # Создаем тестовый файл
            test_file = docs_dir / "test.md"
            test_file.write_text("# Test Document")

            adapter = DocusaurusAdapter(str(docs_dir))
            documents = list(adapter.iter_documents())

            assert len(documents) == 1
            doc = documents[0]

            # Проверяем метаданные
            assert "rel_path" in doc.meta
            assert "site_url" in doc.meta
            assert "dir_meta" in doc.meta
            assert "mtime" in doc.meta
            assert "file_extension" in doc.meta
            assert doc.meta["file_extension"] == ".md"


class TestWebsiteAdapter:
    """Тесты для WebsiteAdapter"""

    def test_website_adapter_creation(self):
        """Тест создания WebsiteAdapter"""
        adapter = WebsiteAdapter(
            seed_urls=["https://example.com"],
            base_url="https://example.com",
            render_js=False,
            max_pages=10
        )

        assert adapter.seed_urls == ["https://example.com"]
        assert adapter.base_url == "https://example.com"
        assert adapter.render_js is False
        assert adapter.max_pages == 10
        assert adapter.get_source_name() == "website"

    def test_website_adapter_defaults(self):
        """Тест значений по умолчанию"""
        adapter = WebsiteAdapter(seed_urls=["https://example.com"])

        assert adapter.base_url is None
        assert adapter.render_js is False
        assert adapter.max_pages is None
        assert adapter.timeout == 30
        assert "User-Agent" in adapter.headers

    @patch('ingestion.adapters.website.requests.get')
    def test_website_adapter_fetch_with_requests(self, mock_get):
        """Тест получения контента через requests"""
        # Настраиваем мок
        mock_response = Mock()
        mock_response.content = b"<html><body>Test content</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        adapter = WebsiteAdapter(seed_urls=["https://example.com"])
        content = adapter._fetch_with_requests("https://example.com")

        assert content == b"<html><body>Test content</body></html>"
        mock_get.assert_called_once_with(
            "https://example.com",
            headers=adapter.headers,
            timeout=30
        )

    @patch('playwright.sync_api.sync_playwright')
    def test_website_adapter_fetch_with_playwright(self, mock_playwright):
        """Тест получения контента через Playwright"""
        # Настраиваем мок Playwright
        mock_browser = Mock()
        mock_page = Mock()
        mock_page.content.return_value = "<html><body>Rendered content</body></html>"
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = Mock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_playwright_instance

        adapter = WebsiteAdapter(
            seed_urls=["https://example.com"],
            render_js=True
        )
        content = adapter._fetch_with_playwright("https://example.com")

        assert content == b"<html><body>Rendered content</body></html>"
        mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle")

    @patch('ingestion.adapters.website.requests.get')
    def test_website_adapter_iter_documents(self, mock_get):
        """Тест итерации по документам веб-сайта"""
        # Настраиваем мок
        mock_response = Mock()
        mock_response.content = b"<html><body>Test content</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        adapter = WebsiteAdapter(
            seed_urls=["https://example.com"],
            max_pages=1
        )
        documents = list(adapter.iter_documents())

        assert len(documents) == 1
        doc = documents[0]

        assert isinstance(doc, RawDoc)
        assert doc.uri == "https://example.com"
        assert doc.bytes == b"<html><body>Test content</body></html>"
        assert doc.meta["source"] == "website"
        assert doc.meta["content_type"] == "text/html"

    def test_website_adapter_is_valid_url(self):
        """Тест валидации URL"""
        adapter = WebsiteAdapter(seed_urls=["https://example.com"], base_url="https://example.com")

        # Валидные URL
        assert adapter._is_valid_url("https://example.com/page", "https://example.com")
        assert adapter._is_valid_url("http://example.com/page", "https://example.com")

        # Невалидные URL
        assert not adapter._is_valid_url("ftp://example.com/file", "https://example.com")
        assert not adapter._is_valid_url("https://other.com/page", "https://example.com")  # Другой домен
        assert not adapter._is_valid_url("https://example.com/file.pdf", "https://example.com")

    @patch('bs4.BeautifulSoup')
    def test_website_adapter_extract_links(self, mock_bs4):
        """Тест извлечения ссылок из HTML"""
        # Настраиваем мок BeautifulSoup
        mock_soup = Mock()
        mock_link1 = MagicMock()
        mock_link1.__getitem__.return_value = "/page1"
        mock_link2 = MagicMock()
        mock_link2.__getitem__.return_value = "/page2"
        mock_soup.find_all.return_value = [mock_link1, mock_link2]
        mock_bs4.return_value = mock_soup

        adapter = WebsiteAdapter(seed_urls=["https://example.com"])
        links = adapter._extract_links(b"<html></html>", "https://example.com")

        assert len(links) == 2
        assert "https://example.com/page1" in links
        assert "https://example.com/page2" in links

    def test_website_adapter_extract_links_no_bs4(self):
        """Тест извлечения ссылок без BeautifulSoup"""
        adapter = WebsiteAdapter(seed_urls=["https://example.com"])

        # Мокаем отсутствие BeautifulSoup
        with patch('bs4.BeautifulSoup', side_effect=ImportError):
            links = adapter._extract_links(b"<html></html>", "https://example.com")
            assert links == []


if __name__ == "__main__":
    pytest.main([__file__])
