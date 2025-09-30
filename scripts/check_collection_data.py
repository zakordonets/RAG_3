#!/usr/bin/env python3
"""
Скрипт для проверки данных в коллекции
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import CONFIG
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

def check_collection():
    """Проверяем данные в коллекции"""
    client = QdrantClient(
        url=CONFIG.qdrant_url,
        api_key=CONFIG.qdrant_api_key,
        prefer_grpc=CONFIG.qdrant_grpc
    )
    
    try:
        # Получаем информацию о коллекции
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        print(f"Коллекция: {CONFIG.qdrant_collection}")
        print(f"Количество точек: {collection_info.points_count}")
        print(f"Векторы: {collection_info.config.params.vectors}")
        print(f"Sparse векторы: {collection_info.config.params.sparse_vectors}")
        
        # Получаем несколько точек
        print("\nПроверяем первые 3 точки...")
        points = client.scroll(
            collection_name=CONFIG.qdrant_collection,
            limit=3,
            with_payload=True,
            with_vectors=True
        )[0]
        
        for i, point in enumerate(points):
            print(f"\nТочка {i+1}:")
            print(f"  ID: {point.id}")
            print(f"  Payload ключи: {list(point.payload.keys()) if point.payload else 'Нет payload'}")
            
            if point.payload:
                title = point.payload.get('title', 'Нет названия')
                url = point.payload.get('url', 'Нет URL')
                content = point.payload.get('content', 'Нет контента')
                text = point.payload.get('text', 'Нет текста')
                
                print(f"  Title: {title[:50]}..." if title and title != 'Нет названия' else "  Title: Нет названия")
                print(f"  URL: {url}")
                print(f"  Content: {content[:100]}..." if content and content != 'Нет контента' else "  Content: Нет контента")
                print(f"  Text: {text[:100]}..." if text and text != 'Нет текста' else "  Text: Нет текста")
            
            if hasattr(point, 'vector') and point.vector:
                if isinstance(point.vector, dict):
                    print(f"  Векторы: {list(point.vector.keys())}")
                    if 'dense' in point.vector:
                        print(f"    Dense: {len(point.vector['dense'])} измерений")
                    if 'sparse' in point.vector:
                        sparse = point.vector['sparse']
                        print(f"    Sparse: {len(sparse.indices)} индексов")
                else:
                    print(f"  Вектор: {len(point.vector)} измерений")
        
        # Проверяем поиск напрямую
        print("\nТестируем поиск напрямую...")
        search_results = client.search(
            collection_name=CONFIG.qdrant_collection,
            query_vector=("dense", [0.1] * 1024),  # Фиктивный вектор
            with_payload=True,
            limit=2
        )
        
        print(f"Поиск вернул {len(search_results)} результатов")
        for i, result in enumerate(search_results):
            print(f"  Результат {i+1}: score={result.score:.3f}")
            if result.payload:
                print(f"    Title: {result.payload.get('title', 'Нет')}")
                print(f"    URL: {result.payload.get('url', 'Нет')}")
        
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_collection()
