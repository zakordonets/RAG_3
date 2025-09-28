#!/usr/bin/env python3
"""
Тест конкретного запроса, который ранее давал плохие результаты
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import hybrid_search
from app.services.bge_embeddings import embed_unified

def test_channel_query():
    """Тестируем запрос о каналах поддержки"""
    query = "Какие каналы поддерживаются в чат-центре"

    print(f"🔍 Тестируем запрос: '{query}'")
    print("=" * 60)

    try:
        # Получаем эмбеддинги для запроса
        embeddings = embed_unified(query, return_dense=True, return_sparse=True)
        dense_vec = embeddings['dense_vecs'][0]
        sparse_vec = embeddings['sparse_vecs'][0]

        # Выполняем гибридный поиск
        results = hybrid_search(
            query_dense=dense_vec,
            query_sparse=sparse_vec,
            k=5
        )

        print(f"📊 Найдено {len(results)} результатов:")
        print()

        for i, result in enumerate(results):
            score = result.get('rrf_score', 0)
            payload = result.get('payload', {})
            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            text = payload.get('text', '')
            indexed_via = payload.get('indexed_via', 'unknown')
            content_length = payload.get('content_length', 0)

            # Проверяем релевантность по ключевым словам
            keywords = ['канал', 'telegram', 'веб-виджет', 'мобильный', 'чат-центр']
            relevance_score = sum(1 for keyword in keywords if keyword.lower() in text.lower())

            print(f"  {i+1}. Score: {score:.4f} | Relevance: {relevance_score}/5")
            print(f"     Title: {title}")
            print(f"     URL: {url}")
            print(f"     indexed_via: {indexed_via}")
            print(f"     content_length: {content_length}")
            print(f"     Text preview: {text[:150]}...")
            print()

        # Проверим, есть ли документ "Что такое edna Chat Center"
        whatis_found = False
        for result in results:
            url = result.get('payload', {}).get('url', '')
            if 'whatis' in url:
                whatis_found = True
                print(f"✅ Найден документ 'Что такое edna Chat Center': позиция {results.index(result) + 1}")
                break

        if not whatis_found:
            print("❌ Документ 'Что такое edna Chat Center' не найден в топ-5")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")

if __name__ == "__main__":
    test_channel_query()
