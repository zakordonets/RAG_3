#!/usr/bin/env python3
"""
Отладка парсера Jina Reader
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.parsers_migration import parse_jina_content


def test_parser():
    """Тест парсера с реальными данными"""

    # Реальные данные от Jina Reader
    jina_content = """Title: Что такое edna Chat Center | edna Chat Center

URL Source: http://docs-chatcenter.edna.ru/docs/start/whatis

Markdown Content:
Обновлено:

24 июля 2024

edna Chat Center — это гибкое и масштабируемое решение для контактных центров, которое помогает обрабатывать все обращения клиентов из неголосовых каналов в едином пространстве. Также edna Chat Center поддерживает интеграции с системами продаж типа CRM и HelpDesk, системами планирования времени, чат-ботами, и легко встраивается в IT-архитектуру.

## Что такое edna Chat Center

edna Chat Center — это платформа для управления многоканальными коммуникациями с клиентами. Она позволяет объединить различные каналы связи в едином интерфейсе.

### Основные возможности

- **Многоканальность**: Поддержка различных мессенджеров и каналов связи
- **Централизованное управление**: Единый интерфейс для всех каналов
- **Автоматизация**: Настройка автоматических ответов и маршрутизации

### Поддерживаемые каналы

В edna Chat Center поддерживаются следующие каналы:

1. **Telegram** - популярный мессенджер
2. **WhatsApp** - международный мессенджер
3. **Viber** - мессенджер с возможностью звонков
4. **Авито** - платформа для объявлений
5. **Веб-виджет** - встроенный чат на сайте
6. **Мобильные приложения** - iOS и Android приложения"""

    print("🔍 ТЕСТ ПАРСЕРА JINA READER")
    print("=" * 50)

    print(f"📄 Исходный контент:")
    print(f"   Длина: {len(jina_content)} символов")
    print(f"   Первые 300 символов:")
    print(f"   {jina_content[:300]}...")

    print(f"\n🔧 Тестирование парсера:")

    # Тестируем парсер
    result = parse_jina_content(jina_content)

    print(f"📝 Результат парсинга:")
    print(f"   Заголовок: '{result['title']}'")
    print(f"   Текст: {len(result['content'])} символов")

    if result['content']:
        print(f"   ✅ Парсинг работает!")
        print(f"   Первые 200 символов текста:")
        print(f"   {result['content'][:200]}...")
    else:
        print(f"   ❌ Текст пустой!")

        # Дополнительная диагностика
        print(f"\n🔍 Диагностика:")
        lines = jina_content.split('\n')
        print(f"   Всего строк: {len(lines)}")

        for i, line in enumerate(lines[:10]):
            print(f"   Строка {i+1}: '{line}'")

        # Ищем "Markdown Content:"
        markdown_start = -1
        for i, line in enumerate(lines):
            if line.startswith("Markdown Content:"):
                markdown_start = i
                print(f"   ✅ Найдена 'Markdown Content:' на строке {i+1}")
                break

        if markdown_start >= 0:
            print(f"   Содержимое после 'Markdown Content:':")
            for i in range(markdown_start + 1, min(markdown_start + 6, len(lines))):
                print(f"     Строка {i+1}: '{lines[i]}'")


if __name__ == "__main__":
    test_parser()
