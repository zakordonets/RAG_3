"""
Проверка текста SDK документа в Qdrant
"""
import sys
sys.path.insert(0, '.')

from app.retrieval.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Ищем документ по URL SDK документации
target_url = "https://docs-sdk.edna.ru/android/getting-started/installation"

print("=" * 80)
print("🔍 ПРОВЕРКА ТЕКСТА SDK ДОКУМЕНТА В QDRANT")
print("=" * 80)

try:
    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="site_url", match=MatchValue(value=target_url))]
        ),
        limit=10,
        with_payload=True,
        with_vectors=False
    )

    if results[0]:
        print(f"\n✅ НАЙДЕНО! Чанков: {len(results[0])}")

        for i, point in enumerate(results[0], 1):
            payload = point.payload
            print(f"\n{'='*80}")
            print(f"Чанк {i}:")
            print(f"  site_url: {payload.get('site_url', 'N/A')}")
            print(f"  title: {payload.get('title', 'N/A')}")

            text = payload.get('text', '')
            print(f"\n  Текст ({len(text)} символов):")

            # Ищем упоминание maven
            if 'maven' in text.lower():
                print(f"\n  ✅ Найдено упоминание 'maven'")
                # Ищем URL maven-pub.edna.ru
                if 'maven-pub.edna.ru' in text:
                    print(f"  ✅ URL 'maven-pub.edna.ru' ПРИСУТСТВУЕТ в тексте!")
                    # Показываем контекст
                    idx = text.lower().find('maven')
                    start = max(0, idx - 100)
                    end = min(len(text), idx + 300)
                    print(f"\n  Контекст вокруг 'maven':")
                    print(f"  {text[start:end]}")
                else:
                    print(f"  ❌ URL 'maven-pub.edna.ru' ОТСУТСТВУЕТ в тексте!")
                    # Показываем что есть
                    idx = text.lower().find('maven')
                    if idx >= 0:
                        start = max(0, idx - 100)
                        end = min(len(text), idx + 300)
                        print(f"\n  Контекст вокруг 'maven':")
                        print(f"  {text[start:end]}")
            else:
                print(f"  ⚠️  Упоминание 'maven' не найдено")
                # Показываем первые 500 символов
                print(f"\n  Первые 500 символов текста:")
                print(f"  {text[:500]}")
    else:
        print(f"\n❌ Документ не найден по URL: {target_url}")
        print("\nПопробуем найти по части URL...")

        # Ищем по части URL
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="site_url", match=MatchValue(value="android"))]
            ),
            limit=20,
            with_payload=True,
            with_vectors=False
        )

        if results[0]:
            print(f"\n✅ Найдено {len(results[0])} документов с 'android' в URL")
            for i, point in enumerate(results[0][:3], 1):
                payload = point.payload
                print(f"\n  Документ {i}: {payload.get('site_url', 'N/A')}")
                text = payload.get('text', '')
                if 'maven' in text.lower():
                    print(f"    ✅ Содержит 'maven'")
                    if 'maven-pub.edna.ru' in text:
                        print(f"    ✅ Содержит полный URL")
                    else:
                        print(f"    ❌ URL обрезан")

except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
