#!/usr/bin/env python3
"""
Тест парсера для Jina Reader
"""
import sys
from pathlib import Path
import re

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.crawler import _jina_reader_fetch


def parse_jina_content(jina_content: str) -> dict:
    """Парсит контент от Jina Reader"""
    if not jina_content:
        return {"title": "", "content": ""}

    # Извлекаем заголовок из первой строки
    title = ""
    content = ""

    lines = jina_content.split('\n')

    # Ищем заголовок в формате "Title: ..."
    for line in lines:
        if line.startswith("Title:"):
            title_part = line.split("Title:")[1].strip()
            if "|" in title_part:
                title = title_part.split("|")[0].strip()
            else:
                title = title_part
            break

    # Ищем начало контента после "Markdown Content:"
    content_started = False
    content_lines = []

    for line in lines:
        if line.startswith("Markdown Content:"):
            content_started = True
            continue

        if content_started:
            content_lines.append(line)

    if content_lines:
        content = '\n'.join(content_lines).strip()

    # Если не нашли через "Markdown Content:", берем все после заголовка
    if not content and title:
        # Ищем контент после заголовка
        title_found = False
        content_lines = []

        for line in lines:
            if line.startswith("Title:"):
                title_found = True
                continue

            if title_found and line.strip():
                content_lines.append(line)

        if content_lines:
            content = '\n'.join(content_lines).strip()

    return {"title": title, "content": content}


def test_jina_parser():
    """Тестирует парсер Jina Reader"""
    test_urls = [
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features",
        "https://docs-chatcenter.edna.ru/docs/sdk/sdk-mobilechat"
    ]

    for url in test_urls:
        print(f"\n🔍 Тестируем: {url}")
        print("="*60)

        try:
            # 1. Получаем контент от Jina Reader
            jina_content = _jina_reader_fetch(url, timeout=30)
            print(f"1️⃣ Jina Reader: {len(jina_content)} символов")

            # 2. Парсим контент
            parsed = parse_jina_content(jina_content)
            print(f"2️⃣ Парсинг:")
            print(f"   Заголовок: {parsed['title']}")
            print(f"   Длина контента: {len(parsed['content'])}")

            if parsed['content']:
                preview = parsed['content'][:200] + "..." if len(parsed['content']) > 200 else parsed['content']
                print(f"   Превью: {preview}")
            else:
                print(f"   Превью: [ПУСТОЙ КОНТЕНТ]")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_jina_parser()
