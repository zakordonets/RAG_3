#!/usr/bin/env python3
"""
Debug script to check what's in the index
"""
from app.services.retrieval import client, COLLECTION

def debug_index():
    try:
        # Получаем общую информацию о коллекции
        info = client.get_collection(COLLECTION)
        print(f'📊 Коллекция: {COLLECTION}')
        print(f'📊 Количество документов: {info.points_count}')

        # Получаем несколько случайных документов
        results = client.scroll(
            collection_name=COLLECTION,
            limit=5,
            with_payload=True
        )

        print(f'\n📋 Примеры документов:')
        for i, doc in enumerate(results[0], 1):
            payload = doc.payload
            print(f'\n{i}. {payload.get("title", "Без названия")}')
            print(f'   URL: {payload.get("url", "Без URL")}')
            content = str(payload.get("content", ""))
            print(f'   Content preview: {content[:200]}...')

            # Проверяем, есть ли русский текст
            if any(ord(c) > 127 for c in content[:100]):
                print('   ✅ Содержит русский текст')
            else:
                print('   ❌ НЕ содержит русский текст')

    except Exception as e:
        print(f'❌ Ошибка: {e}')

if __name__ == "__main__":
    debug_index()
