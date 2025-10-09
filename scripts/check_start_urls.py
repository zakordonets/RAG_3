"""Проверка URL из раздела /start/"""
import sys
sys.path.insert(0, '.')

from app.services.search.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchText

# Ищем все URL, начинающиеся с /docs/start/
results = client.scroll(
    collection_name=COLLECTION,
    limit=100,
    with_payload=True,
    with_vectors=False
)

print("=" * 80)
print("📋 Проверка проиндексированных URL из раздела /start/")
print("=" * 80)

start_urls = []
all_urls = []

for point in results[0]:
    url = point.payload.get('url', point.payload.get('site_url', ''))
    all_urls.append(url)
    if '/start/' in url:
        start_urls.append({
            'url': url,
            'title': point.payload.get('title', 'N/A')
        })

print(f"\n✅ Всего проиндексировано документов: {len(all_urls)}")
print(f"📌 Из них из раздела /start/: {len(start_urls)}")

if start_urls:
    print("\n🔍 URL из раздела /start/:")
    for i, item in enumerate(start_urls, 1):
        print(f"   {i}. {item['url']}")
        print(f"      Title: {item['title']}")
else:
    print("\n❌ НЕТ проиндексированных URL из раздела /start/")
    print("\n💡 Рекомендация: запустите индексацию с включением этого раздела")

# Проверяем, есть ли в URL-ах вариации "whatis"
print("\n🔎 Поиск похожих URL (содержащих 'what'):")
what_urls = [u for u in all_urls if 'what' in u.lower()]
if what_urls:
    for url in what_urls[:5]:
        print(f"   - {url}")
else:
    print("   Не найдено")

print("\n" + "=" * 80)
