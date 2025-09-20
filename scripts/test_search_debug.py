#!/usr/bin/env python3
"""
Скрипт для отладки поиска
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.retrieval import hybrid_search
from app.services.bge_embeddings import embed_unified
from app.config import CONFIG

def test_search():
    """Тестируем поиск напрямую"""
    query = "Как добавить нового агента в чат-центр?"
    print(f"Запрос: {query}")
    print(f"Используем backend: {CONFIG.embeddings_backend}")
    print(f"Используем sparse: {CONFIG.use_sparse}")
    
    # Генерируем эмбеддинги
    print("\n1. Генерируем эмбеддинги...")
    result = embed_unified(query)
    dense_vec_raw = result['dense_vecs']
    sparse_vec_raw = result.get('sparse_vecs', {})
    
    # Обрабатываем dense векторы - извлекаем первый элемент если это список списков
    if isinstance(dense_vec_raw, list) and len(dense_vec_raw) == 1:
        dense_vec = dense_vec_raw[0]  # Извлекаем первый элемент
    else:
        dense_vec = dense_vec_raw
    
    # Обрабатываем sparse векторы - они могут быть в виде списка
    if isinstance(sparse_vec_raw, list) and sparse_vec_raw:
        sparse_vec = sparse_vec_raw[0]  # Берем первый элемент списка
    else:
        sparse_vec = sparse_vec_raw
    
    print(f"Dense векторы: {len(dense_vec) if dense_vec is not None else 0} измерений")
    print(f"Sparse векторы: {len(sparse_vec) if sparse_vec and isinstance(sparse_vec, dict) else 0} индексов")
    
    if sparse_vec and isinstance(sparse_vec, dict):
        print(f"Пример sparse индексов: {list(sparse_vec.keys())[:5]}")
        print(f"Пример sparse значений: {list(sparse_vec.values())[:5]}")
    else:
        print(f"Sparse векторы структура: {type(sparse_vec)}")
        print(f"Sparse векторы содержимое: {sparse_vec}")
    
    # Выполняем поиск
    print("\n2. Выполняем поиск...")
    search_results = hybrid_search(
        query_dense=dense_vec if dense_vec is not None else None,
        query_sparse=sparse_vec if sparse_vec else None,
        k=5
    )
    
    print(f"Найдено результатов: {len(search_results)}")
    
    if not search_results:
        print("❌ Поиск не вернул результатов!")
        return
    
    print("\n3. Результаты поиска:")
    for i, result in enumerate(search_results[:3]):
        title = result.get("title", "Без названия")
        url = result.get("url", "Нет URL")
        score = result.get("score", 0)
        content = result.get("content", "")[:100] + "..." if result.get("content") else "Нет контента"
        
        print(f"\n{i+1}. {title[:50]}...")
        print(f"   URL: {url}")
        print(f"   Score: {score:.3f}")
        print(f"   Content: {content}")
    
    # Проверяем, есть ли контент в результатах
    has_content = any(result.get("content") for result in search_results)
    print(f"\n4. Анализ:")
    print(f"   Результаты содержат контент: {has_content}")
    print(f"   Количество результатов с контентом: {sum(1 for r in search_results if r.get('content'))}")

if __name__ == "__main__":
    test_search()
