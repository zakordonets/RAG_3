#!/usr/bin/env python3
"""
Проверка качества переиндексации с Jina Reader
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from qdrant_client.models import Filter, FieldCondition, MatchValue
import json

def check_collection_stats():
    """Проверить общую статистику коллекции"""
    print("🔍 Проверка статистики коллекции...")

    # Получить информацию о коллекции
    collection_info = client.get_collection(COLLECTION)
    print(f"📊 Общее количество документов: {collection_info.points_count}")

    # Проверить векторы
    vectors_config = collection_info.config.params.vectors
    if hasattr(vectors_config, 'size'):
        print(f"🔢 Размерность dense векторов: {vectors_config.size}")
    else:
        print(f"🔢 Конфигурация dense векторов: {vectors_config}")

    sparse_vectors = collection_info.config.params.sparse_vectors
    if sparse_vectors and 'sparse' in sparse_vectors:
        sparse_config = sparse_vectors['sparse']
        if hasattr(sparse_config, 'index') and hasattr(sparse_config.index, 'name'):
            print(f"📝 Название sparse векторов: {sparse_config.index.name}")
        else:
            print(f"📝 Конфигурация sparse векторов: {sparse_config}")
    else:
        print("📝 Sparse векторы не найдены")

    return collection_info.points_count

def check_recent_documents():
    """Проверить недавно добавленные документы"""
    print("\n🔍 Проверка недавно добавленных документов...")

    # Получить последние 10 документов
    results = client.scroll(
        collection_name=COLLECTION,
        limit=10,
        with_payload=True,
        with_vectors=False
    )

    print(f"📄 Проверяем {len(results[0])} последних документов:")

    good_docs = 0
    jina_docs = 0
    russian_docs = 0

    for i, point in enumerate(results[0]):
        payload = point.payload

        # Проверить метаданные
        indexed_via = payload.get('indexed_via', 'unknown')
        content_length = payload.get('content_length', 0)
        text = payload.get('text', '')

        # Проверить наличие русского текста
        has_russian = any('\u0400' <= char <= '\u04FF' for char in text)

        print(f"\n  Документ {i+1}:")
        print(f"    ID: {point.id}")
        print(f"    URL: {payload.get('url', 'N/A')}")
        print(f"    Title: {payload.get('title', 'N/A')}")
        print(f"    indexed_via: {indexed_via}")
        print(f"    content_length: {content_length}")
        print(f"    has_russian_text: {has_russian}")
        print(f"    text_preview: {text[:100]}...")

        if indexed_via == 'jina':
            jina_docs += 1
        if has_russian:
            russian_docs += 1
        if content_length > 0 and has_russian:
            good_docs += 1

    print(f"\n📊 Статистика последних документов:")
    print(f"   ✅ Документы с Jina Reader: {jina_docs}/{len(results[0])}")
    print(f"   🇷🇺 Документы с русским текстом: {russian_docs}/{len(results[0])}")
    print(f"   ✅ Качественные документы: {good_docs}/{len(results[0])}")

    return good_docs, len(results[0])

def check_specific_terms():
    """Проверить поиск по конкретным терминам"""
    print("\n🔍 Проверка поиска по ключевым терминам...")

    test_queries = [
        "каналы поддержки",
        "telegram",
        "чат-центр",
        "веб-виджет",
        "мобильные приложения"
    ]

    from app.services.retrieval import hybrid_search
    from app.services.bge_embeddings import embed_unified

    for query in test_queries:
        print(f"\n🔎 Поиск: '{query}'")

        try:
            # Получаем эмбеддинги для запроса
            embeddings = embed_unified(query, return_dense=True, return_sparse=True)
            dense_vec = embeddings['dense_vecs'][0]
            sparse_vec = embeddings['sparse_vecs'][0]

            # Выполняем гибридный поиск
            results = hybrid_search(
                query_dense=dense_vec,
                query_sparse=sparse_vec,
                k=3
            )

            if results:
                print(f"   Найдено {len(results)} результатов:")
                for i, result in enumerate(results):
                    score = result.get('rrf_score', 0)
                    payload = result.get('payload', {})
                    title = payload.get('title', 'N/A')
                    text = payload.get('text', '')
                    text_preview = text[:100] if text else ''
                    has_russian = any('\u0400' <= char <= '\u04FF' for char in text)

                    print(f"     {i+1}. Score: {score:.3f}")
                    print(f"        Title: {title}")
                    print(f"        Has Russian: {has_russian}")
                    print(f"        Text: {text_preview}...")
            else:
                print("   ❌ Результаты не найдены")

        except Exception as e:
            print(f"   ❌ Ошибка поиска: {e}")

def check_metadata_fields():
    """Проверить наличие всех необходимых метаданных"""
    print("\n🔍 Проверка метаданных...")

    # Получить несколько документов для анализа метаданных
    results = client.scroll(
        collection_name=COLLECTION,
        limit=5,
        with_payload=True,
        with_vectors=False
    )

    required_fields = [
        'url', 'title', 'text', 'source', 'language',
        'indexed_via', 'indexed_at', 'content_length'
    ]

    field_counts = {}

    for point in results[0]:
        payload = point.payload

        for field in required_fields:
            if field in payload:
                field_counts[field] = field_counts.get(field, 0) + 1

    print("📋 Наличие метаданных в проверенных документах:")
    for field in required_fields:
        count = field_counts.get(field, 0)
        total = len(results[0])
        status = "✅" if count == total else "⚠️" if count > 0 else "❌"
        print(f"   {status} {field}: {count}/{total}")

def main():
    """Основная функция проверки"""
    print("🚀 Проверка качества переиндексации с Jina Reader")
    print("=" * 60)

    try:
        # 1. Общая статистика
        total_docs = check_collection_stats()

        # 2. Проверка недавних документов
        good_docs, checked_docs = check_recent_documents()

        # 3. Проверка поиска
        check_specific_terms()

        # 4. Проверка метаданных
        check_metadata_fields()

        # Итоговая оценка
        print("\n" + "=" * 60)
        print("📊 ИТОГОВАЯ ОЦЕНКА:")
        print(f"   📄 Всего документов в коллекции: {total_docs}")
        print(f"   ✅ Качественных из проверенных: {good_docs}/{checked_docs}")

        if good_docs == checked_docs and good_docs > 0:
            print("   🎉 ПЕРЕИНДЕКСАЦИЯ УСПЕШНА! Все проверенные документы содержат русский текст и правильные метаданные.")
        elif good_docs > checked_docs * 0.8:
            print("   ✅ Переиндексация в основном успешна. Большинство документов в хорошем состоянии.")
        else:
            print("   ⚠️  Обнаружены проблемы с переиндексацией. Требуется дополнительная проверка.")

    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        return False

    return True

if __name__ == "__main__":
    main()
