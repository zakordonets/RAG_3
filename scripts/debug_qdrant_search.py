#!/usr/bin/env python3
"""
Отладка поиска в Qdrant
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

def debug_qdrant_search():
    """Отладить поиск в Qdrant"""
    print("🔍 Отладка поиска в Qdrant")
    print("=" * 50)

    try:
        # Получим несколько документов для анализа
        print("1. Получаем несколько документов для анализа...")
        results = client.scroll(
            collection_name=COLLECTION,
            limit=5,
            with_payload=True,
            with_vectors=False
        )

        for i, point in enumerate(results[0]):
            payload = point.payload
            title = payload.get('title', 'N/A')
            text = payload.get('text', '')

            print(f"\n   Документ {i+1}: {title}")
            print(f"   Длина текста: {len(text)} символов")
            print(f"   Первые 200 символов: {text[:200]}...")

            # Проверим, есть ли в тексте слова "веб-виджет" или "мобильный"
            if 'веб-виджет' in text.lower():
                print(f"   ✅ Содержит 'веб-виджет'")
            if 'мобильный' in text.lower():
                print(f"   ✅ Содержит 'мобильный'")
            if 'канал' in text.lower():
                print(f"   ✅ Содержит 'канал'")

        # Попробуем разные способы поиска
        print(f"\n2. Тестируем разные способы поиска...")

        # Способ 1: Поиск по полю text с MatchValue
        print(f"\n   Способ 1: Поиск по полю 'text' с MatchValue('веб-виджет')")
        try:
            results1 = client.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="text",
                            match=MatchValue(value="веб-виджет")
                        )
                    ]
                ),
                limit=5,
                with_payload=True,
                with_vectors=False
            )
            print(f"   Результат: {len(results1[0])} документов")
        except Exception as e:
            print(f"   Ошибка: {e}")

        # Способ 2: Поиск по полю title
        print(f"\n   Способ 2: Поиск по полю 'title' с MatchValue('веб-виджет')")
        try:
            results2 = client.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="title",
                            match=MatchValue(value="веб-виджет")
                        )
                    ]
                ),
                limit=5,
                with_payload=True,
                with_vectors=False
            )
            print(f"   Результат: {len(results2[0])} документов")
        except Exception as e:
            print(f"   Ошибка: {e}")

        # Способ 3: Получить все документы и поискать в Python
        print(f"\n   Способ 3: Поиск в Python по всем документам")
        all_results = client.scroll(
            collection_name=COLLECTION,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )

        found_docs = []
        for point in all_results[0]:
            text = point.payload.get('text', '').lower()
            if 'веб-виджет' in text:
                found_docs.append({
                    'title': point.payload.get('title', 'N/A'),
                    'url': point.payload.get('url', 'N/A')
                })

        print(f"   Результат: {len(found_docs)} документов с 'веб-виджет'")
        for i, doc in enumerate(found_docs[:3]):
            print(f"      {i+1}. {doc['title']}")
            print(f"         URL: {doc['url']}")

        # Способ 4: Проверим структуру полей
        print(f"\n   Способ 4: Структура полей документа")
        if results[0]:
            sample_payload = results[0][0].payload
            print(f"   Доступные поля: {list(sample_payload.keys())}")

            # Проверим типы полей
            for key, value in sample_payload.items():
                print(f"      {key}: {type(value).__name__}")

    except Exception as e:
        print(f"❌ Ошибка при отладке: {e}")

if __name__ == "__main__":
    debug_qdrant_search()
