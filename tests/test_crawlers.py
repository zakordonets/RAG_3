"""
Тесты для краулеров различных типов источников данных.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.config import SourceConfig, SourceType
from tests.test_utils import TestUtils, MockDataFactory
from ingestion.crawlers import (
    CrawlerFactory,
    WebsiteCrawler,
    LocalFolderCrawler,
    CrawlResult
)


class TestCrawlerFactory:
    """Тесты фабрики краулеров"""

    def test_create_website_crawler(self):
        """Тест создания краулера для веб-сайта"""
        config = SourceConfig(
            name="test_site",
            base_url="https://example.com/",
            source_type=SourceType.API_DOCS,  # Используем API_DOCS для WebsiteCrawler
        )

        crawler = CrawlerFactory.create_crawler(config)
        assert isinstance(crawler, WebsiteCrawler)
        assert crawler.config == config

    def test_create_local_folder_crawler(self):
        """Тест создания краулера для локальной папки"""
        config = SourceConfig(
            name="test_folder",
            base_url="file:///test/",
            source_type=SourceType.LOCAL_FOLDER,
            local_path="/test/path",
        )

        crawler = CrawlerFactory.create_crawler(config)
        assert isinstance(crawler, LocalFolderCrawler)
        assert crawler.config == config

    def test_unsupported_source_type(self):
        """Тест ошибки для неподдерживаемого типа источника"""
        config = SourceConfig(
            name="test_unsupported",
            base_url="https://example.com/",
            source_type=SourceType.GIT_REPOSITORY,  # Не поддерживается пока
        )

        with pytest.raises(ValueError, match="Unsupported source type"):
            CrawlerFactory.create_crawler(config)

    def test_get_supported_types(self):
        """Тест получения поддерживаемых типов"""
        supported_types = CrawlerFactory.get_supported_types()
        assert SourceType.DOCS_SITE in supported_types
        assert SourceType.LOCAL_FOLDER in supported_types

    def test_is_supported(self):
        """Тест проверки поддержки типа источника"""
        assert CrawlerFactory.is_supported(SourceType.DOCS_SITE)
        assert CrawlerFactory.is_supported(SourceType.LOCAL_FOLDER)
        assert not CrawlerFactory.is_supported(SourceType.GIT_REPOSITORY)


class TestWebsiteCrawler:
    """Тесты краулера для веб-сайтов"""

    def setup_method(self):
        """Настройка для каждого теста"""
        self.config = SourceConfig(
            name="test_site",
            base_url="https://example.com/",
            source_type=SourceType.DOCS_SITE,
            sitemap_path="/sitemap.xml",
            seed_urls=["https://example.com/", "https://example.com/docs/"],
        )
        self.crawler = WebsiteCrawler(self.config)

    def test_validation_success(self):
        """Тест успешной валидации конфигурации"""
        assert self.crawler.validate_config() is True

    def test_validation_missing_base_url(self):
        """Тест валидации с отсутствующим base_url"""
        self.config.base_url = ""
        assert self.crawler.validate_config() is False

    def test_get_user_agent(self):
        """Тест получения User-Agent"""
        user_agent = self.crawler.get_user_agent()
        assert "test_site-crawler" in user_agent
        assert "Mozilla" in user_agent

    def test_get_user_agent_custom(self):
        """Тест получения кастомного User-Agent"""
        self.config.user_agent = "MyBot/1.0"
        user_agent = self.crawler.get_user_agent()
        assert user_agent == "MyBot/1.0"

    def test_get_timeout(self):
        """Тест получения таймаута"""
        timeout = self.crawler.get_timeout()
        assert timeout == 30  # Значение по умолчанию

    def test_get_delay_ms(self):
        """Тест получения задержки"""
        delay = self.crawler.get_delay_ms()
        assert delay == 1000  # Значение по умолчанию

    def test_is_valid_url(self):
        """Тест проверки валидности URL"""
        # Валидный URL
        assert self.crawler._is_valid_url("https://example.com/page") is True

        # URL другого домена
        assert self.crawler._is_valid_url("https://other.com/page") is False

        # URL с deny prefix
        self.config.crawl_deny_prefixes = ["https://example.com/admin/"]
        assert self.crawler._is_valid_url("https://example.com/admin/page") is False

    @patch('ingestion.crawlers.website_crawler.requests.Session.get')
    def test_fetch_page_success(self, mock_get):
        """Тест успешной загрузки страницы"""
        # Мокаем HTTP ответ
        mock_response = Mock()
        mock_response.text = "<html><title>Test Page</title><body>Test content</body></html>"
        mock_response.encoding = 'utf-8'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.crawler._fetch_page("https://example.com/test")

        assert isinstance(result, CrawlResult)
        assert result.url == "https://example.com/test"
        assert result.title == "Test Page"
        assert "Test content" in result.text
        assert result.error is None

    @patch('ingestion.crawlers.website_crawler.requests.Session.get')
    def test_fetch_page_error(self, mock_get):
        """Тест ошибки загрузки страницы"""
        # Мокаем HTTP ошибку
        mock_get.side_effect = Exception("Connection error")

        result = self.crawler._fetch_page("https://example.com/test")

        assert isinstance(result, CrawlResult)
        assert result.url == "https://example.com/test"
        assert result.error == "Connection error"
        assert result.html == ""
        assert result.text == ""


class TestLocalFolderCrawler:
    """Тесты краулера для локальных папок"""

    def setup_method(self):
        """Настройка для каждого теста"""
        # Создаем временную папку для тестов
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        self.config = SourceConfig(
            name="test_folder",
            base_url=f"file://{self.temp_path}/",
            source_type=SourceType.LOCAL_FOLDER,
            local_path=str(self.temp_path),
            file_extensions=['.md', '.txt'],
        )
        self.crawler = LocalFolderCrawler(self.config)

    def teardown_method(self):
        """Очистка после каждого теста"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validation_success(self):
        """Тест успешной валидации конфигурации"""
        assert self.crawler.validate_config() is True

    def test_validation_missing_local_path(self):
        """Тест валидации с отсутствующим local_path"""
        self.config.local_path = None
        assert self.crawler.validate_config() is False

    def test_validation_nonexistent_path(self):
        """Тест валидации с несуществующим путем"""
        self.config.local_path = "/nonexistent/path"
        assert self.crawler.validate_config() is False

    def test_get_available_urls_empty_folder(self):
        """Тест получения URL из пустой папки"""
        urls = self.crawler.get_available_urls()
        assert urls == []

    def test_get_available_urls_with_files(self):
        """Тест получения URL из папки с файлами"""
        # Создаем тестовые файлы
        (self.temp_path / "test1.md").write_text("# Test 1")
        (self.temp_path / "test2.txt").write_text("Test 2")
        (self.temp_path / "test3.html").write_text("<html>Test 3</html>")  # Не подходящий тип
        (self.temp_path / "subdir").mkdir()
        (self.temp_path / "subdir" / "test4.md").write_text("# Test 4")

        urls = self.crawler.get_available_urls()

        # Должны найти только .md и .txt файлы
        assert len(urls) == 3
        assert any("test1.md" in url for url in urls)
        assert any("test2.txt" in url for url in urls)
        assert any("subdir/test4.md" in url for url in urls)
        assert not any("test3.html" in url for url in urls)

    def test_process_file_markdown(self):
        """Тест обработки Markdown файла"""
        # Создаем тестовый Markdown файл
        test_file = self.temp_path / "test.md"
        test_file.write_text("# Test Title\n\nThis is test content.")

        result = self.crawler._process_file(test_file)

        assert isinstance(result, CrawlResult)
        assert "test.md" in result.url
        assert result.title == "Test Title"
        assert "This is test content" in result.text
        assert result.metadata['file_extension'] == '.md'
        assert result.error is None

    def test_process_file_txt(self):
        """Тест обработки текстового файла"""
        # Создаем тестовый текстовый файл
        test_file = self.temp_path / "test.txt"
        test_file.write_text("Test content without title")

        result = self.crawler._process_file(test_file)

        assert isinstance(result, CrawlResult)
        assert "test.txt" in result.url
        assert result.title == "Test"  # Из имени файла
        assert "Test content without title" in result.text
        assert result.metadata['file_extension'] == '.txt'
        assert result.error is None

    def test_process_file_error(self):
        """Тест обработки файла с ошибкой"""
        # Создаем файл, который нельзя прочитать
        test_file = self.temp_path / "test.bin"
        test_file.write_bytes(b'\x00\x01\x02\x03')

        result = self.crawler._process_file(test_file)

        assert isinstance(result, CrawlResult)
        assert result.error is not None
        assert result.text == ""

    def test_crawl_success(self):
        """Тест успешного краулинга папки"""
        # Создаем тестовые файлы
        (self.temp_path / "test1.md").write_text("# Test 1\nContent 1")
        (self.temp_path / "test2.txt").write_text("Content 2")

        results = self.crawler.crawl()

        assert len(results) == 2
        successful = [r for r in results if not r.error]
        assert len(successful) == 2

    def test_crawl_with_max_pages(self):
        """Тест краулинга с ограничением количества страниц"""
        # Создаем несколько тестовых файлов
        for i in range(5):
            (self.temp_path / f"test{i}.md").write_text(f"# Test {i}")

        results = self.crawler.crawl(max_pages=3)

        assert len(results) == 3


class TestCrawlResult:
    """Тесты для класса CrawlResult"""

    def test_crawl_result_creation(self):
        """Тест создания CrawlResult"""
        result = CrawlResult(
            url="https://example.com/",
            html="<html>Test</html>",
            text="Test content",
            title="Test Page",
            metadata={"key": "value"},
            cached=False,
            error=None
        )

        assert result.url == "https://example.com/"
        assert result.html == "<html>Test</html>"
        assert result.text == "Test content"
        assert result.title == "Test Page"
        assert result.metadata == {"key": "value"}
        assert result.cached is False
        assert result.error is None

    def test_crawl_result_with_error(self):
        """Тест создания CrawlResult с ошибкой"""
        result = CrawlResult(
            url="https://example.com/",
            html="",
            text="",
            title="",
            error="Connection failed"
        )

        assert result.url == "https://example.com/"
        assert result.error == "Connection failed"
        assert result.html == ""
        assert result.text == ""


# Интеграционные тесты
class TestCrawlerIntegration:
    """Интеграционные тесты краулеров"""

    def test_website_crawler_integration(self):
        """Интеграционный тест краулера веб-сайта"""
        config = SourceConfig(
            name="test_integration",
            base_url="https://httpbin.org/",  # Тестовый сайт
            source_type=SourceType.API_DOCS,  # Используем API_DOCS для WebsiteCrawler
            seed_urls=["https://httpbin.org/"],
        )

        crawler = CrawlerFactory.create_crawler(config)

        # Тестируем получение URL
        urls = crawler.get_available_urls()
        assert isinstance(urls, list)

        # Тестируем краулинг (только одну страницу)
        results = crawler.crawl(max_pages=1)
        assert len(results) == 1

        result = results[0]
        if not result.error:
            assert result.url == "https://httpbin.org/"
            assert len(result.text) > 0

    def test_local_folder_crawler_integration(self):
        """Интеграционный тест краулера локальной папки"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Создаем тестовые файлы
            (temp_path / "readme.md").write_text("# README\n\nThis is a test document.")
            (temp_path / "guide.txt").write_text("This is a guide.")

            config = SourceConfig(
                name="test_integration",
                base_url=f"file://{temp_path}/",
                source_type=SourceType.LOCAL_FOLDER,
                local_path=str(temp_path),
                file_extensions=['.md', '.txt'],
            )

            crawler = CrawlerFactory.create_crawler(config)

            # Тестируем краулинг
            results = crawler.crawl()
            assert len(results) == 2

            successful = [r for r in results if not r.error]
            assert len(successful) == 2
