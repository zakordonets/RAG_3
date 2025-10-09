"""
Глубокий анализ: сравнение оригинала и проиндексированного чанка
"""
import sys
sys.path.insert(0, '.')

from app.services.search.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue

target_url = "https://docs-chatcenter.edna.ru/docs/start/whatis"

# Получаем чанки из Qdrant
results = client.scroll(
    collection_name=COLLECTION,
    scroll_filter=Filter(
        must=[FieldCondition(key="canonical_url", match=MatchValue(value=target_url))]
    ),
    limit=100,
    with_payload=True,
    with_vectors=False
)

# Читаем оригинальный файл
with open(r"C:\CC_RAG\docs\10-start\10-whatis.md", "r", encoding="utf-8") as f:
    original = f.read()

print("=" * 100)
print("АНАЛИЗ: ОРИГИНАЛ vs QDRANT")
print("=" * 100)

print("\n📄 ОРИГИНАЛЬНЫЙ ФАЙЛ:")
print(f"  Длина: {len(original)} символов")
print(f"  Строк: {len(original.splitlines())}")

# Подсчитываем структурные элементы
h2_count = original.count('\n## ')
h3_count = original.count('\n### ')
table_count = original.count('|---|')
list_items = original.count('\n- ')
code_blocks = original.count('```')

print(f"\n  Структура:")
print(f"    - Заголовков H2: {h2_count}")
print(f"    - Заголовков H3: {h3_count}")
print(f"    - Таблиц: {table_count}")
print(f"    - Списков: {list_items}")
print(f"    - Блоков кода: {code_blocks}")

print("\n" + "=" * 100)
print("📦 ЧАНКИ В QDRANT:")
print("=" * 100)

if results[0]:
    chunks = results[0]
    print(f"\n  Всего чанков: {len(chunks)}")

    for i, point in enumerate(chunks, 1):
        payload = point.payload
        text = payload.get('text', '')

        print(f"\n  Чанк #{i}:")
        print(f"    - ID: {point.id}")
        print(f"    - chunk_index: {payload.get('chunk_index', 'N/A')}")
        print(f"    - Длина: {len(text)} символов")
        print(f"    - Title: {payload.get('title', 'N/A')}")

        # Анализируем, что попало в чанк
        chunk_h2 = text.count('\n## ') + text.count('## ')  # Может быть в начале
        chunk_h3 = text.count('\n### ')
        chunk_tables = text.count('|---|')
        chunk_lists = text.count('\n- ')

        print(f"    - Заголовков H2: {chunk_h2}")
        print(f"    - Таблиц: {chunk_tables}")
        print(f"    - Элементов списка: {chunk_lists}")

        # Проверяем наличие ключевых секций
        sections_in_chunk = []
        if "Роли в edna Chat Center" in text:
            sections_in_chunk.append("Роли")
        if "Каналы в edna Chat Center" in text:
            sections_in_chunk.append("Каналы")
        if "К edna Chat Center можно подключить" in text:
            sections_in_chunk.append("Список каналов")

        print(f"    - Секции: {', '.join(sections_in_chunk) if sections_in_chunk else 'Нет основных секций'}")

        # Показываем начало и конец
        print(f"\n    Начало (100 симв): {text[:100]}...")
        print(f"    Конец (100 симв): ...{text[-100:]}")

print("\n" + "=" * 100)
print("🔍 КРИТИЧЕСКИЙ АНАЛИЗ:")
print("=" * 100)

# Считаем покрытие
total_qdrant_chars = sum(len(p.payload.get('text', '')) for p in chunks)
coverage = (total_qdrant_chars / len(original)) * 100

print(f"\n1. ПОКРЫТИЕ КОНТЕНТА:")
print(f"   Оригинал: {len(original)} символов")
print(f"   В Qdrant: {total_qdrant_chars} символов")
print(f"   Покрытие: {coverage:.1f}%")

if len(chunks) == 1:
    print(f"\n2. ❌ ПРОБЛЕМА: Весь документ в ОДНОМ чанке!")
    print(f"   - Смешаны разные темы (роли + каналы)")
    print(f"   - Таблица смешана с текстом")
    print(f"   - Низкая точность поиска по конкретным темам")

print("\n3. СЕМАНТИЧЕСКАЯ КОГЕРЕНТНОСТЬ:")
chunk_text = chunks[0].payload.get('text', '') if chunks else ''
# Проверяем "расстояние" между темами
roles_pos = chunk_text.find("Роли в edna Chat Center")
channels_pos = chunk_text.find("К edna Chat Center можно подключить")

if roles_pos != -1 and channels_pos != -1:
    distance = channels_pos - roles_pos
    print(f"   Расстояние между темами 'Роли' и 'Каналы': {distance} символов")
    if distance > 500:
        print(f"   ⚠️  Темы далеко друг от друга - низкая когерентность")

print("\n4. СТРУКТУРНАЯ РАЗБИВКА:")
if chunk_h2 > 1:
    print(f"   ❌ В одном чанке {chunk_h2} заголовка H2 - разные темы!")
if chunk_tables > 0:
    print(f"   ⚠️  Таблица внутри чанка может искажать семантику")

print("\n" + "=" * 100)
