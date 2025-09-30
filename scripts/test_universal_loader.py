#!/usr/bin/env python3
"""
Тест универсального загрузчика.
Проверяет автоматическое определение типа контента и парсинг.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from ingestion.universal_loader import UniversalLoader, load_content_universal


def test_content_type_detection():
    """Тест определения типа контента."""
    print("🧪 Тестирование определения типа контента...")
    
    loader = UniversalLoader()
    
    # Тестовые случаи
    test_cases = [
        {
            'name': 'Jina Reader контент',
            'content': """Title: Тестовая страница
URL Source: https://example.com
Markdown Content:

# Заголовок

Содержимое страницы.
""",
            'expected_type': 'jina_reader'
        },
        {
            'name': 'HTML Docusaurus',
            'content': """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<nav class="theme-doc-breadcrumbs">
<article class="theme-doc-markdown">
<div class="theme-doc-sidebar">
</body>
</html>""",
            'expected_type': 'html_docusaurus'
        },
        {
            'name': 'Обычный HTML',
            'content': """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Заголовок</h1></body>
</html>""",
            'expected_type': 'html_generic'
        },
        {
            'name': 'Markdown',
            'content': """# Заголовок

**Жирный текст**

*Курсив*

## Подзаголовок

Обычный текст.
""",
            'expected_type': 'markdown'
        },
        {
            'name': 'Обычный текст',
            'content': """Это обычный текст без специальной разметки.""",
            'expected_type': 'text'
        }
    ]
    
    passed = 0
    for case in test_cases:
        detected_type = loader.detect_content_type(case['content'])
        if detected_type == case['expected_type']:
            print(f"   ✅ {case['name']}: {detected_type}")
            passed += 1
        else:
            print(f"   ❌ {case['name']}: ожидалось {case['expected_type']}, получено {detected_type}")
    
    print(f"📊 Результат: {passed}/{len(test_cases)} тестов пройдено")
    return passed == len(test_cases)


def test_page_type_detection():
    """Тест определения типа страницы."""
    print("\n🧪 Тестирование определения типа страницы...")
    
    loader = UniversalLoader()
    
    test_cases = [
        ('https://docs-chatcenter.edna.ru/docs/start/whatis', 'guide'),
        ('https://docs-chatcenter.edna.ru/docs/api/messages', 'api'),
        ('https://docs-chatcenter.edna.ru/faq', 'faq'),
        ('https://docs-chatcenter.edna.ru/blog/release-6.16', 'changelog'),
        ('https://docs-chatcenter.edna.ru/docs/admin/widget', 'admin'),
        ('https://docs-chatcenter.edna.ru/docs/supervisor/threadcontrol', 'supervisor'),
        ('https://docs-chatcenter.edna.ru/docs/agent/routing', 'agent'),
    ]
    
    passed = 0
    for url, expected_type in test_cases:
        detected_type = loader.detect_page_type(url)
        if detected_type == expected_type:
            print(f"   ✅ {url}: {detected_type}")
            passed += 1
        else:
            print(f"   ❌ {url}: ожидалось {expected_type}, получено {detected_type}")
    
    print(f"📊 Результат: {passed}/{len(test_cases)} тестов пройдено")
    return passed == len(test_cases)


def test_universal_loading():
    """Тест универсальной загрузки контента."""
    print("\n🧪 Тестирование универсальной загрузки...")
    
    # Тестовые данные
    test_cases = [
        {
            'name': 'Jina Reader с полными метаданными',
            'url': 'https://docs-chatcenter.edna.ru/docs/start/whatis',
            'content': """Title: Что такое edna Chat Center | edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/start/whatis
Content Length: 2456
Language Detected: Russian
Published Time: 2024-07-24T10:30:00Z
Images: 3
Links: 12
Markdown Content:

# Что такое edna Chat Center

edna Chat Center — это система для организации работы с клиентами.

## Роли в системе

- **Агент** — сотрудник, который общается с клиентами
- **Супервизор** — руководитель агентов  
- **Администратор** — настраивает систему

## Поддерживаемые каналы

- Telegram
- WhatsApp
- Viber
- Веб-виджет
""",
            'strategy': 'auto'
        },
        {
            'name': 'HTML Docusaurus',
            'url': 'https://docs-chatcenter.edna.ru/docs/agent/routing',
            'content': """<!DOCTYPE html>
<html>
<head>
    <title>Настройка маршрутизации</title>
    <meta name="description" content="Руководство по настройке маршрутизации">
</head>
<body>
    <nav class="theme-doc-breadcrumbs">
        <a href="/docs">Документация</a>
        <a href="/docs/agent">Агент</a>
    </nav>
    <article class="theme-doc-markdown">
        <h1>Настройка маршрутизации</h1>
        <p>Маршрутизация позволяет распределять сообщения между агентами.</p>
    </article>
</body>
</html>""",
            'strategy': 'auto'
        },
        {
            'name': 'Принудительный Jina Reader',
            'url': 'https://example.com/page',
            'content': """Обычный текст без специальной разметки.""",
            'strategy': 'force_jina'
        }
    ]
    
    passed = 0
    for case in test_cases:
        print(f"\n📄 Тест: {case['name']}")
        
        try:
            result = load_content_universal(case['url'], case['content'], case['strategy'])
            
            # Проверяем базовые поля
            required_fields = ['url', 'title', 'content', 'content_type', 'page_type']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                print(f"   ❌ Отсутствуют поля: {missing_fields}")
                continue
            
            # Проверяем наличие контента
            if not result.get('content'):
                print(f"   ❌ Пустой контент")
                continue
            
            # Показываем ключевые метаданные
            key_metadata = {
                'content_type': result.get('content_type'),
                'page_type': result.get('page_type'),
                'section': result.get('section'),
                'user_role': result.get('user_role'),
                'permissions': result.get('permissions'),
                'channels': result.get('channels'),
                'features': result.get('features')
            }
            
            print(f"   📊 Метаданные:")
            for key, value in key_metadata.items():
                if value is not None:
                    print(f"      {key}: {value}")
            
            print(f"   ✅ Успешно загружено")
            passed += 1
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    print(f"\n📊 Результат: {passed}/{len(test_cases)} тестов пройдено")
    return passed == len(test_cases)


def test_loader_info():
    """Тест информации о загрузчике."""
    print("\n🧪 Тестирование информации о загрузчике...")
    
    loader = UniversalLoader()
    
    # Проверяем поддерживаемые стратегии
    strategies = loader.get_supported_strategies()
    expected_strategies = ['auto', 'jina', 'html', 'force_jina', 'html_docusaurus', 'markdown', 'text']
    
    missing_strategies = [s for s in expected_strategies if s not in strategies]
    if missing_strategies:
        print(f"   ❌ Отсутствуют стратегии: {missing_strategies}")
        return False
    
    print(f"   ✅ Поддерживаемые стратегии: {strategies}")
    
    # Проверяем информацию о типах контента
    content_types = loader.get_content_type_info()
    if not content_types:
        print(f"   ❌ Отсутствует информация о типах контента")
        return False
    
    print(f"   ✅ Типы контента:")
    for content_type, description in content_types.items():
        print(f"      {content_type}: {description}")
    
    return True


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование универсального загрузчика\n")
    
    tests = [
        test_content_type_detection,
        test_page_type_detection,
        test_universal_loading,
        test_loader_info,
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
        print("\n📈 Преимущества универсального загрузчика:")
        print("   • Автоматическое определение типа контента")
        print("   • Единый интерфейс для всех источников")
        print("   • Обогащенные метаданные из всех источников")
        print("   • Гибкие стратегии парсинга")
        print("   • Упрощенный код pipeline")
        return True
    else:
        print("⚠️ Некоторые тесты не прошли")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

