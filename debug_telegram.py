#!/usr/bin/env python3
"""
Debug script to find articles about Telegram and channels
"""
from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter

def debug_telegram():
    # Ищем документы, содержащие "telegram"
    try:
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    {'key': 'content', 'match': {'text': 'telegram'}}
                ]
            ),
            limit=10,
            with_payload=True
        )

        print(f'📋 Найдено {len(results[0])} документов с "telegram":')
        for i, doc in enumerate(results[0], 1):
            payload = doc.payload
            print(f'\n{i}. {payload.get("title", "Без названия")}')
            print(f'   URL: {payload.get("url", "Без URL")}')
            content = str(payload.get("content", ""))
            print(f'   Content preview: {content[:300]}...')

    except Exception as e:
        print(f'❌ Ошибка при поиске: {e}')

def debug_widget():
    # Ищем документы, содержащие "виджет"
    try:
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    {'key': 'content', 'match': {'text': 'виджет'}}
                ]
            ),
            limit=10,
            with_payload=True
        )

        print(f'\n📋 Найдено {len(results[0])} документов с "виджет":')
        for i, doc in enumerate(results[0], 1):
            payload = doc.payload
            print(f'\n{i}. {payload.get("title", "Без названия")}')
            print(f'   URL: {payload.get("url", "Без URL")}')
            content = str(payload.get("content", ""))
            print(f'   Content preview: {content[:300]}...')

    except Exception as e:
        print(f'❌ Ошибка при поиске: {e}')

if __name__ == "__main__":
    debug_telegram()
    debug_widget()
