"""
Проверка, проиндексирован ли конкретный файл из docs
"""
import sys
sys.path.insert(0, '.')

from app.services.search.retrieval import client, COLLECTION

print("=" * 80)
print("🔍 ПРОВЕРКА ИНДЕКСАЦИИ ФАЙЛА 10-whatis.md")
print("=" * 80)

# Файл 10-start\10-whatis.md должен мапиться на URL:
# https://docs-chatcenter.edna.ru/docs/start/whatis
# (с drop_numeric_prefix_in_first_level: true)

possible_urls = [
    "https://docs-chatcenter.edna.ru/docs/start/whatis",
    "https://docs-chatcenter.edna.ru/docs/10-start/10-whatis",
    "https://docs-chatcenter.edna.ru/docs/start/10-whatis",
    "https://docs-chatcenter.edna.ru/docs/10-start/whatis",
]

print("\n📋 Проверяем возможные варианты URL:")
print("-" * 80)

found = False

for url in possible_urls:
    print(f"\n🔎 Проверяем: {url}")

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="url", match=MatchValue(value=url))]
            ),
            limit=10,
            with_payload=True,
            with_vectors=False
        )

        if results[0]:
            found = True
            print(f"   ✅ НАЙДЕНО! Чанков: {len(results[0])}")

            for i, point in enumerate(results[0][:2], 1):
                payload = point.payload
                print(f"\n   Чанк {i}:")
                print(f"   - ID: {point.id}")
                print(f"   - Title: {payload.get('title', 'N/A')}")
                print(f"   - chunk_index: {payload.get('chunk_index', 'N/A')}")
                text_preview = payload.get('text', '')[:200].replace('\n', ' ')
                print(f"   - Text: {text_preview}...")
        else:
            print(f"   ❌ Не найдено")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

if not found:
    print("\n" + "=" * 80)
    print("❌ ФАЙЛ НЕ ПРОИНДЕКСИРОВАН")
    print("=" * 80)
    print("\n💡 Возможные причины:")
    print("   1. Файл не был обработан при последней индексации")
    print("   2. Маппинг URL не соответствует ожидаемому")
    print("   3. Индексация не была запущена после добавления файла")
    print("\n🔧 Решение:")
    print("   Запустите индексацию Docusaurus файлов:")
    print("   python -m ingestion.run")
else:
    print("\n" + "=" * 80)
    print("✅ ФАЙЛ ПРОИНДЕКСИРОВАН")
    print("=" * 80)

print()
