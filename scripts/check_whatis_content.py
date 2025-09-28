#!/usr/bin/env python3
"""
Проверка полного содержимого документа "Что такое edna Chat Center"
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

def check_whatis_content():
    """Проверить полное содержимое документа 'Что такое edna Chat Center'"""
    print("🔍 Проверка содержимого документа 'Что такое edna Chat Center'")
    print("=" * 70)

    try:
        # Ищем документ
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
            limit=1,
            with_payload=True,
            with_vectors=False
        )

        if not results[0]:
            print("❌ Документ не найден")
            return

        doc = results[0][0]
        text = doc.payload.get('text', '')
        title = doc.payload.get('title', 'N/A')
        url = doc.payload.get('url', 'N/A')

        print(f"📄 Документ: {title}")
        print(f"🔗 URL: {url}")
        print(f"📏 Длина контента: {len(text)} символов")
        print()

        # Показываем полный текст
        print("📝 Полное содержимое:")
        print("-" * 70)
        print(text)
        print("-" * 70)
        print()

        # Анализируем содержимое
        print("🔍 Анализ содержимого:")

        # Ищем упоминания каналов
        channels = ['telegram', 'веб-виджет', 'мобильный', 'email', 'facebook', 'viber', 'whatsapp']
        found_channels = []

        for channel in channels:
            if channel.lower() in text.lower():
                found_channels.append(channel)

        print(f"   Найденные каналы: {found_channels}")

        # Ищем предложения о каналах
        sentences = text.split('.')
        channel_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if any(channel.lower() in sentence.lower() for channel in channels):
                channel_sentences.append(sentence)

        if channel_sentences:
            print(f"\n📋 Предложения о каналах:")
            for i, sentence in enumerate(channel_sentences, 1):
                print(f"   {i}. {sentence}")

        # Проверяем, есть ли список каналов
        if 'канал' in text.lower() and ('поддерживается' in text.lower() or 'подключить' in text.lower()):
            print(f"\n✅ Документ содержит информацию о поддерживаемых каналах")
        else:
            print(f"\n❌ Документ НЕ содержит явную информацию о поддерживаемых каналах")

    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    check_whatis_content()
