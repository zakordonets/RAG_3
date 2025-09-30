#!/usr/bin/env python3
"""
Проверка метаданных, которые сохраняются в коллекции
"""
import sys
from pathlib import Path

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION


def check_metadata():
    """Проверяет метаданные в коллекции"""
    try:
        # Получаем несколько документов
        results = client.scroll(
            collection_name=COLLECTION,
            limit=5,
            with_payload=True
        )

        docs = results[0]
        print(f"🔍 Проверяем метаданные в {len(docs)} документах:")
        print("="*60)

        for i, doc in enumerate(docs, 1):
            payload = doc.payload
            print(f"\n📄 Документ {i} (ID: {doc.id}):")
            print(f"   URL: {payload.get('url', 'НЕТ')}")
            print(f"   Заголовок: {payload.get('title', 'НЕТ')}")
            print(f"   Тип страницы: {payload.get('page_type', 'НЕТ')}")
            print(f"   Источник: {payload.get('source', 'НЕТ')}")
            print(f"   Язык: {payload.get('language', 'НЕТ')}")
            print(f"   Хэш: {payload.get('hash', 'НЕТ')}")
            print(f"   Метод индексации: {payload.get('indexed_via', 'НЕТ')}")
            print(f"   Дата индексации: {payload.get('indexed_at', 'НЕТ')}")
            print(f"   Версия парсера: {payload.get('parser_version', 'НЕТ')}")
            print(f"   Длина контента: {len(payload.get('text', ''))}")

            # Показываем все ключи
            all_keys = list(payload.keys())
            print(f"   Все ключи: {all_keys}")

        # Статистика по метаданным
        print(f"\n📊 Статистика метаданных:")

        # Собираем все уникальные значения для каждого поля
        metadata_stats = {}
        for doc in docs:
            for key, value in doc.payload.items():
                if key not in metadata_stats:
                    metadata_stats[key] = set()
                metadata_stats[key].add(str(value))

        for key, values in metadata_stats.items():
            print(f"   {key}: {len(values)} уникальных значений")
            if len(values) <= 5:  # Показываем значения, если их немного
                print(f"      {list(values)}")
            else:
                print(f"      {list(values)[:3]}... (и еще {len(values)-3})")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    check_metadata()
