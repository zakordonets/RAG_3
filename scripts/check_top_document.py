#!/usr/bin/env python3
"""
Проверка топ документа для генерации ответа
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.orchestrator import handle_query

def check_top_document():
    """Проверить топ документ для генерации"""
    query = "Какие каналы поддерживаются в чат-центре"

    print(f"🔍 Проверка топ документа для запроса: '{query}'")
    print("=" * 70)

    try:
        # Выполняем запрос
        response = handle_query(channel="test", chat_id="test", message=query)

        sources = response.get('sources', [])
        contexts = response.get('contexts', [])

        print(f"📊 Общая информация:")
        print(f"   Источников: {len(sources)}")
        print(f"   Контекстов: {len(contexts)}")
        print()

        if sources:
            print(f"🏆 ТОП-5 источников для генерации:")
            for i, source in enumerate(sources[:5], 1):
                title = source.get('title', 'N/A')
                url = source.get('url', 'N/A')
                score = source.get('score', 'N/A')

                print(f"   {i}. {title}")
                print(f"      URL: {url}")
                print(f"      Score: {score}")
                print()

                # Для первого документа покажем больше деталей
                if i == 1:
                    print(f"   📄 ДЕТАЛИ ТОП-1 ДОКУМЕНТА:")

                    # Найдем соответствующий контекст, если есть
                    if i <= len(contexts):
                        context = contexts[i-1]
                        print(f"      Контекст: {context[:300]}...")
                        print()

                        # Проверим, содержит ли контекст информацию о каналах
                        context_lower = context.lower()
                        channels_in_context = []

                        if 'telegram' in context_lower:
                            channels_in_context.append('Telegram')
                        if 'whatsapp' in context_lower:
                            channels_in_context.append('WhatsApp')
                        if 'viber' in context_lower:
                            channels_in_context.append('Viber')
                        if 'авито' in context_lower or 'avito' in context_lower:
                            channels_in_context.append('Авито')
                        if 'веб-виджет' in context_lower:
                            channels_in_context.append('Веб-виджет')
                        if 'мобильный' in context_lower:
                            channels_in_context.append('Мобильные приложения')

                        print(f"      Каналы в контексте: {', '.join(channels_in_context) if channels_in_context else 'Не найдены'}")
                    else:
                        print(f"      ❌ Контекст не найден")
                    print()

        # Проверим ответ бота
        answer = response.get('answer', '')
        print(f"🤖 Ответ бота:")
        print(f"   {answer[:200]}...")
        print()

        # Анализ соответствия топ документа и ответа
        if sources and contexts:
            top_title = sources[0].get('title', '')
            top_context = contexts[0] if len(contexts) > 0 else ''

            print(f"🔍 Анализ соответствия:")
            print(f"   Топ документ: {top_title}")

            # Проверим, упоминается ли топ документ в ответе
            if top_title.lower() in answer.lower():
                print(f"   ✅ Топ документ упомянут в ответе")
            else:
                print(f"   ❌ Топ документ НЕ упомянут в ответе")

            # Проверим, есть ли ссылки на топ документ
            top_url = sources[0].get('url', '')
            if top_url in answer:
                print(f"   ✅ URL топ документа есть в ответе")
            else:
                print(f"   ❌ URL топ документа НЕ найден в ответе")

    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    check_top_document()
