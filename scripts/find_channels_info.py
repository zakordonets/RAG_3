#!/usr/bin/env python3
"""
Поиск документов с информацией о каналах связи
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from app.services.retrieval import hybrid_search
from app.services.bge_embeddings import embed_unified

def find_channels_info():
    """Найти документы с информацией о каналах связи"""
    print("🔍 Поиск документов с информацией о каналах связи")
    print("=" * 70)

    # Запросы для поиска информации о каналах
    queries = [
        "Какие каналы поддерживаются в чат-центре",
        "Telegram канал подключение",
        "WhatsApp интеграция",
        "Viber канал",
        "Авито канал",
        "поддерживаемые каналы связи",
        "каналы подключения к чат-центру",
        "веб-виджет мобильное приложение каналы"
    ]

    found_documents = {}

    for query in queries:
        print(f"\n🔎 Поиск по запросу: '{query}'")

        try:
            # Получаем эмбеддинги для запроса
            embeddings = embed_unified(query, return_dense=True, return_sparse=True)
            dense_vec = embeddings['dense_vecs'][0]
            sparse_vec = embeddings['sparse_vecs'][0]

            # Выполняем гибридный поиск
            results = hybrid_search(
                query_dense=dense_vec,
                query_sparse=sparse_vec,
                k=10  # Получаем больше результатов
            )

            print(f"   📊 Найдено {len(results)} результатов:")

            for i, result in enumerate(results[:5]):  # Показываем топ-5
                score = result.get('rrf_score', 0)
                payload = result.get('payload', {})
                title = payload.get('title', 'N/A')
                url = payload.get('url', 'N/A')
                text = payload.get('text', '')
                content_length = payload.get('content_length', 0)

                # Проверяем релевантность по ключевым словам
                keywords = ['канал', 'telegram', 'whatsapp', 'viber', 'авито', 'веб-виджет', 'мобильный']
                keyword_matches = sum(1 for keyword in keywords if keyword in text.lower())

                print(f"      {i+1}. Score: {score:.4f} | Keywords: {keyword_matches}/7 | Length: {content_length}")
                print(f"         Title: {title}")
                print(f"         URL: {url}")

                # Сохраняем документ для дальнейшего анализа
                doc_key = f"{title}|{url}"
                if doc_key not in found_documents:
                    found_documents[doc_key] = {
                        'title': title,
                        'url': url,
                        'text': text,
                        'content_length': content_length,
                        'keyword_matches': keyword_matches,
                        'scores': []
                    }
                found_documents[doc_key]['scores'].append(score)

                # Показываем релевантные фрагменты текста
                if keyword_matches > 0:
                    sentences = text.split('.')
                    relevant_sentences = []
                    for sentence in sentences:
                        if any(keyword in sentence.lower() for keyword in keywords):
                            relevant_sentences.append(sentence.strip())

                    if relevant_sentences:
                        print(f"         Релевантные фрагменты:")
                        for sentence in relevant_sentences[:2]:
                            print(f"            • {sentence[:100]}...")
                print()

        except Exception as e:
            print(f"   ❌ Ошибка поиска: {e}")

    # Анализ найденных документов
    print("\n" + "=" * 70)
    print("📊 АНАЛИЗ НАЙДЕННЫХ ДОКУМЕНТОВ:")
    print()

    # Сортируем документы по количеству совпадений ключевых слов
    sorted_docs = sorted(found_documents.items(),
                        key=lambda x: x[1]['keyword_matches'],
                        reverse=True)

    print("🏆 Топ документов с информацией о каналах:")
    for i, (doc_key, doc_info) in enumerate(sorted_docs[:10]):
        avg_score = sum(doc_info['scores']) / len(doc_info['scores'])
        print(f"   {i+1}. {doc_info['title']}")
        print(f"      URL: {doc_info['url']}")
        print(f"      Ключевых слов: {doc_info['keyword_matches']}/7")
        print(f"      Средний score: {avg_score:.4f}")
        print(f"      Длина контента: {doc_info['content_length']}")
        print()

    # Проверим, есть ли документы с полной информацией о каналах
    print("🔍 Поиск документов с полной информацией о каналах...")

    all_results = client.scroll(
        collection_name=COLLECTION,
        limit=1000,
        with_payload=True,
        with_vectors=False
    )

    comprehensive_docs = []
    for point in all_results[0]:
        text = point.payload.get('text', '').lower()

        # Ищем документы, содержащие много каналов
        channels_found = []
        if 'telegram' in text:
            channels_found.append('telegram')
        if 'whatsapp' in text:
            channels_found.append('whatsapp')
        if 'viber' in text:
            channels_found.append('viber')
        if 'авито' in text or 'avito' in text:
            channels_found.append('авито')
        if 'веб-виджет' in text:
            channels_found.append('веб-виджет')
        if 'мобильный' in text:
            channels_found.append('мобильный')

        if len(channels_found) >= 2:  # Документы с 2+ каналами
            comprehensive_docs.append({
                'title': point.payload.get('title', 'N/A'),
                'url': point.payload.get('url', 'N/A'),
                'channels': channels_found,
                'content_length': point.payload.get('content_length', 0)
            })

    if comprehensive_docs:
        print(f"\n📋 Документы с информацией о нескольких каналах ({len(comprehensive_docs)} найдено):")
        for doc in comprehensive_docs[:5]:
            print(f"   • {doc['title']}")
            print(f"     URL: {doc['url']}")
            print(f"     Каналы: {', '.join(doc['channels'])}")
            print(f"     Длина: {doc['content_length']}")
            print()
    else:
        print(f"\n❌ Документы с полной информацией о каналах не найдены")

if __name__ == "__main__":
    find_channels_info()
