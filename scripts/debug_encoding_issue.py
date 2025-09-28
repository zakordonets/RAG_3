#!/usr/bin/env python3
"""
Диагностика проблем с кодировкой и извлечением контента
"""
import asyncio
import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION


class EncodingDebugger:
    """Отладчик проблем с кодировкой"""

    def __init__(self):
        self.client = client
        self.collection = COLLECTION

    def check_raw_content(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Проверяет сырое содержимое документов"""
        try:
            results = self.client.scroll(
                collection_name=self.collection,
                limit=limit,
                with_payload=True
            )

            docs = []
            for doc in results[0]:
                payload = doc.payload

                # Получаем сырое содержимое
                raw_content = payload.get("content", "")
                raw_content_type = type(raw_content).__name__
                raw_content_repr = repr(raw_content)

                # Проверяем кодировку
                encoding_info = self._analyze_encoding(raw_content)

                # Проверяем другие поля
                title = payload.get("title", "")
                url = payload.get("url", "")

                docs.append({
                    "id": str(doc.id),
                    "url": url,
                    "title": title,
                    "raw_content_type": raw_content_type,
                    "raw_content_length": len(str(raw_content)),
                    "raw_content_repr": raw_content_repr[:200] + "..." if len(raw_content_repr) > 200 else raw_content_repr,
                    "encoding_info": encoding_info,
                    "title_encoding": self._analyze_encoding(title),
                    "all_payload_keys": list(payload.keys())
                })

            return docs

        except Exception as e:
            return [{"error": str(e)}]

    def _analyze_encoding(self, text: str) -> Dict[str, Any]:
        """Анализирует кодировку текста"""
        if not text:
            return {"is_empty": True}

        try:
            # Проверяем различные кодировки
            encodings_to_try = ['utf-8', 'cp1251', 'iso-8859-1', 'windows-1252']
            encoding_results = {}

            for encoding in encodings_to_try:
                try:
                    if isinstance(text, bytes):
                        decoded = text.decode(encoding)
                        encoding_results[encoding] = {
                            "success": True,
                            "length": len(decoded),
                            "preview": decoded[:100] + "..." if len(decoded) > 100 else decoded
                        }
                    else:
                        # Текст уже в строке, проверяем можно ли его закодировать/декодировать
                        encoded = text.encode(encoding)
                        decoded = encoded.decode(encoding)
                        encoding_results[encoding] = {
                            "success": True,
                            "length": len(decoded),
                            "preview": decoded[:100] + "..." if len(decoded) > 100 else decoded
                        }
                except Exception as e:
                    encoding_results[encoding] = {
                        "success": False,
                        "error": str(e)
                    }

            # Проверяем наличие русских символов
            has_russian = any(ord(c) > 127 for c in str(text)[:200]) if text else False

            return {
                "is_empty": len(str(text).strip()) == 0,
                "has_russian": has_russian,
                "encodings": encoding_results,
                "raw_type": type(text).__name__,
                "raw_length": len(str(text))
            }

        except Exception as e:
            return {"error": str(e)}

    def test_jina_fetch(self, test_urls: List[str]) -> Dict[str, Any]:
        """Тестирует извлечение контента через Jina Reader"""
        results = {}

        for url in test_urls:
            try:
                print(f"   🔍 Тестируем Jina Reader для: {url}")

                # Простой тест доступности URL
                import requests
                response = requests.get(url, timeout=10)

                results[url] = {
                    "http_success": response.status_code == 200,
                    "status_code": response.status_code,
                    "content_length": len(response.content),
                    "content_type": response.headers.get('content-type', 'unknown'),
                    "encoding": response.encoding,
                    "preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
                }

            except Exception as e:
                results[url] = {"error": str(e)}

        return results

    def check_indexing_process(self) -> Dict[str, Any]:
        """Проверяет процесс индексации"""
        try:
            # Получаем несколько документов
            results = self.client.scroll(
                collection_name=self.collection,
                limit=10,
                with_payload=True
            )

            docs = results[0]

            # Анализируем метаданные
            metadata_analysis = {
                "total_docs": len(docs),
                "has_content_field": 0,
                "has_title_field": 0,
                "has_url_field": 0,
                "content_types": {},
                "title_types": {},
                "indexed_via_values": {},
                "source_values": {},
                "language_values": {}
            }

            for doc in docs:
                payload = doc.payload

                # Проверяем наличие полей
                if 'content' in payload:
                    metadata_analysis["has_content_field"] += 1
                    content_type = type(payload['content']).__name__
                    metadata_analysis["content_types"][content_type] = metadata_analysis["content_types"].get(content_type, 0) + 1

                if 'title' in payload:
                    metadata_analysis["has_title_field"] += 1
                    title_type = type(payload['title']).__name__
                    metadata_analysis["title_types"][title_type] = metadata_analysis["title_types"].get(title_type, 0) + 1

                if 'url' in payload:
                    metadata_analysis["has_url_field"] += 1

                # Анализируем значения
                indexed_via = payload.get('indexed_via', 'unknown')
                metadata_analysis["indexed_via_values"][indexed_via] = metadata_analysis["indexed_via_values"].get(indexed_via, 0) + 1

                source = payload.get('source', 'unknown')
                metadata_analysis["source_values"][source] = metadata_analysis["source_values"].get(source, 0) + 1

                language = payload.get('language', 'unknown')
                metadata_analysis["language_values"][language] = metadata_analysis["language_values"].get(language, 0) + 1

            return metadata_analysis

        except Exception as e:
            return {"error": str(e)}


async def main():
    """Основная функция диагностики кодировки"""
    debugger = EncodingDebugger()

    print("🔍 ДИАГНОСТИКА ПРОБЛЕМ С КОДИРОВКОЙ")
    print("="*60)

    # 1. Проверяем сырое содержимое
    print("\n1️⃣ Анализ сырого содержимого документов:")
    raw_docs = debugger.check_raw_content(5)

    for i, doc in enumerate(raw_docs, 1):
        if "error" in doc:
            print(f"   ❌ Ошибка: {doc['error']}")
            continue

        print(f"\n   📄 Документ {i}:")
        print(f"      URL: {doc['url']}")
        print(f"      Заголовок: {doc['title']}")
        print(f"      Тип контента: {doc['raw_content_type']}")
        print(f"      Длина контента: {doc['raw_content_length']}")
        print(f"      Представление: {doc['raw_content_repr']}")
        print(f"      Ключи payload: {doc['all_payload_keys']}")

        encoding_info = doc['encoding_info']
        if not encoding_info.get('is_empty', True):
            print(f"      Кодировка:")
            for enc, info in encoding_info.get('encodings', {}).items():
                if info.get('success'):
                    print(f"         {enc}: ✅ (длина: {info['length']})")
                    if info.get('preview'):
                        print(f"            Превью: {info['preview']}")
                else:
                    print(f"         {enc}: ❌ ({info.get('error', 'Unknown error')})")
        else:
            print(f"      ❌ Контент пустой!")

    # 2. Тестируем Jina Reader
    print("\n2️⃣ Тестирование Jina Reader:")
    test_urls = [
        "https://docs-chatcenter.edna.ru/docs/start/whatis",
        "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features"
    ]

    jina_results = debugger.test_jina_fetch(test_urls)

    for url, result in jina_results.items():
        if "error" in result:
            print(f"   ❌ {url}: {result['error']}")
        else:
            print(f"   🔍 {url}:")
            print(f"      HTTP: {'✅' if result['http_success'] else '❌'} (код: {result['status_code']})")
            print(f"      Длина: {result['content_length']} байт")
            print(f"      Тип: {result['content_type']}")
            print(f"      Кодировка: {result['encoding']}")
            print(f"      Превью: {result['preview']}")

    # 3. Анализ процесса индексации
    print("\n3️⃣ Анализ процесса индексации:")
    indexing_analysis = debugger.check_indexing_process()

    if "error" not in indexing_analysis:
        print(f"   📊 Всего документов: {indexing_analysis['total_docs']}")
        print(f"   📄 С полем content: {indexing_analysis['has_content_field']}")
        print(f"   📝 С полем title: {indexing_analysis['has_title_field']}")
        print(f"   🔗 С полем url: {indexing_analysis['has_url_field']}")

        print(f"\n   📋 Типы контента:")
        for content_type, count in indexing_analysis['content_types'].items():
            print(f"      {content_type}: {count}")

        print(f"\n   📋 Типы заголовков:")
        for title_type, count in indexing_analysis['title_types'].items():
            print(f"      {title_type}: {count}")

        print(f"\n   🔧 Методы индексации:")
        for method, count in indexing_analysis['indexed_via_values'].items():
            print(f"      {method}: {count}")

        print(f"\n   📂 Источники:")
        for source, count in indexing_analysis['source_values'].items():
            print(f"      {source}: {count}")

        print(f"\n   🌐 Языки:")
        for language, count in indexing_analysis['language_values'].items():
            print(f"      {language}: {count}")

    # 4. Диагностика проблем
    print("\n4️⃣ Диагностика проблем:")

    # Проверяем, есть ли контент вообще
    has_content = any(doc.get('raw_content_length', 0) > 0 for doc in raw_docs if 'error' not in doc)
    if not has_content:
        print("   ❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Весь контент пустой!")
        print("   💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
        print("      - Сайт блокирует ботов (используйте Jina Reader)")
        print("      - Проблема с извлечением контента из HTML")
        print("      - Неправильная настройка парсера")
        print("      - Проблема с кодировкой при сохранении")

    # Проверяем использование Jina Reader
    jina_used = any("jina" in str(method) for method in indexing_analysis.get('indexed_via_values', {}).keys())
    if not jina_used:
        print("   ❌ ПРОБЛЕМА: Jina Reader не использовался для индексации")
        print("   💡 РЕШЕНИЕ: Запустить переиндексацию с --strategy jina")

    # Проверяем кодировку
    encoding_issues = []
    for doc in raw_docs:
        if 'error' not in doc:
            encoding_info = doc.get('encoding_info', {})
            if not encoding_info.get('is_empty', True):
                encodings = encoding_info.get('encodings', {})
                utf8_ok = encodings.get('utf-8', {}).get('success', False)
                if not utf8_ok:
                    encoding_issues.append(doc['url'])

    if encoding_issues:
        print(f"   ❌ ПРОБЛЕМА: Проблемы с кодировкой в {len(encoding_issues)} документах")
        print("   💡 РЕШЕНИЕ: Проверить настройки кодировки при извлечении контента")

    print("\n" + "="*60)
    print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
