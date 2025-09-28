#!/usr/bin/env python3
"""
Debug script to check whatis article content
"""
from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter

def debug_whatis():
    # Ищем документы, содержащие 'whatis' в URL
    try:
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    {'key': 'url', 'match': {'text': 'whatis'}}
                ]
            ),
            limit=5,
            with_payload=True
        )

        print(f'📋 Найдено {len(results[0])} документов с whatis:')
        for i, doc in enumerate(results[0], 1):
            payload = doc.payload
            print(f'\n{i}. {payload.get("title", "Без названия")}')
            print(f'   URL: {payload.get("url", "Без URL")}')
            content = str(payload.get("content", ""))
            print(f'   Content preview: {content[:200]}...')

            # Ищем информацию о каналах
            if 'канал' in content.lower() or 'telegram' in content.lower() or 'виджет' in content.lower():
                print('   ✅ Содержит информацию о каналах!')
            else:
                print('   ❌ НЕ содержит информацию о каналах')

    except Exception as e:
        print(f'❌ Ошибка при поиске: {e}')

if __name__ == "__main__":
    debug_whatis()
