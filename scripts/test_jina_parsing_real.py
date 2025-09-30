#!/usr/bin/env python3
"""
Тест парсинга Jina Reader с реальными данными
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.parsers_migration import parse_jina_content
from ingestion.crawler import _jina_reader_fetch

def test_jina_parsing():
    """Тест парсинга Jina Reader"""
    print("🔍 ТЕСТ ПАРСИНГА JINA READER")
    print("=" * 60)

    # Тестируем разные URL
    test_urls = [
        "https://docs-chatcenter.edna.ru/blog",
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features"
    ]

    for url in test_urls:
        print(f"\n📄 Тестируем URL: {url}")
        print("-" * 40)

        try:
            # Получаем контент от Jina Reader
            jina_result = _jina_reader_fetch(url, timeout=30)
            print(f"   Jina результат: {len(jina_result)} символов")

            if len(jina_result) == 0:
                print("   ❌ Jina Reader вернул пустой результат")
                continue

            # Парсим контент
            parsed = parse_jina_content(jina_result)

            print(f"   Парсинг результат:")
            print(f"     Заголовок: '{parsed['title']}'")
            print(f"     Контент: {len(parsed['content'])} символов")

            if len(parsed['content']) == 0:
                print("   ❌ Парсер вернул пустой контент")
                print(f"     Первые 500 символов Jina результата:")
                print(f"     {jina_result[:500]}...")
            else:
                print("   ✅ Парсинг работает!")
                print(f"     Первые 200 символов контента:")
                print(f"     {parsed['content'][:200]}...")

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_jina_parsing()
