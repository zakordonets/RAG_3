#!/usr/bin/env python3
"""
Проверка содержимого документа "Версия 6.16"
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

def check_version_616():
    """Проверить содержимое документа 'Версия 6.16'"""
    print("🔍 Проверка документа 'Версия 6.16'")
    print("=" * 70)

    try:
        # Ищем документ "Версия 6.16"
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="title",
                        match=MatchValue(value="Версия 6.16 🛠")
                    )
                ]
            ),
            limit=5,
            with_payload=True,
            with_vectors=False
        )

        if results[0]:
            print(f"📄 Найдено {len(results[0])} документов 'Версия 6.16':")
            print()

            for i, point in enumerate(results[0]):
                payload = point.payload
                title = payload.get('title', 'N/A')
                url = payload.get('url', 'N/A')
                text = payload.get('text', '')
                indexed_via = payload.get('indexed_via', 'unknown')
                content_length = payload.get('content_length', 0)

                print(f"  Документ {i+1}:")
                print(f"    ID: {point.id}")
                print(f"    Title: {title}")
                print(f"    URL: {url}")
                print(f"    indexed_via: {indexed_via}")
                print(f"    content_length: {content_length}")
                print(f"    text_preview: {text[:300]}...")
                print()

                # Проверим, содержит ли текст информацию о каналах
                text_lower = text.lower()
                channels_found = []

                if 'telegram' in text_lower:
                    channels_found.append('Telegram')
                if 'whatsapp' in text_lower:
                    channels_found.append('WhatsApp')
                if 'viber' in text_lower:
                    channels_found.append('Viber')
                if 'авито' in text_lower or 'avito' in text_lower:
                    channels_found.append('Авито')
                if 'веб-виджет' in text_lower:
                    channels_found.append('Веб-виджет')
                if 'мобильный' in text_lower:
                    channels_found.append('Мобильные приложения')

                print(f"    Каналы в тексте: {', '.join(channels_found) if channels_found else 'Не найдены'}")

                # Найдем предложения с упоминанием каналов
                sentences = text.split('.')
                channel_sentences = []
                for sentence in sentences:
                    if any(channel.lower() in sentence.lower() for channel in ['telegram', 'канал', 'поддерживается']):
                        channel_sentences.append(sentence.strip())

                if channel_sentences:
                    print(f"    Релевантные предложения:")
                    for sentence in channel_sentences[:3]:
                        print(f"      • {sentence[:150]}...")
                print()

                # Покажем полный текст для первого документа
                if i == 0:
                    print(f"📝 ПОЛНЫЙ ТЕКСТ ДОКУМЕНТА:")
                    print("-" * 70)
                    print(text)
                    print("-" * 70)
                    print()
        else:
            print("❌ Документ 'Версия 6.16' не найден в коллекции")

        # Также поищем документы с похожими названиями
        print("🔍 Поиск похожих документов...")
        all_results = client.scroll(
            collection_name=COLLECTION,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )

        similar_docs = []
        for point in all_results[0]:
            title = point.payload.get('title', '')
            if '6.16' in title or 'версия' in title.lower():
                similar_docs.append({
                    'title': title,
                    'url': point.payload.get('url', 'N/A'),
                    'content_length': point.payload.get('content_length', 0)
                })

        if similar_docs:
            print(f"📋 Найдено {len(similar_docs)} похожих документов:")
            for doc in similar_docs:
                print(f"   • {doc['title']}")
                print(f"     URL: {doc['url']}")
                print(f"     Длина: {doc['content_length']}")
                print()

    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    check_version_616()
