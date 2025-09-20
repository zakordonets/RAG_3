#!/usr/bin/env python3
"""
Скрипт для тестирования полного пайплайна от поиска до генерации ответа
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.orchestrator import handle_query
from app.config import CONFIG

def test_full_pipeline():
    """Тестируем полный пайплайн"""
    query = "Как добавить нового агента в чат-центр?"
    chat_id = "test123"
    channel = "test"
    
    print(f"Запрос: {query}")
    print(f"Chat ID: {chat_id}")
    print(f"Channel: {channel}")
    print("\n" + "="*50)
    
    # Вызываем полный пайплайн
    result = handle_query(
        channel=channel,
        chat_id=chat_id,
        message=query
    )
    
    print("\nРезультат пайплайна:")
    print(f"Ошибка: {result.get('error', 'Нет')}")
    print(f"Ответ: {result.get('answer', 'Нет ответа')}")
    print(f"Источники: {len(result.get('sources', []))}")
    
    if result.get('sources'):
        print("\nИсточники:")
        for i, source in enumerate(result.get('sources', [])[:3]):
            print(f"  {i+1}. {source.get('title', 'Без названия')}")
            print(f"     URL: {source.get('url', 'Нет URL')}")
    
    print(f"\nВремя обработки: {result.get('processing_time', 0):.2f}с")

if __name__ == "__main__":
    test_full_pipeline()
