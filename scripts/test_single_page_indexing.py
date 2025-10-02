#!/usr/bin/env python3
"""
Тестирует индексацию одной страницы для проверки качества
"""
import asyncio
import json
import sys
from pathlib import Path
from loguru import logger

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.crawler import crawl_with_sitemap_progress
from ingestion.processors.html_parser import HTMLParser
from ingestion.chunker import chunk_text_with_overlap
from ingestion.indexer import upsert_chunks
from bs4 import BeautifulSoup


async def test_single_page_indexing():
    """Тестирует индексацию одной страницы"""

    # URL для тестирования
    test_url = "https://docs-chatcenter.edna.ru/docs/start/whatis"

    print(f"🧪 Тестируем индексацию страницы: {test_url}")

    try:
        # 1. Получаем HTML страницы
        print("\n1️⃣ Получаем HTML страницы...")
        pages = crawl_with_sitemap_progress(base_url=test_url, strategy="http", use_cache=False, max_pages=1)

        if not pages:
            print("❌ Не удалось получить страницу")
            return

        page = pages[0]
        html = page["html"]
        url = page["url"]

        print(f"   ✅ Получено {len(html)} символов HTML")

        # 2. Парсим контент
        print("\n2️⃣ Парсим контент...")
        html_parser = HTMLParser()
        processed = html_parser.parse(url, html)
        main_text = processed.content

        print(f"   ✅ Извлечено {len(main_text)} символов текста")
        print(f"   📝 Превью: {main_text[:200]}...")

        # Проверяем наличие русского текста
        has_russian = any(ord(c) > 127 for c in main_text[:500])
        print(f"   {'✅' if has_russian else '❌'} Русский текст: {'ДА' if has_russian else 'НЕТ'}")

        # 3. Чанкируем текст
        print("\n3️⃣ Чанкируем текст...")
        chunks = chunk_text_with_overlap(main_text, min_tokens=50, max_tokens=500)

        print(f"   ✅ Создано {len(chunks)} чанков")

        # Анализируем чанки
        russian_chunks = 0
        for i, chunk in enumerate(chunks):
            if any(ord(c) > 127 for c in chunk[:200]):
                russian_chunks += 1
                print(f"   📄 Чанк {i+1}: {chunk[:100]}...")

        print(f"   {'✅' if russian_chunks > 0 else '❌'} Русских чанков: {russian_chunks}/{len(chunks)}")

        # 4. Подготавливаем данные для индексации
        print("\n4️⃣ Подготавливаем данные для индексации...")

        # Извлекаем заголовок
        title_elem = soup.find('h1')
        title = title_elem.get_text().strip() if title_elem else "Без названия"

        # Определяем тип страницы
        page_type = "guide"
        if "/api/" in url:
            page_type = "api"
        elif "/faq/" in url:
            page_type = "faq"

        # Создаем чанки для индексации
        chunks_to_index = []
        for i, chunk_text in enumerate(chunks):
            chunk_data = {
                "text": chunk_text,
                "payload": {
                    "url": url,
                    "page_type": page_type,
                    "source": "docs-site",
                    "language": "ru",
                    "title": title,
                    "text": chunk_text,
                    "chunk_index": i
                }
            }
            chunks_to_index.append(chunk_data)

        print(f"   ✅ Подготовлено {len(chunks_to_index)} чанков для индексации")

        # 5. Индексируем (только если есть русский текст)
        if russian_chunks > 0:
            print("\n5️⃣ Индексируем чанки...")
            try:
                indexed_count = upsert_chunks(chunks_to_index)
                print(f"   ✅ Успешно проиндексировано {indexed_count} чанков")
            except Exception as e:
                print(f"   ❌ Ошибка индексации: {e}")
        else:
            print("\n5️⃣ Пропускаем индексацию - нет русского текста")

        # 6. Проверяем результат индексации
        print("\n6️⃣ Проверяем результат индексации...")
        from app.services.retrieval import client, COLLECTION
        from qdrant_client.models import Filter

        # Ищем документы с этой страницы
        results = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[
                    {'key': 'url', 'match': {'text': test_url}}
                ]
            ),
            limit=10,
            with_payload=True
        )

        found_docs = results[0]
        print(f"   📊 Найдено {len(found_docs)} документов с этой страницы в индексе")

        for i, doc in enumerate(found_docs, 1):
            payload = doc.payload
            content = str(payload.get("content", ""))
            has_russian = any(ord(c) > 127 for c in content[:200])
            print(f"   {i}. {'✅' if has_russian else '❌'} {payload.get('title', 'Без названия')[:50]}...")
            print(f"      Содержимое: {content[:100]}...")

        # 7. Тестируем поиск
        print("\n7️⃣ Тестируем поиск...")
        from app.services.bge_embeddings import embed_unified
        from app.services.retrieval import hybrid_search
        from app.services.rerank import rerank

        test_query = "Какие каналы поддерживаются в чат-центре?"
        print(f"   🔍 Тестовый запрос: {test_query}")

        # Генерируем эмбеддинги
        embeddings = embed_unified(test_query, return_dense=True, return_sparse=True)

        # Поиск
        search_results = hybrid_search(
            query_dense=embeddings['dense_vecs'][0],
            query_sparse=embeddings['sparse_vecs'][0],
            k=10
        )

        # Реранкинг
        reranked = rerank(test_query, search_results, top_n=5)

        print(f"   📊 Найдено {len(search_results)} результатов")
        print(f"   📊 После реранкинга: {len(reranked)} результатов")

        # Проверяем, есть ли наша страница в результатах
        our_page_found = False
        for i, doc in enumerate(reranked, 1):
            doc_url = doc.get("payload", {}).get("url", "")
            if test_url in doc_url:
                our_page_found = True
                print(f"   ✅ Наша страница найдена на позиции {i}")
                break

        if not our_page_found:
            print(f"   ❌ Наша страница НЕ найдена в топ-5 результатов")

        # Итоговый отчет
        print("\n" + "="*60)
        print("📋 ИТОГОВЫЙ ОТЧЕТ")
        print("="*60)
        print(f"✅ HTML получен: {len(html)} символов")
        print(f"{'✅' if has_russian else '❌'} Русский текст извлечен: {len(main_text)} символов")
        print(f"✅ Чанков создано: {len(chunks)}")
        print(f"{'✅' if russian_chunks > 0 else '❌'} Русских чанков: {russian_chunks}")
        print(f"✅ Документов в индексе: {len(found_docs)}")
        print(f"{'✅' if our_page_found else '❌'} Страница найдена в поиске: {'ДА' if our_page_found else 'НЕТ'}")

        if has_russian and russian_chunks > 0 and our_page_found:
            print("\n🎉 ИНДЕКСАЦИЯ РАБОТАЕТ КОРРЕКТНО!")
        else:
            print("\n⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ С ИНДЕКСАЦИЕЙ!")

    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(test_single_page_indexing())
