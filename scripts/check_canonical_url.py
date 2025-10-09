"""
Проверка по canonical_url
"""
import sys
sys.path.insert(0, '.')

from app.services.search.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

target_url = "https://docs-chatcenter.edna.ru/docs/start/whatis"

print("=" * 80)
print("🔍 ПРОВЕРКА ПО CANONICAL_URL")
print("=" * 80)

# Проверяем canonical_url
try:
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
        print(f"\n✅ НАЙДЕНО по canonical_url! Чанков: {len(results[0])}")
        
        for i, point in enumerate(results[0], 1):
            payload = point.payload
            print(f"\n{'='*80}")
            print(f"Чанк {i}:")
            print(f"  ID: {point.id}")
            print(f"  Title: {payload.get('title', 'N/A')}")
            print(f"  URL: {payload.get('url', 'N/A')}")
            print(f"  Canonical URL: {payload.get('canonical_url', 'N/A')}")
            print(f"  chunk_index: {payload.get('chunk_index', 'N/A')}")
            print(f"  content_length: {payload.get('content_length', 'N/A')}")
            
            text = payload.get('text', '')
            print(f"\n  Текст ({len(text)} символов):")
            print(f"  {text[:500]}...")
            
            # Проверяем наличие ключевых слов
            keywords = ['канал', 'подключить', 'whatsapp', 'telegram', 'viber']
            found_keywords = [kw for kw in keywords if kw.lower() in text.lower()]
            if found_keywords:
                print(f"\n  ✅ Найденные ключевые слова: {', '.join(found_keywords)}")
    else:
        print("\n❌ НЕ НАЙДЕНО по canonical_url")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\n" + "=" * 80)

