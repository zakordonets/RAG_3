#!/usr/bin/env python3
"""
Полный список найденных документов по запросу
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import hybrid_search
from app.services.bge_embeddings import embed_unified

def get_full_search_results():
    """Получить полный список документов по запросу"""
    query = "Какие каналы поддерживаются в чат-центре"

    print(f"🔍 ПОЛНЫЙ СПИСОК ДОКУМЕНТОВ для запроса: '{query}'")
    print("=" * 80)

    try:
        # Получаем эмбеддинги для запроса
        embeddings = embed_unified(query, return_dense=True, return_sparse=True)
        dense_vec = embeddings['dense_vecs'][0]
        sparse_vec = embeddings['sparse_vecs'][0]

        # Выполняем поиск с большим лимитом
        results = hybrid_search(
            query_dense=dense_vec,
            query_sparse=sparse_vec,
            k=50  # Получаем больше результатов
        )

        print(f"📊 Найдено {len(results)} документов:")
        print()

        for i, result in enumerate(results, 1):
            score = result.get('rrf_score', 0)
            boosted_score = result.get('boosted_score', score)
            payload = result.get('payload', {})

            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            page_type = payload.get('page_type', 'N/A')
            source = payload.get('source', 'N/A')
            content_length = payload.get('content_length', 0)
            indexed_via = payload.get('indexed_via', 'unknown')

            # Анализ релевантности
            text = payload.get('text', '').lower()
            keywords = ['канал', 'telegram', 'whatsapp', 'viber', 'авито', 'веб-виджет', 'мобильный', 'поддерживается']
            keyword_matches = sum(1 for keyword in keywords if keyword in text)

            # Определяем тип документа
            doc_type = "📄 Обычный документ"
            if 'blog' in url or 'версия' in title.lower():
                doc_type = "📝 Release Notes"
            elif 'docs/start' in url or 'что такое' in title.lower():
                doc_type = "🏠 Главная документация"
            elif 'admin' in url or 'настройка' in title.lower():
                doc_type = "⚙️ Админ документация"
            elif 'api' in url:
                doc_type = "🔧 API документация"

            print(f"{i:2d}. {doc_type}")
            print(f"    📝 Название: {title}")
            print(f"    🔗 URL: {url}")
            print(f"    📊 RRF Score: {score:.6f}")
            print(f"    🚀 Boosted Score: {boosted_score:.6f}")
            print(f"    📏 Длина контента: {content_length}")
            print(f"    🏷️  Тип страницы: {page_type}")
            print(f"    📍 Источник: {source}")
            print(f"    🔄 Индексировано: {indexed_via}")
            print(f"    🎯 Ключевых слов: {keyword_matches}/8")

            # Показываем фрагмент текста
            text_preview = payload.get('text', '')[:200]
            print(f"    📄 Превью: {text_preview}...")

            # Анализ содержимого
            if keyword_matches >= 3:
                print(f"    ✅ ВЫСОКАЯ РЕЛЕВАНТНОСТЬ")
            elif keyword_matches >= 2:
                print(f"    ⚠️  СРЕДНЯЯ РЕЛЕВАНТНОСТЬ")
            else:
                print(f"    ❌ НИЗКАЯ РЕЛЕВАНТНОСТЬ")

            print()

        # Статистика по типам документов
        print("=" * 80)
        print("📊 СТАТИСТИКА ПО ТИПАМ ДОКУМЕНТОВ:")

        doc_types = {}
        high_relevance = 0
        medium_relevance = 0
        low_relevance = 0

        for result in results:
            payload = result.get('payload', {})
            url = payload.get('url', '')
            title = payload.get('title', '')
            text = payload.get('text', '').lower()

            # Определяем тип
            if 'blog' in url or 'версия' in title.lower():
                doc_type = "Release Notes"
            elif 'docs/start' in url or 'что такое' in title.lower():
                doc_type = "Главная документация"
            elif 'admin' in url:
                doc_type = "Админ документация"
            elif 'api' in url:
                doc_type = "API документация"
            else:
                doc_type = "Другое"

            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

            # Анализ релевантности
            keywords = ['канал', 'telegram', 'whatsapp', 'viber', 'авито', 'веб-виджет', 'мобильный', 'поддерживается']
            keyword_matches = sum(1 for keyword in keywords if keyword in text)

            if keyword_matches >= 3:
                high_relevance += 1
            elif keyword_matches >= 2:
                medium_relevance += 1
            else:
                low_relevance += 1

        print()
        for doc_type, count in doc_types.items():
            print(f"   {doc_type}: {count}")

        print()
        print("📈 РЕЛЕВАНТНОСТЬ:")
        print(f"   ✅ Высокая (3+ ключевых слов): {high_relevance}")
        print(f"   ⚠️  Средняя (2 ключевых слова): {medium_relevance}")
        print(f"   ❌ Низкая (0-1 ключевое слово): {low_relevance}")

        # Топ-5 самых релевантных
        print()
        print("🏆 ТОП-5 САМЫХ РЕЛЕВАНТНЫХ ДОКУМЕНТОВ:")
        relevant_results = []

        for result in results:
            payload = result.get('payload', {})
            text = payload.get('text', '').lower()
            keywords = ['канал', 'telegram', 'whatsapp', 'viber', 'авито', 'веб-виджет', 'мобильный', 'поддерживается']
            keyword_matches = sum(1 for keyword in keywords if keyword in text)

            if keyword_matches >= 2:  # Только документы с 2+ ключевыми словами
                relevant_results.append((result, keyword_matches))

        # Сортируем по количеству ключевых слов
        relevant_results.sort(key=lambda x: x[1], reverse=True)

        for i, (result, keyword_matches) in enumerate(relevant_results[:5], 1):
            payload = result.get('payload', {})
            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            score = result.get('rrf_score', 0)

            print(f"   {i}. {title}")
            print(f"      URL: {url}")
            print(f"      Score: {score:.6f}")
            print(f"      Ключевых слов: {keyword_matches}/8")
            print()

    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")

if __name__ == "__main__":
    get_full_search_results()
