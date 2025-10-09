"""Получаем полный текст чанка"""
import sys
sys.path.insert(0, '.')

from app.services.search.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

target_url = "https://docs-chatcenter.edna.ru/docs/start/whatis"

results = client.scroll(
    collection_name=COLLECTION,
    scroll_filter=Filter(
        must=[FieldCondition(key="canonical_url", match=MatchValue(value=target_url))]
    ),
    limit=10,
    with_payload=True,
    with_vectors=False
)

if results[0]:
    point = results[0][0]
    text = point.payload.get('text', '')

    print("=" * 80)
    print("ПОЛНЫЙ ТЕКСТ ЧАНКА")
    print("=" * 80)
    print(text)
    print("=" * 80)
    print(f"\nДлина: {len(text)} символов")
    print(f"Содержит 'К edna Chat Center можно подключить': {'К edna Chat Center можно подключить' in text}")
    print(f"Содержит список каналов: {('WhatsApp' in text or 'Telegram' in text)}")
