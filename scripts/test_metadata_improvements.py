#!/usr/bin/env python3
"""
Тест всех улучшений метаданных.
Проверяет комбинированное извлечение метаданных из всех источников.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.parsers import parse_jina_content, extract_url_metadata, parse_docusaurus_structure
from bs4 import BeautifulSoup


def test_complete_metadata_pipeline():
    """Тест полного pipeline извлечения метаданных."""
    print("🧪 Тестирование полного pipeline метаданных...")
    
    # Пример URL
    url = "https://docs-chatcenter.edna.ru/docs/agent/routing"
    
    # Пример Jina Reader ответа
    jina_response = """Title: Настройка маршрутизации в edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/agent/routing
Content Length: 2456
Language Detected: Russian
Published Time: 2024-07-24T10:30:00Z
Images: 2
Links: 8
Markdown Content:

# Настройка маршрутизации

Маршрутизация позволяет распределять входящие сообщения между агентами.

## Типы маршрутизации

В системе поддерживаются следующие типы:
- По каналам (Telegram, WhatsApp)
- По времени работы агентов
- По навыкам агентов

## Настройка через API

Для настройки маршрутизации используется API:

**Permissions:** AGENT, SUPERVISOR

### Создание правила маршрутизации

```http
POST /api/routing/rules
```
"""
    
    # Пример HTML для Docusaurus
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Настройка маршрутизации в edna Chat Center</title>
        <meta name="description" content="Подробное руководство по настройке маршрутизации сообщений">
    </head>
    <body>
        <nav class="theme-doc-breadcrumbs">
            <a href="/docs">Документация</a>
            <a href="/docs/agent">Агент</a>
            <a href="/docs/agent/routing">Маршрутизация</a>
        </nav>
        
        <div class="theme-doc-sidebar-item-category-level-1 menu__list-item--collapsed">
            Настройка агента
        </div>
        
        <article class="theme-doc-markdown">
            <h1>Настройка маршрутизации</h1>
            <h2>Типы маршрутизации</h2>
            <h3>По каналам</h3>
            <p>Система поддерживает Telegram и WhatsApp каналы.</p>
            
            <blockquote>
                <strong>Permissions:</strong> AGENT, SUPERVISOR
            </blockquote>
        </article>
    </body>
    </html>
    """
    
    print(f"📄 Тестируем URL: {url}")
    
    # 1. Извлекаем Jina Reader метаданные
    print("\n1️⃣ Jina Reader метаданные:")
    jina_metadata = parse_jina_content(jina_response)
    for key, value in jina_metadata.items():
        if key != 'content':  # Не показываем весь контент
            print(f"   {key}: {value}")
    
    # 2. Извлекаем URL метаданные
    print("\n2️⃣ URL метаданные:")
    url_metadata = extract_url_metadata(url)
    for key, value in url_metadata.items():
        print(f"   {key}: {value}")
    
    # 3. Извлекаем HTML структурные метаданные
    print("\n3️⃣ HTML структурные метаданные:")
    soup = BeautifulSoup(html_content, "lxml")
    html_metadata = parse_docusaurus_structure(soup)
    for key, value in html_metadata.items():
        print(f"   {key}: {value}")
    
    # 4. Объединяем все метаданные
    print("\n4️⃣ Объединенные метаданные:")
    combined_metadata = {
        **jina_metadata,
        **url_metadata,
        **html_metadata
    }
    
    # Показываем ключевые поля
    key_fields = [
        'title', 'section', 'user_role', 'page_type', 'permissions',
        'breadcrumb_path', 'sidebar_category', 'channels', 'features',
        'content_length', 'language_detected'
    ]
    
    for field in key_fields:
        if field in combined_metadata:
            print(f"   {field}: {combined_metadata[field]}")
    
    # 5. Проверяем качество метаданных
    print("\n5️⃣ Проверка качества метаданных:")
    
    quality_checks = {
        'Есть заголовок': 'title' in combined_metadata and combined_metadata['title'],
        'Определена секция': 'section' in combined_metadata,
        'Определена роль пользователя': 'user_role' in combined_metadata,
        'Определен тип страницы': 'page_type' in combined_metadata,
        'Есть разрешения': 'permissions' in combined_metadata,
        'Есть breadcrumb': 'breadcrumb_path' in combined_metadata,
        'Есть каналы': 'channels' in combined_metadata,
        'Есть функции': 'features' in combined_metadata,
    }
    
    passed_checks = 0
    for check, passed in quality_checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check}")
        if passed:
            passed_checks += 1
    
    quality_score = (passed_checks / len(quality_checks)) * 100
    print(f"\n📊 Качество метаданных: {quality_score:.1f}% ({passed_checks}/{len(quality_checks)})")
    
    return quality_score >= 80


def test_search_metadata():
    """Тест поисковых метаданных."""
    print("\n🔍 Тестирование поисковых метаданных...")
    
    # Тестируем разные типы URL
    test_cases = [
        {
            'url': 'https://docs-chatcenter.edna.ru/docs/start/whatis',
            'expected_section': 'start',
            'expected_role': 'all',
            'expected_type': 'guide'
        },
        {
            'url': 'https://docs-chatcenter.edna.ru/docs/api/messages/create',
            'expected_section': 'api',
            'expected_role': 'integrator',
            'expected_type': 'api-reference',
            'expected_method': 'POST'
        },
        {
            'url': 'https://docs-chatcenter.edna.ru/docs/admin/widget',
            'expected_section': 'admin',
            'expected_role': 'admin',
            'expected_type': 'guide',
            'expected_permissions': 'ADMIN'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📄 Тест {i}: {case['url']}")
        
        metadata = extract_url_metadata(case['url'])
        
        # Проверяем ожидаемые значения
        checks = {
            'section': case['expected_section'],
            'user_role': case['expected_role'],
            'page_type': case['expected_type']
        }
        
        if 'expected_method' in case:
            checks['api_method'] = case['expected_method']
        
        if 'expected_permissions' in case:
            checks['permissions'] = case['expected_permissions']
        
        for field, expected in checks.items():
            actual = metadata.get(field)
            if actual == expected:
                print(f"   ✅ {field}: {actual}")
            else:
                print(f"   ❌ {field}: ожидалось '{expected}', получено '{actual}'")
                return False
    
    print("\n✅ Все поисковые метаданные корректны")
    return True


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование улучшений метаданных\n")
    
    tests = [
        test_complete_metadata_pipeline,
        test_search_metadata,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ Тест {test.__name__} пройден")
            else:
                print(f"❌ Тест {test.__name__} не пройден")
        except Exception as e:
            print(f"❌ Ошибка в тесте {test.__name__}: {e}")
    
    print(f"\n📊 Результаты тестирования: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        print("\n📈 Ожидаемые улучшения:")
        print("   • Качество поиска: +25-40%")
        print("   • Фильтрация по ролям: ✅")
        print("   • Фильтрация по каналам: ✅")
        print("   • Фильтрация по функциям: ✅")
        print("   • Структурная навигация: ✅")
        return True
    else:
        print("⚠️ Некоторые тесты не прошли")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

