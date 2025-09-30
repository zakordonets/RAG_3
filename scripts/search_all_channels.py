#!/usr/bin/env python3
"""
Поиск всех упоминаний различных каналов связи
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

def search_all_channels():
    """Найти документы с упоминанием различных каналов"""
    print("🔍 Поиск документов с упоминанием различных каналов связи")
    print("=" * 70)

    # Список каналов для поиска
    channels = [
        'telegram', 'whatsapp', 'viber', 'авито', 'avito',
        'facebook', 'instagram', 'vk', 'вконтакте',
        'email', 'sms', 'звонок', 'call',
        'веб-виджет', 'мобильное приложение', 'мобильный'
    ]

    found_channels = {}

    for channel in channels:
        try:
            print(f"\n🔎 Поиск документов с '{channel}'...")

            results = client.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="text",
                            match=MatchValue(value=channel)
                        )
                    ]
                ),
                limit=20,
                with_payload=True,
                with_vectors=False
            )

            if results[0]:
                found_channels[channel] = len(results[0])
                print(f"   ✅ Найдено {len(results[0])} документов")

                # Показываем первые 3 документа
                for i, point in enumerate(results[0][:3]):
                    payload = point.payload
                    title = payload.get('title', 'N/A')
                    url = payload.get('url', 'N/A')
                    indexed_via = payload.get('indexed_via', 'unknown')

                    print(f"      {i+1}. {title}")
                    print(f"         URL: {url}")
                    print(f"         indexed_via: {indexed_via}")
            else:
                found_channels[channel] = 0
                print(f"   ❌ Не найдено")

        except Exception as e:
            print(f"   ❌ Ошибка поиска: {e}")
            found_channels[channel] = -1

    # Итоговая статистика
    print("\n" + "=" * 70)
    print("📊 ИТОГОВАЯ СТАТИСТИКА:")
    print()

    for channel, count in found_channels.items():
        if count > 0:
            print(f"   ✅ {channel}: {count} документов")
        elif count == 0:
            print(f"   ❌ {channel}: не найден")
        else:
            print(f"   ⚠️  {channel}: ошибка поиска")

    # Проверим общую статистику коллекции
    print(f"\n📄 Общая статистика коллекции:")
    all_results = client.scroll(
        collection_name=COLLECTION,
        limit=1000,
        with_payload=True,
        with_vectors=False
    )

    total_docs = len(all_results[0])
    jina_docs = sum(1 for point in all_results[0] if point.payload.get('indexed_via') == 'jina')
    unknown_docs = sum(1 for point in all_results[0] if point.payload.get('indexed_via') == 'unknown')

    print(f"   Всего документов: {total_docs}")
    print(f"   Документов с Jina Reader: {jina_docs}")
    print(f"   Документов с indexed_via: unknown: {unknown_docs}")

    # Проверим, есть ли документы с длинным контентом
    long_docs = sum(1 for point in all_results[0] if point.payload.get('content_length', 0) > 5000)
    print(f"   Документов с длинным контентом (>5000 символов): {long_docs}")

if __name__ == "__main__":
    search_all_channels()
