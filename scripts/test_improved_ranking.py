#!/usr/bin/env python3
"""
Тест улучшенного ранжирования
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import hybrid_search
from app.services.bge_embeddings import embed_unified

def test_improved_ranking():
    """Тест улучшенного ранжирования"""
    query = "Какие каналы поддерживаются в чат-центре"

    print(f"🔍 ТЕСТ УЛУЧШЕННОГО РАНЖИРОВАНИЯ для запроса: '{query}'")
    print("=" * 80)

    try:
        # Получаем эмбеддинги для запроса
        embeddings = embed_unified(query, return_dense=True, return_sparse=True)
        dense_vec = embeddings['dense_vecs'][0]
        sparse_vec = embeddings['sparse_vecs'][0]

        # Выполняем поиск с улучшенным ранжированием
        results = hybrid_search(
            query_dense=dense_vec,
            query_sparse=sparse_vec,
            k=10  # Топ-10 для анализа
        )

        print(f"📊 Топ-10 документов после улучшенного ранжирования:")
        print()

        for i, result in enumerate(results, 1):
            rrf_score = result.get('rrf_score', 0)
            boosted_score = result.get('boosted_score', rrf_score)
            payload = result.get('payload', {})

            title = payload.get('title', 'N/A')
            url = payload.get('url', 'N/A')
            text = payload.get('text', '').lower()

            # Анализ релевантности
            keywords = ['канал', 'telegram', 'whatsapp', 'viber', 'авито', 'веб-виджет', 'мобильный', 'поддерживается']
            keyword_matches = sum(1 for keyword in keywords if keyword in text)

            # Определяем тип документа
            if 'blog' in url or 'версия' in title.lower():
                doc_type = "📝 Release Notes"
            elif 'docs/start' in url or 'что такое' in title.lower():
                doc_type = "🏠 Главная документация"
            elif 'admin' in url:
                doc_type = "⚙️ Админ документация"
            elif 'api' in url:
                doc_type = "🔧 API документация"
            else:
                doc_type = "📄 Обычный документ"

            # Коэффициент бустинга
            boost_factor = boosted_score / rrf_score if rrf_score > 0 else 1.0

            print(f"{i:2d}. {doc_type}")
            print(f"    📝 Название: {title}")
            print(f"    🔗 URL: {url}")
            print(f"    📊 RRF Score: {rrf_score:.6f}")
            print(f"    🚀 Boosted Score: {boosted_score:.6f}")
            print(f"    ⚡ Boost Factor: {boost_factor:.2f}x")
            print(f"    🎯 Ключевых слов: {keyword_matches}/8")

            # Показываем фрагмент текста
            text_preview = payload.get('text', '')[:150]
            print(f"    📄 Превью: {text_preview}...")

            # Анализ содержимого
            if keyword_matches >= 3:
                print(f"    ✅ ВЫСОКАЯ РЕЛЕВАНТНОСТЬ")
            elif keyword_matches >= 2:
                print(f"    ⚠️  СРЕДНЯЯ РЕЛЕВАНТНОСТЬ")
            else:
                print(f"    ❌ НИЗКАЯ РЕЛЕВАНТНОСТЬ")

            print()

        # Анализ изменений
        print("=" * 80)
        print("📈 АНАЛИЗ УЛУЧШЕНИЙ:")

        # Найдем "Что такое edna Chat Center"
        whatis_doc = None
        for result in results:
            if "docs/start/whatis" in result.get('payload', {}).get('url', ''):
                whatis_doc = result
                break

        if whatis_doc:
            position = next(i for i, r in enumerate(results, 1) if r == whatis_doc)
            print(f"   🏠 'Что такое edna Chat Center': позиция {position}")

            # Проверим, есть ли release notes в топе
            release_notes_count = sum(1 for r in results[:5] if 'blog' in r.get('payload', {}).get('url', ''))
            print(f"   📝 Release Notes в топ-5: {release_notes_count}")

            # Проверим релевантность топ-5
            high_relevance_count = 0
            for r in results[:5]:
                text = r.get('payload', {}).get('text', '').lower()
                keywords = ['канал', 'telegram', 'whatsapp', 'viber', 'авито', 'веб-виджет', 'мобильный', 'поддерживается']
                keyword_matches = sum(1 for keyword in keywords if keyword in text)
                if keyword_matches >= 2:
                    high_relevance_count += 1

            print(f"   🎯 Высокорелевантных в топ-5: {high_relevance_count}")

            if position <= 2:
                print("   ✅ УСПЕХ: Главная документация в топ-2!")
            else:
                print("   ⚠️  Главная документация не в топ-2")

            if release_notes_count == 0:
                print("   ✅ УСПЕХ: Release Notes исключены из топ-5!")
            else:
                print("   ⚠️  Release Notes все еще в топ-5")

            if high_relevance_count >= 3:
                print("   ✅ УСПЕХ: Большинство топ-5 документов релевантны!")
            else:
                print("   ⚠️  Мало релевантных документов в топ-5")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")

if __name__ == "__main__":
    test_improved_ranking()
