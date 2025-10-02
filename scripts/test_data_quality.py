#!/usr/bin/env python3
"""
Тест качества данных для системы индексации.
Проверяет конкретные аспекты качества: пустые страницы, метаданные, контент.
"""

import sys
from pathlib import Path
import json
import time
from typing import Dict, List, Any, Optional
from loguru import logger

# Добавляем корневую директорию проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from ingestion.universal_loader import load_content_universal
from app.sources_registry import extract_url_metadata
from ingestion.processors.content_processor import ContentProcessor


class DataQualityTester:
    """Тестер качества данных."""

    def __init__(self):
        self.client = client
        self.collection = COLLECTION
        self.test_results = []

    def test_empty_pages_detection(self) -> Dict[str, Any]:
        """Тест обнаружения пустых страниц."""
        logger.info("🔍 Тестирование обнаружения пустых страниц...")

        try:
            # Получаем выборку точек
            scroll_result = self.client.scroll(
                collection_name=self.collection,
                limit=50,
                with_payload=True,
                with_vectors=False
            )

            points = scroll_result[0]
            empty_pages = []
            short_pages = []

            for point in points:
                payload = point.get('payload', {})
                text = payload.get('text', '')
                url = payload.get('url', 'unknown')

                if not text or len(text.strip()) == 0:
                    empty_pages.append(url)
                elif len(text.strip()) < 50:
                    short_pages.append(url)

            return {
                "total_checked": len(points),
                "empty_pages": len(empty_pages),
                "short_pages": len(short_pages),
                "empty_urls": empty_pages[:10],  # Первые 10 для примера
                "short_urls": short_pages[:10]
            }

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования пустых страниц: {e}")
            return {"error": str(e)}

    def test_metadata_completeness(self) -> Dict[str, Any]:
        """Тест полноты метаданных."""
        logger.info("🔍 Тестирование полноты метаданных...")

        try:
            scroll_result = self.client.scroll(
                collection_name=self.collection,
                limit=50,
                with_payload=True,
                with_vectors=False
            )

            points = scroll_result[0]
            required_fields = [
                'url', 'title', 'content_type', 'section',
                'user_role', 'permissions', 'content_length'
            ]

            field_stats = {field: 0 for field in required_fields}
            missing_fields = {field: [] for field in required_fields}

            for point in points:
                payload = point.get('payload', {})
                url = payload.get('url', 'unknown')

                for field in required_fields:
                    if field in payload and payload[field]:
                        field_stats[field] += 1
                    else:
                        missing_fields[field].append(url)

            # Вычисляем процент полноты
            completeness = {field: (count / len(points)) * 100 for field, count in field_stats.items()}

            return {
                "total_checked": len(points),
                "field_completeness": completeness,
                "missing_fields": {field: urls[:5] for field, urls in missing_fields.items() if urls}
            }

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования метаданных: {e}")
            return {"error": str(e)}

    def test_content_quality(self) -> Dict[str, Any]:
        """Тест качества контента."""
        logger.info("🔍 Тестирование качества контента...")

        try:
            scroll_result = self.client.scroll(
                collection_name=self.collection,
                limit=50,
                with_payload=True,
                with_vectors=False
            )

            points = scroll_result[0]
            quality_issues = []

            for point in points:
                payload = point.get('payload', {})
                text = payload.get('text', '')
                url = payload.get('url', 'unknown')

                issues = []

                # Проверяем длину текста
                if len(text) < 100:
                    issues.append("Слишком короткий текст")

                # Проверяем наличие HTML тегов
                if '<' in text and '>' in text:
                    issues.append("Содержит HTML теги")

                # Проверяем наличие только пробелов
                if text.strip() == '':
                    issues.append("Пустой текст")

                # Проверяем наличие повторяющихся символов
                if len(set(text)) < 10:
                    issues.append("Слишком мало уникальных символов")

                if issues:
                    quality_issues.append({
                        "url": url,
                        "issues": issues
                    })

            return {
                "total_checked": len(points),
                "quality_issues": len(quality_issues),
                "issue_details": quality_issues[:10]  # Первые 10 для примера
            }

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования качества контента: {e}")
            return {"error": str(e)}

    def test_url_metadata_extraction(self) -> Dict[str, Any]:
        """Тест извлечения метаданных из URL."""
        logger.info("🔍 Тестирование извлечения метаданных из URL...")

        test_urls = [
            "https://docs-chatcenter.edna.ru/docs/start/whatis",
            "https://docs-chatcenter.edna.ru/docs/agent/quick-start",
            "https://docs-chatcenter.edna.ru/docs/supervisor/dashboard",
            "https://docs-chatcenter.edna.ru/docs/admin/settings",
            "https://docs-chatcenter.edna.ru/docs/api/create-agent",
            "https://docs-chatcenter.edna.ru/faq",
            "https://docs-chatcenter.edna.ru/blog/latest-updates"
        ]

        results = []

        for url in test_urls:
            try:
                metadata = extract_url_metadata(url)
                results.append({
                    "url": url,
                    "metadata": metadata,
                    "success": True
                })
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "success": False
                })

        successful = sum(1 for r in results if r['success'])

        return {
            "total_tested": len(test_urls),
            "successful": successful,
            "results": results
        }

    def test_jina_reader_parsing(self) -> Dict[str, Any]:
        """Тест парсинга Jina Reader контента."""
        logger.info("🔍 Тестирование парсинга Jina Reader...")

        test_content = """Title: Тестовая страница | edna Chat Center
URL Source: https://docs-chatcenter.edna.ru/docs/test
Content Length: 1500
Language Detected: Russian
Published Time: 2024-01-01T00:00:00Z
Images: 2
Links: 8
Markdown Content:

# Тестовая страница

Это тестовая страница для проверки парсинга Jina Reader.

## Основные возможности

1. **Функция 1** — описание
2. **Функция 2** — описание
3. **Функция 3** — описание

## Дополнительная информация

- Пункт 1
- Пункт 2
- Пункт 3
"""

        try:
            processor = ContentProcessor()
            processed = processor.process(test_content, "https://example.com/test", "jina")

            # Проверяем наличие обязательных полей
            missing_fields = []
            if not processed.title:
                missing_fields.append('title')
            if not processed.content:
                missing_fields.append('content')

            return {
                "success": True,
                "parsed_fields": ['title', 'content', 'page_type'],
                "missing_fields": missing_fields,
                "content_length": len(processed.content),
                "title": processed.title,
                "page_type": processed.page_type
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def test_content_loading_strategies(self) -> Dict[str, Any]:
        """Тест различных стратегий загрузки контента."""
        logger.info("🔍 Тестирование стратегий загрузки контента...")

        test_cases = [
            {
                "name": "Jina Reader контент",
                "content": """Title: Тест
URL Source: https://example.com
Markdown Content:

# Тест

Содержимое.""",
                "strategy": "auto"
            },
            {
                "name": "HTML Docusaurus",
                "content": """<!DOCTYPE html>
<html>
<body>
<nav class="theme-doc-breadcrumbs">
<article class="theme-doc-markdown">
<h1>Тест</h1>
<p>Содержимое.</p>
</article>
</body>
</html>""",
                "strategy": "auto"
            },
            {
                "name": "Обычный HTML",
                "content": """<!DOCTYPE html>
<html>
<head><title>Тест</title></head>
<body>
<h1>Тест</h1>
<p>Содержимое.</p>
</body>
</html>""",
                "strategy": "auto"
            }
        ]

        results = []

        for case in test_cases:
            try:
                result = load_content_universal("https://example.com", case['content'], case['strategy'])

                results.append({
                    "name": case['name'],
                    "success": True,
                    "content_type": result.get('content_type'),
                    "title": result.get('title'),
                    "content_length": len(result.get('content', '')),
                    "has_content": bool(result.get('content'))
                })

            except Exception as e:
                results.append({
                    "name": case['name'],
                    "success": False,
                    "error": str(e)
                })

        successful = sum(1 for r in results if r['success'])

        return {
            "total_tested": len(test_cases),
            "successful": successful,
            "results": results
        }


def print_quality_report(empty_pages: Dict, metadata: Dict, content: Dict,
                        url_metadata: Dict, jina_parsing: Dict, loading: Dict):
    """Выводит отчет о качестве данных."""
    print("\n" + "="*80)
    print("📊 ОТЧЕТ О КАЧЕСТВЕ ДАННЫХ")
    print("="*80)

    # Пустые страницы
    if "error" not in empty_pages:
        print(f"\n🔍 ПУСТЫЕ СТРАНИЦЫ:")
        print(f"   Проверено страниц: {empty_pages['total_checked']}")
        print(f"   Пустых страниц: {empty_pages['empty_pages']}")
        print(f"   Коротких страниц: {empty_pages['short_pages']}")

        if empty_pages['empty_urls']:
            print(f"   Примеры пустых URL:")
            for url in empty_pages['empty_urls']:
                print(f"     • {url}")

    # Метаданные
    if "error" not in metadata:
        print(f"\n📋 МЕТАДАННЫЕ:")
        print(f"   Проверено страниц: {metadata['total_checked']}")
        print(f"   Полнота полей:")
        for field, completeness in metadata['field_completeness'].items():
            print(f"     {field}: {completeness:.1f}%")

    # Качество контента
    if "error" not in content:
        print(f"\n📝 КАЧЕСТВО КОНТЕНТА:")
        print(f"   Проверено страниц: {content['total_checked']}")
        print(f"   Проблемных страниц: {content['quality_issues']}")

        if content['issue_details']:
            print(f"   Примеры проблем:")
            for issue in content['issue_details'][:3]:
                print(f"     • {issue['url']}: {', '.join(issue['issues'])}")

    # URL метаданные
    print(f"\n🔗 МЕТАДАННЫЕ URL:")
    print(f"   Протестировано URL: {url_metadata['total_tested']}")
    print(f"   Успешно обработано: {url_metadata['successful']}")

    # Jina Reader парсинг
    print(f"\n📖 ПАРСИНГ JINA READER:")
    if jina_parsing['success']:
        print(f"   ✅ Успешно")
        print(f"   Заголовок: {jina_parsing['title']}")
        print(f"   Длина контента: {jina_parsing['content_length']} символов")
        print(f"   Язык: {jina_parsing['language']}")
    else:
        print(f"   ❌ Ошибка: {jina_parsing['error']}")

    # Стратегии загрузки
    print(f"\n🚀 СТРАТЕГИИ ЗАГРУЗКИ:")
    print(f"   Протестировано стратегий: {loading['total_tested']}")
    print(f"   Успешно: {loading['successful']}")

    for result in loading['results']:
        if result['success']:
            print(f"   ✅ {result['name']}: {result['content_type']} ({result['content_length']} символов)")
        else:
            print(f"   ❌ {result['name']}: {result['error']}")

    print("\n" + "="*80)


def main():
    """Основная функция тестирования качества."""
    print("🚀 Запуск тестирования качества данных\n")

    tester = DataQualityTester()

    # Запускаем все тесты
    print("1️⃣ Тестирование пустых страниц...")
    empty_pages = tester.test_empty_pages_detection()

    print("2️⃣ Тестирование метаданных...")
    metadata = tester.test_metadata_completeness()

    print("3️⃣ Тестирование качества контента...")
    content = tester.test_content_quality()

    print("4️⃣ Тестирование URL метаданных...")
    url_metadata = tester.test_url_metadata_extraction()

    print("5️⃣ Тестирование Jina Reader парсинга...")
    jina_parsing = tester.test_jina_reader_parsing()

    print("6️⃣ Тестирование стратегий загрузки...")
    loading = tester.test_content_loading_strategies()

    # Выводим отчет
    print_quality_report(empty_pages, metadata, content, url_metadata, jina_parsing, loading)

    # Определяем общий статус
    total_tests = 6
    passed_tests = 0

    if "error" not in empty_pages:
        passed_tests += 1

    if "error" not in metadata:
        passed_tests += 1

    if "error" not in content:
        passed_tests += 1

    if url_metadata['successful'] > 0:
        passed_tests += 1

    if jina_parsing['success']:
        passed_tests += 1

    if loading['successful'] > 0:
        passed_tests += 1

    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ: {passed_tests}/{total_tests} тестов пройдено")

    if passed_tests == total_tests:
        print("✅ Все тесты качества пройдены успешно!")
        return True
    else:
        print("⚠️ Некоторые тесты качества не прошли")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
