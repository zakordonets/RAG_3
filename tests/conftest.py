"""
Общие фикстуры и утилиты для тестов.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any


@pytest.fixture
def mock_requests_get():
    """Фикстура для мокирования requests.get."""
    with patch('requests.get') as mock_get:
        yield mock_get


@pytest.fixture
def mock_qdrant_client():
    """Фикстура для мокирования Qdrant клиента."""
    with patch('app.services.search.retrieval.client') as mock_client:
        yield mock_client


@pytest.fixture
def sample_jina_content():
    """Образец контента от Jina Reader."""
    return """Title: Тестовая страница
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Content Length: 2456
Language Detected: Russian
Published Time: 2024-07-24T10:30:00Z
Images: 3
Links: 12
Markdown Content:

# Заголовок

Содержимое страницы.
"""


@pytest.fixture
def sample_html_content():
    """Образец HTML контента."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>Тестовая страница</title>
</head>
<body>
    <h1>Заголовок</h1>
    <p>Содержимое страницы.</p>
</body>
</html>"""


@pytest.fixture
def sample_markdown_content():
    """Образец Markdown контента."""
    return """# Заголовок

Содержимое страницы.

## Подзаголовок

Еще содержимое.
"""


@pytest.fixture
def test_urls():
    """Тестовые URL для различных разделов."""
    return {
        'guide': 'https://docs-chatcenter.edna.ru/docs/start/whatis',
        'api': 'https://docs-chatcenter.edna.ru/docs/api/messages',
        'faq': 'https://docs-chatcenter.edna.ru/faq',
        'changelog': 'https://docs-chatcenter.edna.ru/blog/release-6.16',
        'admin': 'https://docs-chatcenter.edna.ru/docs/admin/widget',
        'supervisor': 'https://docs-chatcenter.edna.ru/docs/supervisor/threadcontrol',
        'agent': 'https://docs-chatcenter.edna.ru/docs/agent/routing',
    }


class TestDataFactory:
    """Фабрика тестовых данных."""

    @staticmethod
    def create_jina_content(title: str = "Тестовая страница",
                          url: str = "https://docs-chatcenter.edna.ru/docs/start/whatis",
                          content: str = "# Заголовок\n\nСодержимое страницы.") -> str:
        """Создает тестовый контент от Jina Reader."""
        return f"""Title: {title}
URL Source: {url}
Content Length: 2456
Language Detected: Russian
Published Time: 2024-07-24T10:30:00Z
Images: 3
Links: 12
Markdown Content:

{content}
"""

    @staticmethod
    def create_html_content(title: str = "Тестовая страница",
                          content: str = "<h1>Заголовок</h1><p>Содержимое страницы.</p>") -> str:
        """Создает тестовый HTML контент."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
</head>
<body>
    {content}
</body>
</html>"""

    @staticmethod
    def create_markdown_content(title: str = "Заголовок",
                              content: str = "Содержимое страницы.") -> str:
        """Создает тестовый Markdown контент."""
        return f"""# {title}

{content}

## Подзаголовок

Еще содержимое.
"""


@pytest.fixture
def test_data_factory():
    """Фикстура для фабрики тестовых данных."""
    return TestDataFactory()
