#!/usr/bin/env python3
"""
Debug script to analyze search quality
"""
from app.services.bge_embeddings import embed_unified
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank

def debug_search():
    # Тестируем поиск по запросу
    query = 'Какие каналы поддерживаются в чат-центре?'
    print(f'🔍 Тестируем поиск для запроса: "{query}"')

    # Генерируем эмбеддинги
    embeddings = embed_unified(query, return_dense=True, return_sparse=True)
    print(f'📊 Dense embedding: {len(embeddings["dense_vecs"][0])} dims')
    print(f'📊 Sparse embedding: {len(embeddings["sparse_vecs"][0])} tokens')

    # Выполняем поиск
    results = hybrid_search(
        query_dense=embeddings['dense_vecs'][0],
        query_sparse=embeddings['sparse_vecs'][0],
        k=20
    )

    print(f'\n📋 Найдено {len(results)} результатов:')
    for i, result in enumerate(results[:10], 1):
        payload = result.get('payload', {})
        title = payload.get('title', 'Без названия')
        url = payload.get('url', 'Без URL')
        score = result.get('boosted_score', 0.0)
        print(f'{i:2d}. {title[:60]:<60} | {score:.4f}')
        print(f'    {url[:80]}')
        print()

    # Проверяем, есть ли релевантная статья
    relevant_found = False
    for result in results:
        url = result.get('payload', {}).get('url', '')
        if 'whatis' in url:
            relevant_found = True
            print(f'✅ Релевантная статья найдена: {url}')
            print(f'   Позиция: {results.index(result) + 1}')
            print(f'   Счет: {result.get("boosted_score", 0.0):.4f}')
            break

    if not relevant_found:
        print('❌ Релевантная статья НЕ найдена в топ-20')

    # Тестируем реранкинг
    print('\n🔄 Тестируем реранкинг...')
    reranked = rerank(query, results[:10], top_n=5)

    print(f'\n📋 После реранкинга (топ-5):')
    for i, result in enumerate(reranked, 1):
        payload = result.get('payload', {})
        title = payload.get('title', 'Без названия')
        url = payload.get('url', 'Без URL')
        score = result.get('score', 0.0)
        print(f'{i:2d}. {title[:60]:<60} | {score:.4f}')
        print(f'    {url[:80]}')
        print()

if __name__ == "__main__":
    debug_search()
