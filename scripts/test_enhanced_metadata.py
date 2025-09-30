#!/usr/bin/env python3
"""
Тест улучшенных метаданных для системы индексации.
Проверяет извлечение метаданных из Jina Reader и URL паттернов.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.parsers_migration import parse_jina_content, extract_url_metadata


def test_jina_reader_metadata():
    """Тест извлечения метаданных из Jina Reader."""
    print("🧪 Тестирование извлечения метаданных из Jina Reader...")
    
    # Пример ответа от Jina Reader
    jina_response = """Title: Что такое edna Chat Center | edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Content Length: 2456
Language Detected: Russian
Published Time: 2024-07-24T10:30:00Z
Images: 3
Links: 12
Markdown Content:

# Что такое edna Chat Center

edna Chat Center — это система для организации работы с клиентами через различные каналы связи.

## Роли в edna Chat Center

В системе edna Chat Center есть три основные роли:
- **Агент** — сотрудник, который общается с клиентами
- **Супервизор** — руководитель агентов
- **Администратор** — настраивает систему

## Каналы в edna Chat Center

Система поддерживает следующие каналы:
- Telegram
- WhatsApp
- Viber
- Веб-виджет
- Мобильные приложения
"""
    
    # Парсим метаданные
    metadata = parse_jina_content(jina_response)
    
    print(f"✅ Извлеченные метаданные:")
    for key, value in metadata.items():
        print(f"   {key}: {value}")
    
    # Проверяем наличие ключевых полей
    expected_fields = ['title', 'content', 'url_source', 'content_length', 'language_detected']
    for field in expected_fields:
        if field not in metadata:
            print(f"❌ Отсутствует поле: {field}")
            return False
    
    print(f"✅ Все ожидаемые поля присутствуют")
    return True


def test_url_metadata_extraction():
    """Тест извлечения метаданных из URL паттернов."""
    print("\n🧪 Тестирование извлечения метаданных из URL...")
    
    test_urls = [
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/agent/routing",
        "https://docs-chatcenter.edna.ru/docs/supervisor/threadcontrol",
        "https://docs-chatcenter.edna.ru/docs/admin/widget",
        "https://docs-chatcenter.edna.ru/docs/api/messages/create",
        "https://docs-chatcenter.edna.ru/blog/release-6.16",
        "https://docs-chatcenter.edna.ru/faq",
    ]
    
    for url in test_urls:
        metadata = extract_url_metadata(url)
        print(f"\n📄 URL: {url}")
        print(f"   Метаданные: {metadata}")
        
        # Проверяем наличие ключевых полей
        if not metadata:
            print(f"   ❌ Не извлечены метаданные")
            continue
            
        if 'section' not in metadata:
            print(f"   ❌ Отсутствует поле 'section'")
            continue
            
        if 'user_role' not in metadata:
            print(f"   ❌ Отсутствует поле 'user_role'")
            continue
            
        print(f"   ✅ Метаданные извлечены корректно")
    
    return True


def test_combined_metadata():
    """Тест комбинированных метаданных."""
    print("\n🧪 Тестирование комбинированных метаданных...")
    
    # Пример Jina Reader ответа
    jina_response = """Title: Настройка маршрутизации в edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/agent/routing
Content Length: 1890
Language Detected: Russian
Markdown Content:

# Настройка маршрутизации

Маршрутизация позволяет распределять входящие сообщения между агентами.
"""
    
    # Парсим Jina Reader метаданные
    jina_metadata = parse_jina_content(jina_response)
    url = jina_metadata.get('url_source', '')
    
    # Извлекаем URL метаданные
    url_metadata = extract_url_metadata(url)
    
    # Объединяем метаданные
    combined_metadata = {**jina_metadata, **url_metadata}
    
    print(f"✅ Объединенные метаданные:")
    for key, value in combined_metadata.items():
        print(f"   {key}: {value}")
    
    # Проверяем наличие всех типов метаданных
    expected_sources = {
        'jina': ['title', 'content', 'url_source', 'content_length'],
        'url': ['section', 'user_role', 'page_type', 'permissions']
    }
    
    for source, fields in expected_sources.items():
        for field in fields:
            if field not in combined_metadata:
                print(f"❌ Отсутствует {source} поле: {field}")
                return False
    
    print(f"✅ Все типы метаданных присутствуют")
    return True


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование улучшенных метаданных\n")
    
    tests = [
        test_jina_reader_metadata,
        test_url_metadata_extraction,
        test_combined_metadata,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Ошибка в тесте {test.__name__}: {e}")
    
    print(f"\n📊 Результаты тестирования: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        return True
    else:
        print("⚠️ Некоторые тесты не прошли")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

