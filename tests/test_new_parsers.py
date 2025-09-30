"""
Быстрые тесты новых парсеров без краулинга.
"""

import pytest
from ingestion.processors.content_processor import ContentProcessor
from ingestion.processors.jina_parser import JinaParser
from ingestion.processors.html_parser import HTMLParser
from ingestion.processors.markdown_parser import MarkdownParser


class TestNewParsers:
    """Тесты новых специализированных парсеров."""

    def test_jina_parser_basic(self):
        """Тест базового Jina парсера."""
        jina_content = """Title: Тестовая страница
URL Source: https://docs-chatcenter.edna.ru/docs/test
Content Length: 500
Language Detected: Russian
Markdown Content:

# Тестовая страница

Это тестовый контент для проверки парсера.

## Подзаголовок

Дополнительная информация.
"""

        parser = JinaParser()
        result = parser.parse("https://docs-chatcenter.edna.ru/docs/test", jina_content)

        assert result.url == "https://docs-chatcenter.edna.ru/docs/test"
        assert result.title == "Тестовая страница"
        assert "Тестовая страница" in result.content
        assert "Подзаголовок" in result.content
        assert result.page_type == "guide"  # определяется по URL
        assert result.metadata['content_length'] == 500
        assert result.metadata['language_detected'] == "Russian"

    def test_html_parser_docusaurus(self):
        """Тест HTML парсера для Docusaurus."""
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Настройка агента</title>
    <meta name="description" content="Руководство по настройке агента">
</head>
<body>
    <nav class="theme-doc-breadcrumbs">
        <a href="/docs">Документация</a>
        <a href="/docs/agent">Агент</a>
        <span>Настройка</span>
    </nav>
    <article class="theme-doc-markdown">
        <h1>Настройка агента</h1>
        <p>Руководство по настройке агента в системе.</p>
        <h2>Основные параметры</h2>
        <p>Настройте основные параметры агента.</p>
        <blockquote>
            <strong>Permissions:</strong> AGENT, SUPERVISOR
        </blockquote>
    </article>
</body>
</html>"""

        parser = HTMLParser()
        result = parser.parse("https://docs-chatcenter.edna.ru/docs/agent/setup", html_content)

        assert result.url == "https://docs-chatcenter.edna.ru/docs/agent/setup"
        assert result.title == "Настройка агента"
        assert "Настройка агента" in result.content
        assert "Основные параметры" in result.content
        assert result.page_type == "guide"
        assert "Документация" in result.metadata.get('breadcrumb_path', [])
        assert "AGENT" in result.metadata.get('permissions', [])

    def test_markdown_parser_basic(self):
        """Тест базового Markdown парсера."""
        markdown_content = """# Markdown тест

Это **жирный** текст и *курсив*.

[Ссылка](https://example.com) на внешний ресурс.

## Подзаголовок

Список:
- Пункт 1
- Пункт 2
"""

        parser = MarkdownParser()
        result = parser.parse("https://example.com/test.md", markdown_content)

        assert result.url == "https://example.com/test.md"
        assert result.title == "Markdown тест"
        assert "Markdown тест" in result.content
        assert "жирный" in result.content  # разметка убрана
        assert "курсив" in result.content
        assert "Ссылка" in result.content  # ссылка преобразована в текст
        assert result.page_type == "guide"

    def test_content_processor_auto_detection(self):
        """Тест автоматического определения типа контента."""
        processor = ContentProcessor()

        # Jina контент
        jina_content = """Title: Jina Test
URL Source: https://example.com
Markdown Content:
# Jina Test
Content here."""

        result = processor.process(jina_content, "https://example.com", "auto")
        assert "Jina Test" in result.content

        # HTML контент
        html_content = """<!DOCTYPE html>
<html><head><title>HTML Test</title></head>
<body><h1>HTML Test</h1><p>Content here.</p></body></html>"""

        result = processor.process(html_content, "https://example.com", "auto")
        assert "HTML Test" in result.content

        # Markdown контент
        markdown_content = """# Markdown Test
Content here."""

        result = processor.process(markdown_content, "https://example.com", "auto")
        assert "Markdown Test" in result.content

    def test_content_processor_strategy_override(self):
        """Тест принудительного выбора стратегии."""
        processor = ContentProcessor()

        # HTML контент, но принудительно Jina - ожидаем ошибку
        html_content = """<!DOCTYPE html><html><body><h1>Test</h1></body></html>"""

        with pytest.raises(ValueError, match="Content too short"):
            processor.process("https://example.com", html_content, "jina")

    def test_page_type_detection(self):
        """Тест определения типа страницы по URL."""
        processor = ContentProcessor()

        # FAQ страница
        faq_content = """Title: FAQ
URL Source: https://docs-chatcenter.edna.ru/faq
Markdown Content:
# FAQ
Часто задаваемые вопросы."""

        result = processor.process(faq_content, "https://docs-chatcenter.edna.ru/faq", "jina")
        assert result.page_type == "faq"

        # API страница
        api_content = """Title: API Reference
URL Source: https://docs-chatcenter.edna.ru/docs/api
Markdown Content:
# API Reference
API документация."""

        result = processor.process(api_content, "https://docs-chatcenter.edna.ru/docs/api", "jina")
        assert result.page_type == "api"

    def test_error_handling(self):
        """Тест обработки ошибок."""
        processor = ContentProcessor()

        # Пустой контент
        with pytest.raises(ValueError, match="Content too short"):
            processor.process("", "https://example.com", "auto")

        # Очень короткий контент
        with pytest.raises(ValueError, match="Content too short"):
            processor.process("short", "https://example.com", "auto")

        # Некорректный Jina контент (без Title)
        jina_bad = """URL Source: https://example.com
Markdown Content:
# Test
Content here."""

        # Должен обработаться, но с пустым title
        result = processor.process(jina_bad, "https://example.com", "jina")
        assert result.title == "Untitled"  # fallback title
        assert "Test" in result.content
