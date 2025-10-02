#!/usr/bin/env python3
"""
Тест парсинга через Jina Reader
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.crawler import _jina_reader_fetch
from ingestion.processors.content_processor import ContentProcessor


def test_jina_parsing():
    """Тест парсинга конкретной страницы через Jina Reader"""
    print("🔍 ТЕСТ ПАРСИНГА ЧЕРЕЗ JINA READER")
    print("=" * 50)

    # Тестируем разные URL
    test_urls = [
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/start/",
        "https://docs-chatcenter.edna.ru/docs/admin/",
        "https://docs-chatcenter.edna.ru/blog"
    ]

    for i, url in enumerate(test_urls, 1):
        print(f"\n📄 Тест {i}: {url}")

        try:
            # Загружаем через Jina Reader
            html = _jina_reader_fetch(url, timeout=30)
            print(f"   ✅ HTML загружен: {len(html)} символов")

            if len(html) > 0:
                print(f"   Первые 200 символов: {html[:200]}...")

                # Парсим контент
                processor = ContentProcessor()
                processed = processor.process(html, url, "html")
                text = processed.content
                title = processed.title

                print(f"   📝 Парсинг:")
                print(f"      Заголовок: {title}")
                print(f"      Текст: {len(text)} символов")
                print(f"      Тип страницы: {processed.page_type}")

                if len(text) > 0:
                    print(f"      Первые 100 символов текста: {text[:100]}...")
                    print(f"   ✅ Парсинг успешен!")
                else:
                    print(f"   ❌ Текст пустой после парсинга!")

                    # Дополнительная диагностика
                    print(f"   🔍 Диагностика HTML:")
                    print(f"      Содержит <title>: {'<title>' in html}")
                    print(f"      Содержит <body>: {'<body>' in html}")
                    print(f"      Содержит <main>: {'<main>' in html}")
                    print(f"      Содержит <article>: {'<article>' in html}")
                    print(f"      Содержит <div>: {'<div>' in html}")

                    # Проверим, не является ли это Jina Reader форматом
                    if "Title:" in html and "URL Source:" in html:
                        print(f"   📋 Обнаружен Jina Reader формат!")
                        lines = html.split('\n')
                        for line in lines[:10]:
                            if line.strip():
                                print(f"      {line}")
            else:
                print(f"   ❌ HTML пустой!")

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()


def test_direct_jina_format():
    """Тест прямого парсинга Jina Reader формата"""
    print("\n🔍 ТЕСТ ПАРСИНГА JINA READER ФОРМАТА")
    print("=" * 50)

    # Тестовый Jina Reader контент
    jina_content = """Title: Что такое edna Chat Center

URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis

edna Chat Center — это платформа для управления многоканальными коммуникациями с клиентами. Она позволяет объединить различные каналы связи в едином интерфейсе.

## Основные возможности

- **Многоканальность**: Поддержка различных мессенджеров и каналов связи
- **Централизованное управление**: Единый интерфейс для всех каналов
- **Автоматизация**: Настройка автоматических ответов и маршрутизации

## Поддерживаемые каналы

В edna Chat Center поддерживаются следующие каналы:

1. **Telegram** - популярный мессенджер
2. **WhatsApp** - международный мессенджер
3. **Viber** - мессенджер с возможностью звонков
4. **Авито** - платформа для объявлений
5. **Веб-виджет** - встроенный чат на сайте
6. **Мобильные приложения** - iOS и Android приложения
"""

    print(f"📄 Тестовый Jina Reader контент:")
    print(f"   Длина: {len(jina_content)} символов")

    try:
        # Тестируем парсинг
        parsed = parse_guides(jina_content)
        text = parsed.get("text", "")
        title = parsed.get("title", "")

        print(f"📝 Результат парсинга:")
        print(f"   Заголовок: {title}")
        print(f"   Текст: {len(text)} символов")

        if len(text) > 0:
            print(f"   ✅ Парсинг Jina Reader формата работает!")
            print(f"   Первые 200 символов: {text[:200]}...")
        else:
            print(f"   ❌ Парсинг не работает!")

    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ ПАРСИНГА JINA READER")
    print("=" * 80)

    # Тест 1: Парсинг реальных страниц
    test_jina_parsing()

    # Тест 2: Парсинг Jina Reader формата
    test_direct_jina_format()


if __name__ == "__main__":
    main()
