"""
Проверка: есть ли поле text в payload чанков Qdrant
"""
import sys
sys.path.insert(0, '.')

from app.services.search.retrieval import client, COLLECTION

print("=" * 100)
print("🔍 ПРОВЕРКА НАЛИЧИЯ ПОЛЯ 'text' В QDRANT PAYLOAD")
print("=" * 100)

# Получаем несколько чанков для анализа
results = client.scroll(
    collection_name=COLLECTION,
    limit=20,
    with_payload=True,
    with_vectors=False
)

if not results[0]:
    print("❌ Коллекция пустая")
    sys.exit(1)

points = results[0]

print(f"\n✅ Получено {len(points)} чанков для анализа\n")
print("=" * 100)

# Анализируем структуру payload
has_text_count = 0
no_text_count = 0
empty_text_count = 0

for i, point in enumerate(points[:10], 1):
    payload = point.payload

    has_text = 'text' in payload
    text_value = payload.get('text', None)
    text_length = len(text_value) if text_value else 0

    if has_text:
        if text_length > 0:
            has_text_count += 1
        else:
            empty_text_count += 1
    else:
        no_text_count += 1

    url = payload.get('url', payload.get('canonical_url', payload.get('site_url', 'N/A')))

    print(f"\nЧанк #{i}:")
    print(f"  URL: {url[:80]}...")
    print(f"  Title: {payload.get('title', 'N/A')[:60]}")
    print(f"  Поле 'text' присутствует: {'✅ ДА' if has_text else '❌ НЕТ'}")

    if has_text:
        print(f"  Длина text: {text_length} символов")
        if text_length > 0:
            print(f"  Начало: {text_value[:80]}...")
        else:
            print(f"  ⚠️  text = пустая строка!")

    # Проверяем альтернативные поля
    chunk_text = payload.get('chunk_text', None)
    content_length = payload.get('content_length', None)

    if chunk_text:
        print(f"  ℹ️  Есть chunk_text: {len(chunk_text)} символов")
    if content_length:
        print(f"  ℹ️  Есть content_length: {content_length}")

    # Список всех ключей payload
    if i == 1:
        print(f"\n  📋 Все ключи payload:")
        for key in sorted(payload.keys()):
            value = payload[key]
            if isinstance(value, str):
                print(f"     - {key}: {type(value).__name__} (len={len(value)})")
            else:
                print(f"     - {key}: {type(value).__name__}")

print("\n" + "=" * 100)
print("📊 ИТОГОВАЯ СТАТИСТИКА:")
print("=" * 100)

total = len(points[:10])
print(f"\n  Проверено чанков: {total}")
print(f"  ✅ Поле 'text' есть и не пустое: {has_text_count} ({100*has_text_count/total:.0f}%)")
print(f"  ⚠️  Поле 'text' пустое: {empty_text_count} ({100*empty_text_count/total:.0f}%)")
print(f"  ❌ Поле 'text' отсутствует: {no_text_count} ({100*no_text_count/total:.0f}%)")

print("\n" + "=" * 100)

if no_text_count > 0 or empty_text_count > 0:
    print("❌ ПРОБЛЕМА ПОДТВЕРЖДЕНА!")
    print("   Поле 'text' отсутствует или пустое в некоторых чанках")
    print("   Это КРИТИЧЕСКИ влияет на:")
    print("   - Boosting по содержимому")
    print("   - Reranking (нечего ранжировать)")
    print("   - Context optimization")
else:
    print("✅ Поле 'text' присутствует и заполнено во всех чанках")

print("=" * 100)
