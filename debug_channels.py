#!/usr/bin/env python3
"""
Debug script to find articles about channels
"""
from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter

def debug_channels():
    # Ищем документы, содержащие информацию о каналах
    try:
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    {'key': 'content', 'match': {'text': 'канал'}}
                ]
            ),
            limit=10,
            with_payload=True
        )

        print(f'📋 Найдено {len(results[0])} документов с "канал":')
        for i, doc in enumerate(results[0], 1):
            payload = doc.payload
            print(f'\n{i}. {payload.get("title", "Без названия")}')
            print(f'   URL: {payload.get("url", "Без URL")}')
            content = str(payload.get("content", ""))
            print(f'   Content preview: {content[:300]}...')

            # Проверяем, содержит ли информацию о поддерживаемых каналах
            if 'telegram' in content.lower() and 'виджет' in content.lower():
                print('   ✅ Содержит информацию о Telegram и виджете!')
            elif 'telegram' in content.lower():
                print('   📱 Содержит информацию о Telegram')
            elif 'виджет' in content.lower():
                print('   🌐 Содержит информацию о виджете')

    except Exception as e:
        print(f'❌ Ошибка при поиске: {e}')

if __name__ == "__main__":
    debug_channels()
