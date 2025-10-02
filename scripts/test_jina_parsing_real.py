#!/usr/bin/env python3
"""
Тест парсинга Jina Reader с реальными данными
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.processors.content_processor import ContentProcessor
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
            processor = ContentProcessor()
            processed = processor.process(jina_result, url, "jina")

            print(f"   Парсинг результат:")
            print(f"     Заголовок: '{processed.title}'")
            print(f"     Контент: {len(processed.content)} символов")
            print(f"     Тип страницы: {processed.page_type}")

            if len(processed.content) == 0:
                print("   ❌ Парсер вернул пустой контент")
                print(f"     Первые 500 символов Jina результата:")
                print(f"     {jina_result[:500]}...")
            else:
                print("   ✅ Парсинг работает!")
                print(f"     Первые 200 символов контента:")
                print(f"     {processed.content[:200]}...")

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_jina_parsing()
