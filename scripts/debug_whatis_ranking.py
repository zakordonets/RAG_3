#!/usr/bin/env python3
"""
Отладка ранжирования документа "Что такое edna Chat Center"
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import hybrid_search, client, COLLECTION
from app.services.bge_embeddings import embed_unified
from qdrant_client.models import Filter, FieldCondition, MatchValue

def debug_whatis_ranking():
    """Отладить ранжирование документа 'Что такое edna Chat Center'"""
    query = "Какие каналы поддерживаются в чат-центре"

    print(f"🔍 Отладка ранжирования для запроса: '{query}'")
    print("=" * 60)

    # 1. Проверим, есть ли документ в коллекции
    print("1. Проверяем наличие документа 'Что такое edna Chat Center'...")
    whatis_results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="url",
                    match=MatchValue(value="https://docs-chatcenter.edna.ru/docs/start/whatis")
                )
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False
    )

    if whatis_results[0]:
        whatis_doc = whatis_results[0][0]
        print(f"   ✅ Документ найден:")
        print(f"      ID: {whatis_doc.id}")
        print(f"      Title: {whatis_doc.payload.get('title', 'N/A')}")
        print(f"      URL: {whatis_doc.payload.get('url', 'N/A')}")
        print(f"      Content length: {whatis_doc.payload.get('content_length', 0)}")
        print(f"      Text preview: {whatis_doc.payload.get('text', '')[:200]}...")
        print()
    else:
        print("   ❌ Документ не найден в коллекции")
        return

    # 2. Выполним поиск и посмотрим на все результаты
    print("2. Выполняем поиск и анализируем результаты...")

    embeddings = embed_unified(query, return_dense=True, return_sparse=True)
    dense_vec = embeddings['dense_vecs'][0]
    sparse_vec = embeddings['sparse_vecs'][0]

    # Получаем больше результатов для анализа
    results = hybrid_search(
        query_dense=dense_vec,
        query_sparse=sparse_vec,
        k=20  # Получаем больше результатов
    )

    print(f"   📊 Получено {len(results)} результатов")
    print()

    # 3. Найдем позицию документа "Что такое edna Chat Center"
    whatis_position = None
    for i, result in enumerate(results):
        url = result.get('payload', {}).get('url', '')
        if 'whatis' in url:
            whatis_position = i + 1
            whatis_result = result
            break

    if whatis_position:
        print(f"3. Документ 'Что такое edna Chat Center' найден на позиции {whatis_position}")
        print(f"   Score: {whatis_result.get('rrf_score', 0):.6f}")
        print(f"   URL: {whatis_result.get('payload', {}).get('url', 'N/A')}")
        print()

        # 4. Проанализируем топ-10 результатов
        print("4. Анализ топ-10 результатов:")
        for i, result in enumerate(results[:10]):
            score = result.get('rrf_score', 0)
            payload = result.get('payload', {})
            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            content_length = payload.get('content_length', 0)

            # Проверим релевантность по ключевым словам
            text = payload.get('text', '').lower()
            keywords = ['канал', 'telegram', 'веб-виджет', 'мобильный', 'чат-центр', 'поддерживается']
            keyword_matches = sum(1 for keyword in keywords if keyword in text)

            is_whatis = 'whatis' in url
            marker = "🎯" if is_whatis else "  "

            print(f"   {marker} {i+1:2d}. Score: {score:.6f} | Keywords: {keyword_matches}/6 | Length: {content_length}")
            print(f"       Title: {title}")
            print(f"       URL: {url}")
            print()
    else:
        print("3. ❌ Документ 'Что такое edna Chat Center' не найден в топ-20 результатов")

        # Покажем топ-5 для сравнения
        print("\n   Топ-5 результатов:")
        for i, result in enumerate(results[:5]):
            score = result.get('rrf_score', 0)
            payload = result.get('payload', {})
            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            print(f"      {i+1}. Score: {score:.6f} | {title}")

    # 5. Проверим содержимое документа "Что такое edna Chat Center"
    if whatis_results[0]:
        print("5. Анализ содержимого документа 'Что такое edna Chat Center':")
        text = whatis_results[0][0].payload.get('text', '')

        # Проверим наличие ключевых слов
        keywords = ['канал', 'telegram', 'веб-виджет', 'мобильный', 'чат-центр', 'поддерживается']
        found_keywords = []
        for keyword in keywords:
            if keyword in text.lower():
                found_keywords.append(keyword)

        print(f"   Найденные ключевые слова: {found_keywords}")
        print(f"   Общее количество найденных: {len(found_keywords)}/{len(keywords)}")

        # Найдем предложения с ключевыми словами
        sentences = text.split('.')
        relevant_sentences = []
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in keywords):
                relevant_sentences.append(sentence.strip())

        if relevant_sentences:
            print(f"   Релевантные предложения:")
            for sentence in relevant_sentences[:3]:  # Показываем первые 3
                print(f"      • {sentence[:150]}...")
        else:
            print("   ❌ Релевантные предложения не найдены")

if __name__ == "__main__":
    debug_whatis_ranking()
