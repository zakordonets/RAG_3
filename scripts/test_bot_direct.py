#!/usr/bin/env python3
"""
Прямое тестирование бота для проверки ответов
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.orchestrator import handle_query

def test_bot_response():
    """Тестируем ответ бота на конкретный запрос"""
    query = "Какие каналы поддерживаются в чат-центре"

    print(f"🤖 Тестируем ответ бота на запрос: '{query}'")
    print("=" * 70)

    try:
        # Выполняем запрос
        print("🔍 Выполняем поиск...")
        response = handle_query(channel="test", chat_id="test", message=query)

        print(f"📝 Ответ бота:")
        print("-" * 70)
        print(response.get('answer', 'N/A'))
        print("-" * 70)
        print()

        print(f"📊 Детали ответа:")
        print(f"   Источники: {len(response.get('sources', []))}")
        print(f"   Контексты: {len(response.get('contexts', []))}")
        print(f"   Время обработки: {response.get('processing_time', 0):.2f}s")
        print()

        print(f"🔗 Источники:")
        for i, source in enumerate(response.get('sources', []), 1):
            print(f"   {i}. {source.get('title', 'N/A')}")
            print(f"      URL: {source.get('url', 'N/A')}")
            print(f"      Score: {source.get('score', 'N/A')}")
            print()

        print(f"📄 Контексты:")
        for i, context in enumerate(response.get('contexts', [])[:3], 1):  # Показываем первые 3
            print(f"   {i}. {context[:150]}...")
            print()

        # Проверяем, содержит ли ответ информацию о нужных каналах
        answer_lower = response.get('answer', '').lower()
        channels_mentioned = []

        if 'telegram' in answer_lower:
            channels_mentioned.append('Telegram')
        if 'whatsapp' in answer_lower:
            channels_mentioned.append('WhatsApp')
        if 'viber' in answer_lower:
            channels_mentioned.append('Viber')
        if 'авито' in answer_lower or 'avito' in answer_lower:
            channels_mentioned.append('Авито')
        if 'веб-виджет' in answer_lower:
            channels_mentioned.append('Веб-виджет')
        if 'мобильный' in answer_lower:
            channels_mentioned.append('Мобильные приложения')

        print(f"🎯 Анализ ответа:")
        print(f"   Упомянутые каналы: {', '.join(channels_mentioned) if channels_mentioned else 'Не найдены'}")

        expected_channels = ['Telegram', 'WhatsApp', 'Viber', 'Авито', 'Веб-виджет', 'Мобильные приложения']
        missing_channels = [ch for ch in expected_channels if ch not in channels_mentioned]

        if missing_channels:
            print(f"   ❌ Отсутствуют каналы: {', '.join(missing_channels)}")
        else:
            print(f"   ✅ Все ожидаемые каналы упомянуты")

        return response

    except Exception as e:
        print(f"❌ Ошибка при тестировании бота: {e}")
        return None

def main():
    """Основная функция"""
    test_bot_response()

if __name__ == "__main__":
    main()
