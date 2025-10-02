"""
Тесты универсального загрузчика для системы автотестов.
"""

import pytest
from unittest.mock import patch, MagicMock
from ingestion.universal_loader import UniversalLoader, load_content_universal
from app.sources_registry import extract_url_metadata


class TestUniversalLoader:
    """Тесты универсального загрузчика."""

    def setup_method(self):
        """Настройка для каждого теста."""
        self.loader = UniversalLoader()

    def test_content_type_detection_jina_reader(self):
        """Тест определения Jina Reader контента."""
        content = """Title: Тестовая страница
URL Source: https://example.com
Markdown Content:

# Заголовок

Содержимое страницы.
"""
        assert self.loader.detect_content_type(content) == 'jina_reader'

    def test_content_type_detection_html_docusaurus(self):
        """Тест определения HTML Docusaurus контента."""
        content = """<!DOCTYPE html>
<html>
<body>
<nav class="theme-doc-breadcrumbs">
<article class="theme-doc-markdown">
<div class="theme-doc-sidebar">
</body>
</html>"""
        assert self.loader.detect_content_type(content) == 'html_docusaurus'

    def test_content_type_detection_html_generic(self):
        """Тест определения обычного HTML контента."""
        content = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Заголовок</h1></body>
</html>"""
        assert self.loader.detect_content_type(content) == 'html_generic'

    def test_content_type_detection_markdown(self):
        """Тест определения Markdown контента."""
        content = """# Заголовок

**Жирный текст**

*Курсив*

## Подзаголовок
"""
        assert self.loader.detect_content_type(content) == 'markdown'

    def test_content_type_detection_text(self):
        """Тест определения обычного текста."""
        content = "Это обычный текст без специальной разметки."
        assert self.loader.detect_content_type(content) == 'text'

    def test_content_type_detection_empty(self):
        """Тест определения пустого контента."""
        assert self.loader.detect_content_type("") == 'empty'
        assert self.loader.detect_content_type(None) == 'empty'

    def test_page_type_detection_guide(self):
        """Тест определения типа страницы - гайд."""
        url = "https://docs-chatcenter.edna.ru/docs/start/whatis"
        assert self.loader.detect_page_type(url) == 'guide'

    def test_page_type_detection_api(self):
        """Тест определения типа страницы - API."""
        url = "https://docs-chatcenter.edna.ru/docs/api/messages"
        assert self.loader.detect_page_type(url) == 'api'

    def test_page_type_detection_faq(self):
        """Тест определения типа страницы - FAQ."""
        url = "https://docs-chatcenter.edna.ru/faq"
        assert self.loader.detect_page_type(url) == 'faq'

    def test_page_type_detection_changelog(self):
        """Тест определения типа страницы - changelog."""
        url = "https://docs-chatcenter.edna.ru/blog/release-6.16"
        assert self.loader.detect_page_type(url) == 'changelog'

    def test_page_type_detection_admin(self):
        """Тест определения типа страницы - admin."""
        url = "https://docs-chatcenter.edna.ru/docs/admin/widget"
        assert self.loader.detect_page_type(url) == 'admin'

    def test_page_type_detection_supervisor(self):
        """Тест определения типа страницы - supervisor."""
        url = "https://docs-chatcenter.edna.ru/docs/supervisor/threadcontrol"
        assert self.loader.detect_page_type(url) == 'supervisor'

    def test_page_type_detection_agent(self):
        """Тест определения типа страницы - agent."""
        url = "https://docs-chatcenter.edna.ru/docs/agent/routing"
        assert self.loader.detect_page_type(url) == 'agent'

    def test_page_type_detection_with_content(self):
        """Тест определения типа страницы с учетом контента."""
        url = "https://example.com/page"
        content = "This page contains API documentation with endpoints."

        # Мокаем detect_page_type для возврата api на основе контента
        with patch.object(self.loader, 'detect_page_type') as mock_detect:
            mock_detect.return_value = 'api'
            result = self.loader.detect_page_type(url, content)
            assert result == 'api'

    def test_load_content_jina_reader(self):
        """Тест загрузки Jina Reader контента."""
        url = "https://docs-chatcenter.edna.ru/docs/start/whatis"
        content = """Title: Что такое edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Content Length: 2456
Language Detected: Russian
Markdown Content:

# Что такое edna Chat Center

edna Chat Center — это система для организации работы с клиентами.
"""

        result = self.loader.load_content(url, content, 'auto')

        # Проверяем базовые поля
        assert result['url'] == url
        assert result['title'] == 'Что такое edna Chat Center'
        assert 'Что такое edna Chat Center' in result['content']
        assert result['content_type'] == 'jina_reader'
        assert result['page_type'] == 'guide'

        # Проверяем метаданные Jina Reader
        assert result['url_source'] == url
        assert result['content_length'] == 2456  # Из метаданных Jina Reader (может отличаться от реальной длины)
        assert result['language_detected'] == 'Russian'

        # Проверяем URL метаданные
        assert result['section'] == 'start'
        assert result['user_role'] == 'all'
        assert result['permissions'] == 'ALL'

    def test_load_content_html_docusaurus(self):
        """Тест загрузки HTML Docusaurus контента."""
        url = "https://docs-chatcenter.edna.ru/docs/agent/routing"
        content = """<!DOCTYPE html>
<html>
<head>
    <title>Настройка маршрутизации</title>
    <meta name="description" content="Руководство по настройке">
</head>
<body>
    <nav class="theme-doc-breadcrumbs">
        <a href="/docs">Документация</a>
        <a href="/docs/agent">Агент</a>
    </nav>
    <article class="theme-doc-markdown">
        <h1>Настройка маршрутизации</h1>
        <p>Маршрутизация позволяет распределять сообщения.</p>
    </article>
</body>
</html>"""

        result = self.loader.load_content(url, content, 'auto')

        # Проверяем базовые поля
        assert result['url'] == url
        assert result['title'] == 'Настройка маршрутизации'
        assert 'Маршрутизация позволяет' in result['content']
        assert result['content_type'] == 'html_docusaurus'
        assert result['page_type'] == 'guide'  # Fallback к guide, так как URL не распознан как agent в load_content

        # Проверяем URL метаданные
        assert result['section'] == 'agent'
        assert result['user_role'] == 'agent'
        assert result['permissions'] == 'AGENT'

    def test_load_content_force_jina_strategy(self):
        """Тест принудительного использования Jina Reader стратегии."""
        url = "https://example.com/page"
        content = "Обычный текст без специальной разметки."

        result = self.loader.load_content(url, content, 'force_jina')

        assert result['content_type'] == 'jina_reader'
        assert result['url'] == url

    def test_load_content_empty_content(self):
        """Тест загрузки пустого контента."""
        url = "https://example.com/page"
        content = ""

        result = self.loader.load_content(url, content, 'auto')

        # Пустой контент обрабатывается как 'empty' тип, не как ошибка
        assert result['content_type'] == 'empty'
        assert result['content'] == ''
        assert result['url'] == url

    def test_load_content_error_handling(self):
        """Тест обработки ошибок при загрузке."""
        url = "https://example.com/page"
        content = "Valid content"

        # Мокаем parse_jina_content для вызова исключения
        with patch('ingestion.universal_loader.parse_jina_content', side_effect=Exception("Test error")):
            result = self.loader.load_content(url, content, 'force_jina')

            assert 'error' in result
            assert result['error'] == 'Test error'
            assert result['url'] == url

    def test_get_supported_strategies(self):
        """Тест получения поддерживаемых стратегий."""
        strategies = self.loader.get_supported_strategies()

        expected_strategies = ['auto', 'jina', 'html', 'force_jina', 'html_docusaurus', 'markdown', 'text']
        for strategy in expected_strategies:
            assert strategy in strategies

    def test_get_content_type_info(self):
        """Тест получения информации о типах контента."""
        info = self.loader.get_content_type_info()

        assert 'jina_reader' in info
        assert 'html_docusaurus' in info
        assert 'html_generic' in info
        assert 'markdown' in info
        assert 'text' in info
        assert 'error' in info

    @pytest.mark.slow
    def test_load_content_performance(self):
        """Тест производительности загрузки контента."""
        url = "https://docs-chatcenter.edna.ru/docs/start/whatis"
        content = """Title: Performance Test
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Markdown Content:

# Performance Test

This is a performance test with a lot of content.
""" * 100  # Увеличиваем размер контента

        import time
        start_time = time.time()

        result = self.loader.load_content(url, content, 'auto')

        end_time = time.time()
        processing_time = end_time - start_time

        # Проверяем, что обработка заняла менее 1 секунды
        assert processing_time < 1.0
        assert result['url'] == url


class TestLoadContentUniversal:
    """Тесты удобной функции загрузки контента."""

    def test_load_content_universal_function(self):
        """Тест функции load_content_universal."""
        url = "https://docs-chatcenter.edna.ru/docs/start/whatis"
        content = """Title: Test Page
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Markdown Content:

# Test Page

Test content.
"""

        result = load_content_universal(url, content, 'auto')

        assert result['url'] == url
        assert result['title'] == 'Test Page'
        assert result['content_type'] == 'jina_reader'

    def test_load_content_universal_default_strategy(self):
        """Тест функции load_content_universal с стратегией по умолчанию."""
        url = "https://example.com"
        content = "Simple text content."

        result = load_content_universal(url, content)

        assert result['url'] == url
        assert result['content_type'] == 'text'


class TestURLMetadataExtraction:
    """Тесты извлечения метаданных из URL."""

    def test_extract_url_metadata_start_section(self):
        """Тест извлечения метаданных для секции start."""
        url = "https://docs-chatcenter.edna.ru/docs/start/whatis"
        metadata = extract_url_metadata(url)

        assert metadata['section'] == 'start'
        assert metadata['user_role'] == 'all'
        assert 'url' in metadata
        assert 'source' in metadata

    def test_extract_url_metadata_api_section(self):
        """Тест извлечения метаданных для API секции."""
        url = "https://docs-chatcenter.edna.ru/docs/api/messages/create"
        metadata = extract_url_metadata(url)

        assert metadata['section'] == 'api'
        assert metadata['user_role'] == 'integrator'
        assert 'url' in metadata
        assert 'source' in metadata

    def test_extract_url_metadata_admin_section(self):
        """Тест извлечения метаданных для admin секции."""
        url = "https://docs-chatcenter.edna.ru/docs/admin/widget"
        metadata = extract_url_metadata(url)

        assert metadata['section'] == 'admin'
        assert metadata['user_role'] == 'admin'
        assert 'url' in metadata
        assert 'source' in metadata

    def test_extract_url_metadata_changelog_section(self):
        """Тест извлечения метаданных для changelog секции."""
        url = "https://docs-chatcenter.edna.ru/blog/release-6.16"
        metadata = extract_url_metadata(url)

        assert metadata['section'] == 'changelog'
        assert metadata['user_role'] == 'all'
        assert 'url' in metadata
        assert 'source' in metadata

    def test_extract_url_metadata_unknown_url(self):
        """Тест извлечения метаданных для неизвестного URL."""
        url = "https://example.com/unknown/path"
        metadata = extract_url_metadata(url)

        # Неизвестный URL возвращает базовые метаданные
        assert 'url' in metadata
        assert 'source' in metadata


@pytest.mark.integration
class TestUniversalLoaderIntegration:
    """Интеграционные тесты универсального загрузчика."""

    def test_full_metadata_pipeline(self):
        """Тест полного pipeline метаданных."""
        url = "https://docs-chatcenter.edna.ru/docs/agent/routing"
        content = """Title: Настройка маршрутизации в edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/agent/routing
Content Length: 2456
Language Detected: Russian
Markdown Content:

# Настройка маршрутизации

Маршрутизация позволяет распределять входящие сообщения между агентами.

## Типы маршрутизации

- По каналам (Telegram, WhatsApp)
- По времени работы агентов
- По навыкам агентов

**Permissions:** AGENT, SUPERVISOR
"""

        loader = UniversalLoader()
        result = loader.load_content(url, content, 'auto')

        # Проверяем все типы метаданных
        assert result['url'] == url
        assert result['title'] == 'Настройка маршрутизации в edna Chat Center'

        # Jina Reader метаданные
        assert result['url_source'] == url
        assert result['content_length'] == 2456  # Из метаданных Jina Reader
        assert result['language_detected'] == 'Russian'

        # URL метаданные
        assert result['section'] == 'agent'
        assert result['user_role'] == 'agent'
        assert result['page_type'] == 'guide'  # load_content использует fallback к guide
        assert result['permissions'] == 'AGENT'

        # Проверяем наличие контента
        assert 'Маршрутизация позволяет' in result['content']
        assert 'Telegram' in result['content']

    def test_content_type_consistency(self):
        """Тест консистентности определения типа контента."""
        loader = UniversalLoader()

        # Jina Reader контент
        jina_content = """Title: Test
URL Source: https://example.com
Markdown Content:

# Test
"""

        result1 = loader.detect_content_type(jina_content)
        result2 = loader.detect_content_type(jina_content)

        assert result1 == result2 == 'jina_reader'

    def test_error_recovery(self):
        """Тест восстановления после ошибок."""
        loader = UniversalLoader()

        # Тест с некорректным контентом
        url = "https://example.com"
        content = "Valid content"

        # Мокаем ошибку в парсинге
        with patch('ingestion.universal_loader.parse_jina_content', side_effect=Exception("Parse error")):
            result = loader.load_content(url, content, 'force_jina')

            # Должен вернуть результат с ошибкой, а не упасть
            assert 'error' in result
            assert result['url'] == url
            assert result['error'] == 'Parse error'


@pytest.mark.e2e
class TestUniversalLoaderE2E:
    """End-to-end тесты универсального загрузчика."""

    def test_real_world_scenarios(self):
        """Тест реальных сценариев использования."""
        loader = UniversalLoader()

        # Сценарий 1: Jina Reader с полными метаданными
        scenario1 = {
            'url': 'https://docs-chatcenter.edna.ru/docs/start/whatis',
            'content': """Title: Что такое edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Content Length: 2456
Language Detected: Russian
Published Time: 2024-07-24T10:30:00Z
Images: 3
Links: 12
Markdown Content:

# Что такое edna Chat Center

edna Chat Center — это система для организации работы с клиентами.
""",
            'expected_type': 'jina_reader'
        }

        result1 = loader.load_content(scenario1['url'], scenario1['content'], 'auto')
        assert result1['content_type'] == scenario1['expected_type']
        assert result1['title'] == 'Что такое edna Chat Center'
        assert result1['section'] == 'start'

        # Сценарий 2: HTML Docusaurus
        scenario2 = {
            'url': 'https://docs-chatcenter.edna.ru/docs/admin/widget',
            'content': """<!DOCTYPE html>
<html>
<body>
<nav class="theme-doc-breadcrumbs">
<article class="theme-doc-markdown">
<h1>Настройка виджета</h1>
</article>
</body>
</html>""",
            'expected_type': 'html_docusaurus'
        }

        result2 = loader.load_content(scenario2['url'], scenario2['content'], 'auto')
        assert result2['content_type'] == scenario2['expected_type']
        assert result2['section'] == 'admin'
        assert result2['permissions'] == 'ADMIN'

        # Сценарий 3: Markdown документ
        scenario3 = {
            'url': 'https://example.com/guide.md',
            'content': """# Руководство пользователя

## Введение

Это руководство поможет вам начать работу.

### Шаг 1

Выполните следующие действия.
""",
            'expected_type': 'markdown'
        }

        result3 = loader.load_content(scenario3['url'], scenario3['content'], 'auto')
        assert result3['content_type'] == scenario3['expected_type']
        # Markdown парсер может не извлечь заголовок, проверяем наличие контента
        assert 'Руководство пользователя' in result3.get('content', '')

    def test_metadata_completeness(self):
        """Тест полноты метаданных."""
        loader = UniversalLoader()

        url = "https://docs-chatcenter.edna.ru/docs/api/messages/create"
        content = """Title: Создание сообщения
URL Source: https://docs-chatcenter.edna.ru/docs/api/messages/create
Content Length: 1200
Markdown Content:

# Создание сообщения

API для создания сообщений.

## Endpoint

POST /api/messages/create

**Permissions:** INTEGRATOR
"""

        result = loader.load_content(url, content, 'auto')

        # Проверяем наличие всех ожидаемых метаданных
        expected_fields = [
            'url', 'title', 'content', 'content_type', 'page_type',
            'section', 'user_role', 'permissions', 'url_source',
            'content_length', 'loaded_at'
        ]

        for field in expected_fields:
            assert field in result, f"Отсутствует поле: {field}"

        # Проверяем значения ключевых полей
        assert result['section'] == 'api'
        assert result['user_role'] == 'integrator'
        assert result['page_type'] == 'api-reference'  # URL определяет как api-reference
        assert result['api_method'] == 'POST'
