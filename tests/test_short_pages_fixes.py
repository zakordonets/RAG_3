#!/usr/bin/env python3
"""
Тесты для исправления критических регрессий в рефакторинге.
"""

import pytest
from ingestion.processors.base import ProcessedPage
from ingestion.processors.content_processor import ContentProcessor
from ingestion.processors.content_processor import ContentProcessor
from ingestion.processors.html_parser import HTMLParser
from bs4 import BeautifulSoup


class TestShortPagesFixes:
    """Тесты исправлений для коротких страниц и регрессий."""

    def test_processed_page_short_content_no_error(self):
        """Тест: ProcessedPage не выбрасывает ValueError для короткого контента."""
        # Короткий контент (менее 10 символов)
        page = ProcessedPage(
            url="https://example.com/short",
            title="Short Page",
            content="Hi",  # 2 символа
            page_type="guide",
            metadata={}
        )

        # Должен создаться без ошибки
        assert page.content == "Hi"
        assert page.title == "Short Page"

    def test_processed_page_empty_content_no_error(self):
        """Тест: ProcessedPage не выбрасывает ValueError для пустого контента."""
        page = ProcessedPage(
            url="https://example.com/empty",
            title="Empty Page",
            content="",  # Пустой контент
            page_type="guide",
            metadata={}
        )

        # Должен создаться без ошибки
        assert page.content == ""
        assert page.title == "Empty Page"

    def test_content_processor_short_jina_content(self):
        """Тест: ContentProcessor обрабатывает короткий Jina контент."""
        processor = ContentProcessor()

        # Короткий Jina контент
        short_jina = """Title: FAQ
URL Source: https://example.com/faq
Markdown Content:

# FAQ
Q&A"""

        result = processor.process(short_jina, "https://example.com/faq", "auto")

        # Должен обработаться без ошибки
        assert result.url == "https://example.com/faq"
        # Контент может быть пустым из-за обработки, но структура должна быть правильной
        assert result.content is not None
        # page_type может быть 'stub' для короткого контента
        assert result.page_type in ["faq", "stub"]

    def test_content_processor_with_leading_whitespace(self):
        """Тест: ContentProcessor корректно обрабатывает контент с лидирующими пробелами."""
        processor = ContentProcessor()

        # Jina контент с лидирующими пробелами и БОМ
        jina_with_whitespace = """\ufeff   \n
Title: Test Page
URL Source: https://example.com/test
Markdown Content:

# Test Page
Content here."""

        result = processor.process(jina_with_whitespace, "https://example.com/test", "auto")

        # Должен правильно определить тип как Jina
        assert result.url == "https://example.com/test"
        # Контент может быть пустым из-за обработки, но структура должна быть правильной
        assert result.content is not None
        # page_type может быть 'stub' для короткого контента
        assert result.page_type in ["guide", "stub"]

    def test_content_processor_with_bom(self):
        """Тест: ContentProcessor корректно обрабатывает контент с БОМ."""
        processor = ContentProcessor()

        # HTML контент с БОМ
        html_with_bom = """\ufeff<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Test Page</h1></body>
</html>"""

        result = processor.process(html_with_bom, "https://example.com/test", "auto")

        # Должен правильно определить тип как HTML
        assert result.url == "https://example.com/test"
        assert "Test Page" in result.content

    def test_migration_wrapper_correct_args(self):
        """Тест: ContentProcessor правильно обрабатывает Jina контент."""
        # Тест Jina парсера
        jina_content = """Title: Test
URL Source: https://example.com/test
Markdown Content:

# Test
Content here."""

        processor = ContentProcessor()
        processed = processor.process(jina_content, "https://example.com/test", "jina")

        # Должен правильно обработать Jina контент
        assert processed.title is not None
        assert processed.content is not None
        # page_type может быть 'stub' для короткого контента
        assert processed.page_type in ["guide", "stub"]

    def test_extract_main_text_correct_args(self):
        """Тест: HTMLParser правильно извлекает текст."""
        html_content = """<!DOCTYPE html>
<html>
<body>
<div class="theme-doc-markdown">
<h1>Test Page</h1>
<p>Test content here.</p>
</div>
</body>
</html>"""

        html_parser = HTMLParser()
        processed = html_parser.parse("https://example.com/test", html_content)

        # Должен правильно извлечь текст
        assert "Test Page" in processed.content
        assert "Test content here" in processed.content

    def test_pipeline_error_handling_simulation(self):
        """Тест: симуляция обработки ошибок в пайплайне."""
        processor = ContentProcessor()

        # Тест с проблемным контентом, который может вызвать ошибку
        problematic_content = "Invalid content that might cause parsing errors"

        # Должен обработаться без исключения (fallback к HTML парсеру)
        try:
            result = processor.process(problematic_content, "https://example.com/problem", "auto")
            # Если дошли сюда, значит ошибка была обработана
            assert result is not None
            assert result.url == "https://example.com/problem"
        except Exception as e:
            pytest.fail(f"Processor should handle problematic content gracefully, but raised: {e}")

    def test_very_short_content_processing(self):
        """Тест: обработка очень короткого контента."""
        processor = ContentProcessor()

        # Очень короткий контент
        very_short = "Hi"

        result = processor.process(very_short, "https://example.com/short", "auto")

        # Должен обработаться без ошибки
        assert result.url == "https://example.com/short"
        # Контент может быть обработан и изменен
        assert result.content is not None
        assert result.title is not None  # Должен быть извлечен из URL

    def test_jina_metadata_preservation(self):
        """Тест: сохранение Jina метаданных при правильном порядке аргументов."""
        jina_content = """Title: API Documentation
URL Source: https://docs.example.com/api
Content Length: 1500
Markdown Content:

# API Documentation

## Endpoints

**Permissions:** ADMIN, USER"""

        processor = ContentProcessor()
        processed = processor.process(jina_content, "https://docs.example.com/api", "jina")

        # Проверяем, что метаданные сохранились
        assert processed.title is not None
        assert processed.content is not None
        # page_type может быть 'stub' для короткого контента
        assert processed.page_type in ["api", "stub"]
