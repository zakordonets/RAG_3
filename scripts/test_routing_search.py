#!/usr/bin/env python3
"""
Скрипт для тестирования поиска по маршрутизации
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.retrieval import hybrid_search
from app.services.bge_embeddings import embed_unified

def test_routing_search():
    """Тестируем поиск по маршрутизации"""
    query = "Как настроить маршрутизацию в чат-центре?"
    print(f"Запрос: {query}")
    
    # Генерируем эмбеддинги
    result = embed_unified(query)
    dense_vec_raw = result['dense_vecs']
    sparse_vec_raw = result.get('sparse_vecs', {})
    
    # Обрабатываем dense векторы - извлекаем первый элемент если это список списков
    if isinstance(dense_vec_raw, list) and len(dense_vec_raw) == 1:
        dense_vec = dense_vec_raw[0]  # Извлекаем первый элемент
    else:
        dense_vec = dense_vec_raw
    
    # Обрабатываем sparse векторы
    if isinstance(sparse_vec_raw, list) and sparse_vec_raw:
        sparse_vec = sparse_vec_raw[0]
    else:
        sparse_vec = sparse_vec_raw
    
    print(f"Dense векторы: {len(dense_vec)} измерений")
    print(f"Sparse векторы: {len(sparse_vec)} индексов")
    
    # Выполняем поиск
    search_results = hybrid_search(
        query_dense=dense_vec if dense_vec is not None else None,
        query_sparse=sparse_vec if sparse_vec else None,
        k=10
    )
    
    print(f"\nНайдено результатов: {len(search_results)}")
    
    if not search_results:
        print("❌ Поиск не вернул результатов!")
        return
    
    print("\nТоп-5 результатов:")
    for i, result in enumerate(search_results[:5]):
        payload = result.get("payload", {})
        title = payload.get("title", "Без названия")
        url = payload.get("url", "Нет URL")
        text = payload.get("text", "")[:200] + "..." if payload.get("text") else "Нет текста"
        score = result.get("score", 0)
        
        print(f"\n{i+1}. {title}")
        print(f"   URL: {url}")
        print(f"   Score: {score:.3f}")
        print(f"   Text: {text}")
        
        # Проверяем, содержит ли текст ключевые слова
        text_lower = text.lower()
        routing_keywords = ["маршрут", "routing", "направл", "переадрес", "передача"]
        has_routing = any(keyword in text_lower for keyword in routing_keywords)
        print(f"   Содержит маршрутизацию: {'✅' if has_routing else '❌'}")

if __name__ == "__main__":
    test_routing_search()
