#!/usr/bin/env python3
"""
Тестирует индексацию через Jina Reader для обхода блокировки ботов
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.crawler import crawl_with_sitemap_progress
from ingestion.processors.html_parser import HTMLParser
from ingestion.chunker import chunk_text_with_overlap
from ingestion.indexer import upsert_chunks
from bs4 import BeautifulSoup


async def test_jina_indexing():
    """Тестирует индексацию через Jina Reader"""

    # URL для тестирования
    test_url = "https://docs-chatcenter.edna.ru/docs/start/whatis"

    print(f"🧪 Тестируем индексацию через Jina Reader: {test_url}")

    try:
        # 1. Получаем HTML страницы через Jina Reader
        print("\n1️⃣ Получаем HTML через Jina Reader...")

        # Используем Jina Reader напрямую
        from ingestion.crawler import _jina_reader_fetch

        try:
            jina_text = _jina_reader_fetch(test_url, timeout=30)
            print(f"   ✅ Получено {len(jina_text)} символов через Jina Reader")
            print(f"   📝 Превью: {jina_text[:300]}...")

            # Проверяем наличие русского текста
            has_russian = any(ord(c) > 127 for c in jina_text[:500])
            print(f"   {'✅' if has_russian else '❌'} Русский текст: {'ДА' if has_russian else 'НЕТ'}")

            if not has_russian:
                print("   ⚠️ Jina Reader не смог получить русский контент")
                return

            # 2. Парсим контент
            print("\n2️⃣ Парсим контент...")
            html_parser = HTMLParser()
            processed = html_parser.parse(url, jina_text)
            main_text = processed.content

            # Если парсинг не сработал, используем весь текст
            if not main_text or len(main_text) < 100:
                main_text = jina_text
                print("   ⚠️ Используем весь текст от Jina Reader")

            print(f"   ✅ Извлечено {len(main_text)} символов текста")
            print(f"   📝 Превью: {main_text[:200]}...")

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
            title = "Что такое edna Chat Center"  # Известный заголовок
            page_type = "guide"

            # Создаем чанки для индексации
            chunks_to_index = []
            for i, chunk_text in enumerate(chunks):
                chunk_data = {
                    "text": chunk_text,
                    "payload": {
                        "url": test_url,
                        "page_type": page_type,
                        "source": "docs-site",
                        "language": "ru",
                        "title": title,
                        "text": chunk_text,
                        "chunk_index": i,
                        "indexed_via": "jina_reader"
                    }
                }
                chunks_to_index.append(chunk_data)

            print(f"   ✅ Подготовлено {len(chunks_to_index)} чанков для индексации")

            # 5. Индексируем
            if russian_chunks > 0:
                print("\n5️⃣ Индексируем чанки...")
                try:
                    indexed_count = upsert_chunks(chunks_to_index)
                    print(f"   ✅ Успешно проиндексировано {indexed_count} чанков")
                except Exception as e:
                    print(f"   ❌ Ошибка индексации: {e}")
            else:
                print("\n5️⃣ Пропускаем индексацию - нет русского текста")

            # 6. Проверяем результат
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
            print("📋 ИТОГОВЫЙ ОТЧЕТ JINA READER")
            print("="*60)
            print(f"✅ Jina Reader работает: {len(jina_text)} символов")
            print(f"{'✅' if has_russian else '❌'} Русский текст получен: {len(main_text)} символов")
            print(f"✅ Чанков создано: {len(chunks)}")
            print(f"{'✅' if russian_chunks > 0 else '❌'} Русских чанков: {russian_chunks}")
            print(f"✅ Документов в индексе: {len(found_docs)}")
            print(f"{'✅' if our_page_found else '❌'} Страница найдена в поиске: {'ДА' if our_page_found else 'НЕТ'}")

            if has_russian and russian_chunks > 0 and our_page_found:
                print("\n🎉 JINA READER РАБОТАЕТ! Можно использовать для переиндексации!")
            else:
                print("\n⚠️ JINA READER НЕ СМОГ ОБОЙТИ БЛОКИРОВКУ!")

        except Exception as e:
            print(f"   ❌ Ошибка Jina Reader: {e}")
            print("   💡 Попробуйте другие методы обхода блокировки")

    except Exception as e:
        print(f"❌ Общая ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(test_jina_indexing())
