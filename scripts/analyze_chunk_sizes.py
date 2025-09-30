#!/usr/bin/env python3
"""
Анализ размеров чанков и распределения информации
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION

def analyze_chunk_sizes():
    """Анализ размеров чанков и распределения информации"""
    print("🔍 АНАЛИЗ РАЗМЕРОВ ЧАНКОВ И РАСПРЕДЕЛЕНИЯ ИНФОРМАЦИИ")
    print("=" * 80)

    try:
        # Получаем все документы из коллекции
        all_points = client.scroll(
            collection_name=COLLECTION,
            limit=10000,  # Получаем все документы
            with_payload=True,
            with_vectors=False
        )[0]

        print(f"📊 Всего документов в коллекции: {len(all_points)}")

        # Анализ размеров чанков
        content_lengths = []
        chunk_indices = []

        for point in all_points:
            payload = point.payload or {}
            content_length = payload.get('content_length', 0)
            chunk_index = payload.get('chunk_index', 0)

            content_lengths.append(content_length)
            chunk_indices.append(chunk_index)

        # Статистика по размерам
        print("\n📏 СТАТИСТИКА ПО РАЗМЕРАМ КОНТЕНТА:")
        print(f"   Минимальный размер: {min(content_lengths)} символов")
        print(f"   Максимальный размер: {max(content_lengths)} символов")
        print(f"   Средний размер: {sum(content_lengths) / len(content_lengths):.0f} символов")
        print(f"   Медианный размер: {sorted(content_lengths)[len(content_lengths)//2]} символов")

        # Распределение по диапазонам
        ranges = [
            (0, 500, "Очень маленькие"),
            (500, 1000, "Маленькие"),
            (1000, 2000, "Средние"),
            (2000, 5000, "Большие"),
            (5000, float('inf'), "Очень большие")
        ]

        print("\n📊 РАСПРЕДЕЛЕНИЕ ПО РАЗМЕРАМ:")
        for min_size, max_size, label in ranges:
            count = sum(1 for length in content_lengths if min_size <= length < max_size)
            percentage = (count / len(content_lengths)) * 100
            print(f"   {label} ({min_size}-{max_size if max_size != float('inf') else '∞'}): {count} ({percentage:.1f}%)")

        # Анализ чанков по документам
        print("\n🔍 АНАЛИЗ ЧАНКОВ ПО ДОКУМЕНТАМ:")

        # Группируем по URL
        docs_by_url = {}
        for point in all_points:
            payload = point.payload or {}
            url = payload.get('url', 'unknown')
            chunk_index = payload.get('chunk_index', 0)
            content_length = payload.get('content_length', 0)

            if url not in docs_by_url:
                docs_by_url[url] = []
            docs_by_url[url].append((chunk_index, content_length))

        # Анализ документов с множественными чанками
        multi_chunk_docs = []
        for url, chunks in docs_by_url.items():
            if len(chunks) > 1:
                total_length = sum(length for _, length in chunks)
                multi_chunk_docs.append((url, len(chunks), total_length))

        multi_chunk_docs.sort(key=lambda x: x[1], reverse=True)

        print(f"\n📄 Документов с множественными чанками: {len(multi_chunk_docs)}")
        print("\n🏆 ТОП-10 ДОКУМЕНТОВ С НАИБОЛЬШИМ КОЛИЧЕСТВОМ ЧАНКОВ:")

        for i, (url, chunk_count, total_length) in enumerate(multi_chunk_docs[:10], 1):
            title = url.split('/')[-1] or url.split('/')[-2] or url
            print(f"   {i:2d}. {title}")
            print(f"       URL: {url}")
            print(f"       Чанков: {chunk_count}")
            print(f"       Общая длина: {total_length} символов")
            print(f"       Средний размер чанка: {total_length // chunk_count} символов")
            print()

        # Поиск документов с информацией о каналах
        print("🔍 ПОИСК ДОКУМЕНТОВ С ИНФОРМАЦИЕЙ О КАНАЛАХ:")

        channel_docs = []
        channel_keywords = ['telegram', 'whatsapp', 'viber', 'авито', 'канал', 'каналы']

        for point in all_points:
            payload = point.payload or {}
            text = payload.get('text', '').lower()
            url = payload.get('url', '')
            title = payload.get('title', '')
            content_length = payload.get('content_length', 0)

            # Считаем количество ключевых слов
            keyword_matches = sum(1 for keyword in channel_keywords if keyword in text)

            if keyword_matches >= 2:  # Документы с 2+ упоминаниями каналов
                channel_docs.append((url, title, keyword_matches, content_length, text[:200]))

        # Сортируем по количеству ключевых слов
        channel_docs.sort(key=lambda x: x[2], reverse=True)

        print(f"\n📋 Найдено {len(channel_docs)} документов с информацией о каналах:")

        for i, (url, title, keyword_count, length, preview) in enumerate(channel_docs[:15], 1):
            print(f"   {i:2d}. {title}")
            print(f"       URL: {url}")
            print(f"       Ключевых слов: {keyword_count}/6")
            print(f"       Длина: {length} символов")
            print(f"       Превью: {preview}...")
            print()

        # Анализ конкретного документа "Что такое edna Chat Center"
        print("🎯 АНАЛИЗ ДОКУМЕНТА 'Что такое edna Chat Center':")

        whatis_chunks = []
        for point in all_points:
            payload = point.payload or {}
            if 'docs/start/whatis' in payload.get('url', ''):
                chunk_index = payload.get('chunk_index', 0)
                content_length = payload.get('content_length', 0)
                text = payload.get('text', '')
                whatis_chunks.append((chunk_index, content_length, text))

        if whatis_chunks:
            whatis_chunks.sort(key=lambda x: x[0])
            print(f"   Всего чанков: {len(whatis_chunks)}")

            total_length = sum(length for _, length, _ in whatis_chunks)
            print(f"   Общая длина: {total_length} символов")
            print(f"   Средний размер чанка: {total_length // len(whatis_chunks)} символов")

            print("\n   📄 Содержимое чанков:")
            for i, (chunk_index, length, text) in enumerate(whatis_chunks, 1):
                print(f"      Чанк {chunk_index}: {length} символов")
                print(f"         {text[:100]}...")
                print()
        else:
            print("   ❌ Документ не найден")

        # Рекомендации по улучшению
        print("💡 РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ:")

        small_chunks = sum(1 for length in content_lengths if length < 1000)
        small_percentage = (small_chunks / len(content_lengths)) * 100

        if small_percentage > 50:
            print(f"   ⚠️  {small_percentage:.1f}% чанков меньше 1000 символов - слишком мелкое разбиение")
            print("   📝 Рекомендация: Увеличить CHUNK_MIN_TOKENS и CHUNK_MAX_TOKENS")

        if len(multi_chunk_docs) > len(all_points) * 0.3:
            print(f"   ⚠️  Много документов разбито на чанки ({len(multi_chunk_docs)} из {len(all_points)})")
            print("   📝 Рекомендация: Использовать семантическое разбиение вместо фиксированного размера")

        # Проверка текущих настроек
        print("\n⚙️  ТЕКУЩИЕ НАСТРОЙКИ ЧАНКИНГА:")
        from app.config import CONFIG
        print(f"   CHUNK_MIN_TOKENS: {CONFIG.chunk_min_tokens}")
        print(f"   CHUNK_MAX_TOKENS: {CONFIG.chunk_max_tokens}")

    except Exception as e:
        print(f"❌ Ошибка при анализе: {e}")

if __name__ == "__main__":
    analyze_chunk_sizes()
