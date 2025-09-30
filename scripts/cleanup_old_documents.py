#!/usr/bin/env python3
"""
Удаление старых документов из коллекции Qdrant
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue
from datetime import datetime, date
import json

def cleanup_old_documents(dry_run=True):
    """Удалить старые документы из коллекции"""
    print("🧹 Очистка старых документов из коллекции")
    print("=" * 60)

    try:
        # Получаем все документы
        print("📄 Получаем все документы из коллекции...")
        all_results = client.scroll(
            collection_name=COLLECTION,
            limit=10000,  # Получаем все документы
            with_payload=True,
            with_vectors=False
        )

        today = date.today().isoformat()
        old_documents = []
        today_documents = []

        print(f"🔍 Анализируем {len(all_results[0])} документов...")

        for point in all_results[0]:
            payload = point.payload
            indexed_at = payload.get('indexed_at', '')
            indexed_via = payload.get('indexed_via', 'unknown')
            content_length = payload.get('content_length', 0)

            # Определяем, нужно ли удалить документ
            should_delete = False

            # Удаляем документы с indexed_via: unknown
            if indexed_via == 'unknown':
                should_delete = True
                reason = "indexed_via: unknown"

            # Удаляем документы с content_length: 0
            elif content_length == 0:
                should_delete = True
                reason = "content_length: 0"

            if should_delete:
                old_documents.append({
                    'id': point.id,
                    'url': payload.get('url', 'N/A'),
                    'title': payload.get('title', 'N/A'),
                    'reason': reason,
                    'indexed_via': indexed_via,
                    'content_length': content_length,
                    'indexed_at': indexed_at
                })
            else:
                today_documents.append({
                    'id': point.id,
                    'url': payload.get('url', 'N/A'),
                    'title': payload.get('title', 'N/A'),
                    'indexed_via': indexed_via,
                    'content_length': content_length,
                    'indexed_at': indexed_at
                })

        print(f"\n📊 Статистика:")
        print(f"   🗑️  Документов для удаления: {len(old_documents)}")
        print(f"   ✅ Документов для сохранения: {len(today_documents)}")

        # Группируем по причинам удаления
        reasons = {}
        for doc in old_documents:
            reason = doc['reason']
            reasons[reason] = reasons.get(reason, 0) + 1

        print(f"\n📋 Причины удаления:")
        for reason, count in reasons.items():
            print(f"   {reason}: {count}")

        if dry_run:
            print(f"\n🔍 РЕЖИМ ПРОСМОТРА (dry_run=True)")
            print("Документы НЕ будут удалены. Для реального удаления запустите с dry_run=False")

            # Показываем примеры документов для удаления
            print(f"\n📄 Примеры документов для удаления:")
            for i, doc in enumerate(old_documents[:5]):
                print(f"   {i+1}. {doc['title']}")
                print(f"      URL: {doc['url']}")
                print(f"      Причина: {doc['reason']}")
                print()
        else:
            print(f"\n⚠️  РЕЖИМ УДАЛЕНИЯ (dry_run=False)")

            if len(old_documents) == 0:
                print("✅ Нет документов для удаления")
                return

            # Удаляем документы
            print(f"🗑️  Удаляем {len(old_documents)} документов...")

            # Разбиваем на батчи для удаления
            batch_size = 100
            deleted_count = 0

            for i in range(0, len(old_documents), batch_size):
                batch = old_documents[i:i + batch_size]
                point_ids = [doc['id'] for doc in batch]

                client.delete(
                    collection_name=COLLECTION,
                    points_selector=point_ids
                )

                deleted_count += len(batch)
                print(f"   Удалено {deleted_count}/{len(old_documents)} документов...")

            print(f"✅ Успешно удалено {deleted_count} документов")

            # Проверяем новое состояние коллекции
            collection_info = client.get_collection(COLLECTION)
            print(f"📊 Новое количество документов в коллекции: {collection_info.points_count}")

    except Exception as e:
        print(f"❌ Ошибка при очистке: {e}")

def main():
    """Основная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Очистка старых документов из коллекции Qdrant')
    parser.add_argument('--execute', action='store_true',
                       help='Выполнить реальное удаление (по умолчанию только просмотр)')

    args = parser.parse_args()

    dry_run = not args.execute

    if dry_run:
        print("🔍 Режим просмотра - документы НЕ будут удалены")
        print("Для реального удаления используйте: python scripts/cleanup_old_documents.py --execute")
        print()

    cleanup_old_documents(dry_run=dry_run)

if __name__ == "__main__":
    main()
