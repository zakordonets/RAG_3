#!/usr/bin/env python3
"""Отладка проблем с тестами."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.universal_loader import UniversalLoader

def test_html_docusaurus():
    """Тест HTML Docusaurus."""
    loader = UniversalLoader()

    url = "https://docs-chatcenter.edna.ru/docs/agent/routing"
    content = """<!DOCTYPE html>
<html>
<head>
    <title>Настройка маршрутизации</title>
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

    print("URL:", url)
    print("Detect page type:", loader.detect_page_type(url))
    print("Detect content type:", loader.detect_content_type(content))

    result = loader.load_content(url, content, 'auto')

    print("\nResult:")
    print("URL:", result.get('url'))
    print("Title:", result.get('title'))
    print("Content type:", result.get('content_type'))
    print("Page type:", result.get('page_type'))
    print("Section:", result.get('section'))
    print("User role:", result.get('user_role'))
    print("Permissions:", result.get('permissions'))

def test_jina_reader():
    """Тест Jina Reader."""
    loader = UniversalLoader()

    url = "https://docs-chatcenter.edna.ru/docs/start/whatis"
    content = """Title: Что такое edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Content Length: 2456
Language Detected: Russian
Markdown Content:

# Что такое edna Chat Center

edna Chat Center — это система для организации работы с клиентами.
"""

    print("URL:", url)
    print("Detect page type:", loader.detect_page_type(url))
    print("Detect content type:", loader.detect_content_type(content))

    result = loader.load_content(url, content, 'auto')

    print("\nResult:")
    print("URL:", result.get('url'))
    print("Title:", result.get('title'))
    print("Content type:", result.get('content_type'))
    print("Page type:", result.get('page_type'))
    print("Content length (metadata):", result.get('content_length'))
    print("Content length (actual):", len(result.get('content', '')))
    print("URL source:", result.get('url_source'))
    print("Language:", result.get('language_detected'))

if __name__ == "__main__":
    print("=== HTML Docusaurus Test ===")
    test_html_docusaurus()

    print("\n=== Jina Reader Test ===")
    test_jina_reader()

