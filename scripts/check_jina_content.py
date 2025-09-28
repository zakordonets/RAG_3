#!/usr/bin/env python3
"""
Проверка контента от Jina Reader
"""
import sys
from pathlib import Path

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter


def check_jina_content():
    """Проверяет контент от Jina Reader"""
    try:
        # Ищем документы с indexed_via = 'jina'
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=[{'key': 'indexed_via', 'match': {'text': 'jina'}}]),
            limit=5,
            with_payload=True
        )

        docs = results[0]
        print(f"🔍 Проверяем контент от Jina Reader ({len(docs)} документов):")
        print("="*60)

        for i, doc in enumerate(docs, 1):
            payload = doc.payload
            title = payload.get('title', 'Без названия')
            content = payload.get('text', '')

            print(f"\n📄 Документ {i}: {title}")
            print(f"   Длина контента: {len(content)}")
            print(f"   indexed_via: {payload.get('indexed_via', 'НЕТ')}")
            print(f"   chunk_index: {payload.get('chunk_index', 'НЕТ')}")
            print(f"   content_length: {payload.get('content_length', 'НЕТ')}")

            if content:
                preview = content[:200] + "..." if len(content) > 200 else content
                print(f"   Превью: {preview}")

                # Проверяем русский текст
                has_russian = any(ord(c) > 127 for c in content[:200])
                print(f"   Русский текст: {'✅' if has_russian else '❌'}")
            else:
                print(f"   Превью: [ПУСТОЙ КОНТЕНТ]")
                print(f"   Русский текст: ❌")

        # Статистика
        total_docs = len(docs)
        empty_docs = sum(1 for doc in docs if len(doc.payload.get('text', '').strip()) == 0)
        russian_docs = sum(1 for doc in docs if any(ord(c) > 127 for c in doc.payload.get('text', '')[:200]))

        print(f"\n📊 Статистика:")
        print(f"   Всего документов: {total_docs}")
        print(f"   Пустых: {empty_docs} ({empty_docs/total_docs*100:.1f}%)")
        print(f"   С русским текстом: {russian_docs} ({russian_docs/total_docs*100:.1f}%)")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    check_jina_content()
