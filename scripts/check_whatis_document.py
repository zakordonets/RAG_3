#!/usr/bin/env python3
"""
Проверка наличия и качества документа "Что такое edna Chat Center"
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

def check_whatis_document():
    """Проверить документ 'Что такое edna Chat Center'"""
    print("🔍 Поиск документа 'Что такое edna Chat Center'")
    print("=" * 60)

    try:
        # Ищем документы с URL содержащим 'whatis'
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="url",
                        match=MatchValue(value="https://docs-chatcenter.edna.ru/docs/start/whatis")
                    )
                ]
            ),
            limit=10,
            with_payload=True,
            with_vectors=False
        )

        if results[0]:
            print(f"📄 Найдено {len(results[0])} документов с URL 'whatis':")
            print()

            for i, point in enumerate(results[0]):
                payload = point.payload
                url = payload.get('url', 'N/A')
                title = payload.get('title', 'N/A')
                text = payload.get('text', '')
                indexed_via = payload.get('indexed_via', 'unknown')
                content_length = payload.get('content_length', 0)

                print(f"  Документ {i+1}:")
                print(f"    ID: {point.id}")
                print(f"    URL: {url}")
                print(f"    Title: {title}")
                print(f"    indexed_via: {indexed_via}")
                print(f"    content_length: {content_length}")
                print(f"    text_preview: {text[:200]}...")
                print()

                # Проверим, содержит ли текст информацию о каналах
                if 'канал' in text.lower() or 'telegram' in text.lower() or 'веб-виджет' in text.lower():
                    print("    ✅ Содержит информацию о каналах")
                else:
                    print("    ❌ Не содержит информацию о каналах")
                print()
        else:
            print("❌ Документ 'Что такое edna Chat Center' не найден в коллекции")

        # Также проверим общую статистику по indexed_via
        print("\n📊 Статистика по indexed_via в коллекции:")
        all_results = client.scroll(
            collection_name=COLLECTION,
            limit=1000,  # Получаем больше документов для статистики
            with_payload=True,
            with_vectors=False
        )

        indexed_via_stats = {}
        content_length_stats = {'zero': 0, 'non_zero': 0}

        for point in all_results[0]:
            payload = point.payload
            indexed_via = payload.get('indexed_via', 'unknown')
            content_length = payload.get('content_length', 0)

            indexed_via_stats[indexed_via] = indexed_via_stats.get(indexed_via, 0) + 1

            if content_length == 0:
                content_length_stats['zero'] += 1
            else:
                content_length_stats['non_zero'] += 1

        print(f"  indexed_via статистика:")
        for via, count in indexed_via_stats.items():
            print(f"    {via}: {count}")

        print(f"  content_length статистика:")
        print(f"    Пустые документы (0): {content_length_stats['zero']}")
        print(f"    Документы с контентом (>0): {content_length_stats['non_zero']}")

    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    check_whatis_document()
