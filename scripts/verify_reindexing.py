#!/usr/bin/env python3
"""
Проверяет качество переиндексации
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from app.services.bge_embeddings import embed_unified
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from qdrant_client.models import Filter


async def verify_reindexing():
    """Проверяет качество переиндексации"""

    print("🔍 ПРОВЕРКА КАЧЕСТВА ПЕРЕИНДЕКСАЦИИ")
    print("="*50)

    try:
        # 1. Базовая статистика
        print("\n1️⃣ Базовая статистика:")
        info = client.get_collection(COLLECTION)
        total_docs = info.points_count
        print(f"   📊 Всего документов: {total_docs}")

        # 2. Проверка русского контента
        print("\n2️⃣ Проверка русского контента:")
        results = client.scroll(
            collection_name=COLLECTION,
            limit=100,
            with_payload=True
        )

        docs = results[0]
        russian_docs = 0
        empty_docs = 0
        total_content_length = 0

        for doc in docs:
            content = str(doc.payload.get("content", ""))
            if content:
                total_content_length += len(content)
                if any(ord(c) > 127 for c in content[:200]):
                    russian_docs += 1
            else:
                empty_docs += 1

        russian_pct = (russian_docs / len(docs) * 100) if docs else 0
        avg_length = total_content_length / len(docs) if docs else 0

        print(f"   🇷🇺 Русских документов: {russian_docs} ({russian_pct:.1f}%)")
        print(f"   📄 Пустых документов: {empty_docs}")
        print(f"   📏 Средняя длина: {avg_length:.0f} символов")

        # 3. Проверка ключевых терминов
        print("\n3️⃣ Проверка ключевых терминов:")
        key_terms = ["канал", "telegram", "виджет", "чат-центр", "edna"]

        for term in key_terms:
            try:
                filter_result = client.scroll(
                    collection_name=COLLECTION,
                    scroll_filter=Filter(
                        must=[
                            {'key': 'content', 'match': {'text': term}}
                        ]
                    ),
                    limit=1,
                    with_payload=True
                )
                found = len(filter_result[0]) > 0
                print(f"   {'✅' if found else '❌'} '{term}': {'найден' if found else 'НЕ найден'}")
            except Exception as e:
                print(f"   ❌ '{term}': ошибка - {e}")

        # 4. Тестирование поиска
        print("\n4️⃣ Тестирование поиска:")
        test_queries = [
            "Какие каналы поддерживаются в чат-центре?",
            "Как настроить Telegram бота?",
            "Что такое веб-виджет?",
            "Как работает edna Chat Center?",
            "Настройка маршрутизации"
        ]

        for query in test_queries:
            try:
                # Генерируем эмбеддинги
                embeddings = embed_unified(query, return_dense=True, return_sparse=True)

                # Выполняем поиск
                search_results = hybrid_search(
                    query_dense=embeddings['dense_vecs'][0],
                    query_sparse=embeddings['sparse_vecs'][0],
                    k=10
                )

                # Реранкинг
                reranked = rerank(query, search_results, top_n=5)

                # Оцениваем качество
                quality_score = min(1.0, len(reranked) / 5.0)
                print(f"   {quality_score:.2f} {query}")

                # Показываем топ-3 результата
                for i, doc in enumerate(reranked[:3], 1):
                    title = doc.get("payload", {}).get("title", "Без названия")
                    url = doc.get("payload", {}).get("url", "Без URL")
                    print(f"      {i}. {title[:50]}...")

            except Exception as e:
                print(f"   ❌ {query}: ошибка - {e}")

        # 5. Итоговая оценка
        print("\n5️⃣ Итоговая оценка:")

        if russian_pct >= 80 and avg_length > 100:
            print("   ✅ КАЧЕСТВО: ОТЛИЧНО!")
            print("   🎉 Переиндексация прошла успешно!")
        elif russian_pct >= 50 and avg_length > 50:
            print("   ⚠️ КАЧЕСТВО: ХОРОШО")
            print("   💡 Рекомендуется дополнительная проверка")
        else:
            print("   ❌ КАЧЕСТВО: ПЛОХО")
            print("   🚨 Требуется повторная переиндексация")

        # 6. Рекомендации
        print("\n6️⃣ Рекомендации:")

        if russian_pct < 50:
            print("   🔄 Запустите повторную переиндексацию")
        if avg_length < 100:
            print("   📝 Проверьте настройки чанкинга")
        if empty_docs > 0:
            print("   🗑️ Очистите пустые документы")

        print("\n" + "="*50)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА!")
        print("="*50)

    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")


if __name__ == "__main__":
    asyncio.run(verify_reindexing())
