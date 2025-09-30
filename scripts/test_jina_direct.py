#!/usr/bin/env python3
"""
Прямой тест Jina Reader
"""
import sys
from pathlib import Path

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.crawler import _jina_reader_fetch
from ingestion.parsers_migration import parse_api_documentation, parse_release_notes, parse_faq_content, parse_guides
from ingestion.chunker import chunk_text


def test_jina_direct():
    """Тестирует Jina Reader напрямую"""
    test_urls = [
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features",
        "https://docs-chatcenter.edna.ru/docs/sdk/sdk-mobilechat"
    ]

    for url in test_urls:
        print(f"\n🔍 Тестируем: {url}")
        print("="*60)

        try:
            # 1. Прямой вызов Jina Reader
            print("1️⃣ Jina Reader:")
            jina_content = _jina_reader_fetch(url, timeout=30)
            print(f"   Длина: {len(jina_content) if jina_content else 0}")
            print(f"   Превью: {jina_content[:200] + '...' if jina_content and len(jina_content) > 200 else jina_content}")

            if not jina_content:
                print("   ❌ Jina Reader вернул пустой контент!")
                continue

            # 2. Парсинг контента
            print("\n2️⃣ Парсинг:")
            parsed_content = parse_api_documentation(jina_content)
            if not parsed_content:
                parsed_content = parse_guides(jina_content)
            if not parsed_content:
                parsed_content = parse_faq_content(jina_content)
            if not parsed_content:
                parsed_content = parse_release_notes(jina_content)

            if parsed_content:
                print(f"   Заголовок: {parsed_content.get('title', 'Без заголовка')}")
                print(f"   Длина контента: {len(parsed_content.get('content', ''))}")
                print(f"   Превью контента: {parsed_content.get('content', '')[:200] + '...' if len(parsed_content.get('content', '')) > 200 else parsed_content.get('content', '')}")
            else:
                print("   ❌ Парсинг не удался!")
                continue

            # 3. Чанкинг
            print("\n3️⃣ Чанкинг:")
            content = parsed_content.get('content', '')
            if content:
                chunks = chunk_text(content)
                print(f"   Количество чанков: {len(chunks)}")
                if chunks:
                    print(f"   Первый чанк: {chunks[0][:100] + '...' if len(chunks[0]) > 100 else chunks[0]}")
            else:
                print("   ❌ Нет контента для чанкинга!")

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_jina_direct()
