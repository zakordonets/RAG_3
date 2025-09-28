#!/usr/bin/env python3
"""
Полная переиндексация с использованием Jina Reader для обхода блокировки ботов
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.crawler import _jina_reader_fetch, SEED_URLS
from ingestion.parsers import extract_main_text
from ingestion.chunker import chunk_text_with_overlap
from ingestion.indexer import upsert_chunks
from app.services.retrieval import client, COLLECTION
from bs4 import BeautifulSoup
from tqdm import tqdm


async def reindex_with_jina():
    """Полная переиндексация через Jina Reader"""

    print("🚀 ЗАПУСК ПОЛНОЙ ПЕРЕИНДЕКСАЦИИ ЧЕРЕЗ JINA READER")
    print("="*60)

    # Очищаем старый индекс
    print("\n1️⃣ Очищаем старый индекс...")
    try:
        client.delete_collection(COLLECTION)
        print("   ✅ Старый индекс очищен")
    except Exception as e:
        print(f"   ⚠️ Ошибка при очистке: {e}")

    # Создаем новую коллекцию
    print("\n2️⃣ Создаем новую коллекцию...")
    try:
        from qdrant_client.models import VectorParams, Distance
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={
                "dense": VectorParams(size=1024, distance=Distance.COSINE),
                "sparse": VectorParams(size=65536, distance=Distance.DOT)
            }
        )
        print("   ✅ Новая коллекция создана")
    except Exception as e:
        print(f"   ❌ Ошибка при создании коллекции: {e}")
        return

    # Список URL для индексации
    urls_to_index = [
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features",
        "https://docs-chatcenter.edna.ru/docs/sdk/sdk-mobilechat",
        "https://docs-chatcenter.edna.ru/docs/chat-bot/bot-testing",
        "https://docs-chatcenter.edna.ru/docs/api/external-api/agents/get-agent-status",
        "https://docs-chatcenter.edna.ru/docs/admin/routing/",
        "https://docs-chatcenter.edna.ru/docs/start/",
        "https://docs-chatcenter.edna.ru/docs/agent/",
        "https://docs-chatcenter.edna.ru/docs/supervisor/",
        "https://docs-chatcenter.edna.ru/docs/admin/",
        "https://docs-chatcenter.edna.ru/docs/chat-bot/",
        "https://docs-chatcenter.edna.ru/docs/api/index/",
        "https://docs-chatcenter.edna.ru/docs/faq/",
        "https://docs-chatcenter.edna.ru/blog/",
    ]

    print(f"\n3️⃣ Индексируем {len(urls_to_index)} страниц...")

    all_chunks = []
    successful_pages = 0
    failed_pages = 0

    for i, url in enumerate(tqdm(urls_to_index, desc="Индексация страниц")):
        try:
            # Получаем контент через Jina Reader
            jina_text = _jina_reader_fetch(url, timeout=30)

            if not jina_text or len(jina_text) < 100:
                print(f"   ⚠️ Пустой контент для {url}")
                failed_pages += 1
                continue

            # Проверяем наличие русского текста
            has_russian = any(ord(c) > 127 for c in jina_text[:500])
            if not has_russian:
                print(f"   ⚠️ Нет русского текста для {url}")
                failed_pages += 1
                continue

            # Парсим контент
            soup = BeautifulSoup(jina_text, 'html.parser')
            main_text = extract_main_text(soup)

            # Если extract_main_text не сработал, используем весь текст
            if not main_text or len(main_text) < 100:
                main_text = jina_text

            # Чанкируем текст
            chunks = chunk_text_with_overlap(main_text, min_tokens=50, max_tokens=500)

            if not chunks:
                print(f"   ⚠️ Нет чанков для {url}")
                failed_pages += 1
                continue

            # Извлекаем заголовок
            title_elem = soup.find('h1')
            title = title_elem.get_text().strip() if title_elem else url.split('/')[-1].replace('-', ' ').title()

            # Определяем тип страницы
            page_type = "guide"
            if "/api/" in url:
                page_type = "api"
            elif "/faq/" in url:
                page_type = "faq"
            elif "/blog/" in url:
                page_type = "blog"

            # Создаем чанки для индексации
            for j, chunk_text in enumerate(chunks):
                chunk_data = {
                    "text": chunk_text,
                    "payload": {
                        "url": url,
                        "page_type": page_type,
                        "source": "docs-site",
                        "language": "ru",
                        "title": title,
                        "text": chunk_text,
                        "chunk_index": j,
                        "indexed_via": "jina_reader"
                    }
                }
                all_chunks.append(chunk_data)

            successful_pages += 1
            print(f"   ✅ {url}: {len(chunks)} чанков")

        except Exception as e:
            print(f"   ❌ Ошибка для {url}: {e}")
            failed_pages += 1
            continue

    print(f"\n📊 Статистика индексации:")
    print(f"   ✅ Успешно: {successful_pages} страниц")
    print(f"   ❌ Ошибок: {failed_pages} страниц")
    print(f"   📄 Всего чанков: {len(all_chunks)}")

    if not all_chunks:
        print("   ❌ Нет чанков для индексации!")
        return

    # Батчевая индексация
    print(f"\n4️⃣ Выполняем батчевую индексацию...")

    batch_size = 50
    total_indexed = 0

    with tqdm(total=len(all_chunks), desc="Индексация чанков") as pbar:
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            try:
                indexed_count = upsert_chunks(batch)
                total_indexed += indexed_count
                pbar.update(len(batch))
            except Exception as e:
                print(f"   ❌ Ошибка индексации батча {i//batch_size + 1}: {e}")
                pbar.update(len(batch))

    print(f"\n✅ ИНДЕКСАЦИЯ ЗАВЕРШЕНА!")
    print(f"   📊 Проиндексировано: {total_indexed} чанков")
    print(f"   📊 Успешных страниц: {successful_pages}")
    print(f"   📊 Ошибок: {failed_pages}")

    # Проверяем качество индексации
    print(f"\n5️⃣ Проверяем качество индексации...")

    try:
        # Получаем статистику
        info = client.get_collection(COLLECTION)
        total_docs = info.points_count

        # Проверяем наличие русского контента
        results = client.scroll(
            collection_name=COLLECTION,
            limit=100,
            with_payload=True
        )

        docs = results[0]
        russian_docs = 0
        for doc in docs:
            content = str(doc.payload.get("content", ""))
            if content and any(ord(c) > 127 for c in content[:200]):
                russian_docs += 1

        russian_pct = (russian_docs / len(docs) * 100) if docs else 0

        print(f"   📊 Всего документов: {total_docs}")
        print(f"   🇷🇺 Русских документов: {russian_docs} ({russian_pct:.1f}%)")

        if russian_pct >= 80:
            print("   ✅ КАЧЕСТВО ИНДЕКСАЦИИ: ОТЛИЧНО!")
        elif russian_pct >= 50:
            print("   ⚠️ КАЧЕСТВО ИНДЕКСАЦИИ: ХОРОШО")
        else:
            print("   ❌ КАЧЕСТВО ИНДЕКСАЦИИ: ПЛОХО")

    except Exception as e:
        print(f"   ❌ Ошибка при проверке качества: {e}")

    print("\n" + "="*60)
    print("🎉 ПЕРЕИНДЕКСАЦИЯ ЗАВЕРШЕНА!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(reindex_with_jina())
