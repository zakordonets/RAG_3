#!/usr/bin/env python3
"""
Поиск информации о Telegram в документах
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

def find_telegram_info():
    """Найти документы с информацией о Telegram"""
    print("🔍 Поиск документов с информацией о Telegram")
    print("=" * 60)

    try:
        # Ищем все документы, содержащие "telegram"
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="text",
                        match=MatchValue(value="telegram")
                    )
                ]
            ),
            limit=50,
            with_payload=True,
            with_vectors=False
        )

        print(f"📄 Найдено {len(results[0])} документов с упоминанием 'telegram':")
        print()

        for i, point in enumerate(results[0]):
            payload = point.payload
            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            text = payload.get('text', '')
            content_length = payload.get('content_length', 0)
            indexed_via = payload.get('indexed_via', 'unknown')

            print(f"  {i+1}. {title}")
            print(f"     URL: {url}")
            print(f"     indexed_via: {indexed_via}")
            print(f"     content_length: {content_length}")

            # Найдем предложения с "telegram"
            sentences = text.split('.')
            telegram_sentences = []
            for sentence in sentences:
                if 'telegram' in sentence.lower():
                    telegram_sentences.append(sentence.strip())

            if telegram_sentences:
                print(f"     Предложения с 'telegram':")
                for sentence in telegram_sentences[:2]:  # Показываем первые 2
                    print(f"       • {sentence[:100]}...")
            print()

        # Также поищем документы с "канал" и "поддерживается"
        print("\n" + "=" * 60)
        print("🔍 Поиск документов с 'канал' и 'поддерживается'")

        # Ищем документы с "канал"
        channel_results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="text",
                        match=MatchValue(value="канал")
                    )
                ]
            ),
            limit=20,
            with_payload=True,
            with_vectors=False
        )

        print(f"📄 Найдено {len(channel_results[0])} документов с упоминанием 'канал':")
        print()

        for i, point in enumerate(channel_results[0][:5]):  # Показываем первые 5
            payload = point.payload
            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            text = payload.get('text', '')

            print(f"  {i+1}. {title}")
            print(f"     URL: {url}")

            # Найдем предложения с "канал"
            sentences = text.split('.')
            channel_sentences = []
            for sentence in sentences:
                if 'канал' in sentence.lower() and ('поддерживается' in sentence.lower() or 'подключить' in sentence.lower()):
                    channel_sentences.append(sentence.strip())

            if channel_sentences:
                print(f"     Релевантные предложения:")
                for sentence in channel_sentences[:2]:
                    print(f"       • {sentence[:100]}...")
            print()

    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")

if __name__ == "__main__":
    find_telegram_info()
