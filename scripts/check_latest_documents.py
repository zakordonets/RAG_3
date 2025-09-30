#!/usr/bin/env python3
"""
Проверка последних добавленных документов в коллекции
"""
import sys
from pathlib import Path

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION


def check_latest_documents(limit: int = 20):
    """Проверяет последние добавленные документы"""
    try:
        # Получаем последние документы (сортировка по ID в обратном порядке)
        results = client.scroll(
            collection_name=COLLECTION,
            limit=limit,
            with_payload=True,
            offset=None  # Начинаем с конца
        )

        docs = results[0]
        print(f"🔍 Проверяем последние {len(docs)} документов:")
        print("="*60)

        for i, doc in enumerate(docs, 1):
            payload = doc.payload
            content = str(payload.get("content", ""))

            # Анализируем содержимое
            has_russian = any(ord(c) > 127 for c in content[:200]) if content else False
            is_empty = len(content.strip()) == 0

            print(f"\n📄 Документ {i} (ID: {doc.id}):")
            print(f"   URL: {payload.get('url', 'Без URL')}")
            print(f"   Заголовок: {payload.get('title', 'Без названия')}")
            print(f"   Тип: {payload.get('page_type', 'unknown')}")
            print(f"   Язык: {payload.get('language', 'unknown')}")
            print(f"   Источник: {payload.get('source', 'unknown')}")
            print(f"   Длина: {len(content)} символов")
            print(f"   {'✅' if has_russian else '❌'} Русский текст")
            print(f"   {'❌' if is_empty else '✅'} Не пустой")
            print(f"   Индексирован через: {payload.get('indexed_via', 'unknown')}")

            if content:
                preview = content[:200] + "..." if len(content) > 200 else content
                print(f"   Превью: {preview}")
            else:
                print(f"   Превью: [ПУСТОЙ КОНТЕНТ]")

        # Статистика
        total_docs = len(docs)
        empty_docs = sum(1 for doc in docs if len(str(doc.payload.get("content", "")).strip()) == 0)
        russian_docs = sum(1 for doc in docs if any(ord(c) > 127 for c in str(doc.payload.get("content", ""))[:200]))

        print(f"\n📊 Статистика последних {total_docs} документов:")
        print(f"   Пустых: {empty_docs} ({empty_docs/total_docs*100:.1f}%)")
        print(f"   С русским текстом: {russian_docs} ({russian_docs/total_docs*100:.1f}%)")

        # Проверяем методы индексации
        indexed_via = {}
        for doc in docs:
            method = doc.payload.get('indexed_via', 'unknown')
            indexed_via[method] = indexed_via.get(method, 0) + 1

        print(f"\n🔧 Методы индексации:")
        for method, count in indexed_via.items():
            print(f"   {method}: {count}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    check_latest_documents(20)
