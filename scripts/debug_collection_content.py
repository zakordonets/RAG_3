#!/usr/bin/env python3
"""
Тест для проверки содержимого коллекции и диагностики проблем с лоадером
"""
import asyncio
import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from app.services.bge_embeddings import embed_unified
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from qdrant_client.models import Filter


class CollectionDebugger:
    """Отладчик содержимого коллекции"""

    def __init__(self):
        self.client = client
        self.collection = COLLECTION

    def check_collection_info(self) -> Dict[str, Any]:
        """Проверяет базовую информацию о коллекции"""
        try:
            info = self.client.get_collection(self.collection)
            return {
                "exists": True,
                "points_count": info.points_count,
                "vectors_config": info.config.params.vectors,
                "status": info.status
            }
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def sample_documents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает образцы документов из коллекции"""
        try:
            results = self.client.scroll(
                collection_name=self.collection,
                limit=limit,
                with_payload=True
            )

            docs = []
            for doc in results[0]:
                payload = doc.payload
                content = str(payload.get("content", ""))

                # Анализируем содержимое
                has_russian = any(ord(c) > 127 for c in content[:200]) if content else False
                is_empty = len(content.strip()) == 0

                docs.append({
                    "id": str(doc.id),
                    "title": payload.get("title", "Без названия"),
                    "url": payload.get("url", "Без URL"),
                    "page_type": payload.get("page_type", "unknown"),
                    "language": payload.get("language", "unknown"),
                    "source": payload.get("source", "unknown"),
                    "content_length": len(content),
                    "content_preview": content[:200] + "..." if len(content) > 200 else content,
                    "has_russian": has_russian,
                    "is_empty": is_empty,
                    "indexed_via": payload.get("indexed_via", "unknown"),
                    "chunk_index": payload.get("chunk_index", "unknown")
                })

            return docs

        except Exception as e:
            return [{"error": str(e)}]

    def check_content_quality(self) -> Dict[str, Any]:
        """Проверяет качество контента в коллекции"""
        try:
            # Получаем больше документов для анализа
            results = self.client.scroll(
                collection_name=self.collection,
                limit=100,
                with_payload=True
            )

            docs = results[0]
            total_docs = len(docs)

            # Анализируем содержимое
            empty_docs = 0
            russian_docs = 0
            english_docs = 0
            total_content_length = 0
            content_lengths = []

            sources = {}
            page_types = {}
            languages = {}
            indexed_via = {}

            for doc in docs:
                payload = doc.payload
                content = str(payload.get("content", ""))

                # Длина контента
                content_length = len(content)
                content_lengths.append(content_length)
                total_content_length += content_length

                # Пустые документы
                if content_length == 0:
                    empty_docs += 1
                else:
                    # Проверяем язык
                    if any(ord(c) > 127 for c in content[:200]):
                        russian_docs += 1
                    else:
                        english_docs += 1

                # Статистика по источникам
                source = payload.get("source", "unknown")
                sources[source] = sources.get(source, 0) + 1

                page_type = payload.get("page_type", "unknown")
                page_types[page_type] = page_types.get(page_type, 0) + 1

                language = payload.get("language", "unknown")
                languages[language] = languages.get(language, 0) + 1

                indexed_via_method = payload.get("indexed_via", "unknown")
                indexed_via[indexed_via_method] = indexed_via.get(indexed_via_method, 0) + 1

            # Статистика по длине контента
            if content_lengths:
                avg_length = total_content_length / len(content_lengths)
                min_length = min(content_lengths)
                max_length = max(content_lengths)
            else:
                avg_length = min_length = max_length = 0

            return {
                "total_documents": total_docs,
                "empty_documents": empty_docs,
                "russian_documents": russian_docs,
                "english_documents": english_docs,
                "russian_percentage": (russian_docs / total_docs * 100) if total_docs > 0 else 0,
                "empty_percentage": (empty_docs / total_docs * 100) if total_docs > 0 else 0,
                "average_content_length": avg_length,
                "min_content_length": min_length,
                "max_content_length": max_length,
                "sources": sources,
                "page_types": page_types,
                "languages": languages,
                "indexed_via": indexed_via
            }

        except Exception as e:
            return {"error": str(e)}

    def test_search_functionality(self) -> Dict[str, Any]:
        """Тестирует функциональность поиска"""
        test_queries = [
            "Какие каналы поддерживаются в чат-центре?",
            "telegram",
            "виджет",
            "edna Chat Center",
            "настройка"
        ]

        results = {}

        for query in test_queries:
            try:
                # Генерируем эмбеддинги
                embeddings = embed_unified(query, return_dense=True, return_sparse=True)

                # Выполняем поиск
                search_results = hybrid_search(
                    query_dense=embeddings['dense_vecs'][0],
                    query_sparse=embeddings['sparse_vecs'][0],
                    k=5
                )

                # Реранкинг
                reranked = rerank(query, search_results, top_n=3)

                # Анализируем результаты
                result_analysis = []
                for i, doc in enumerate(reranked):
                    payload = doc.get("payload", {})
                    content = str(payload.get("content", ""))

                    result_analysis.append({
                        "rank": i + 1,
                        "title": payload.get("title", "Без названия"),
                        "url": payload.get("url", "Без URL"),
                        "score": doc.get("boosted_score", 0.0),
                        "content_length": len(content),
                        "has_russian": any(ord(c) > 127 for c in content[:200]) if content else False,
                        "content_preview": content[:100] + "..." if len(content) > 100 else content
                    })

                results[query] = {
                    "total_found": len(search_results),
                    "reranked_count": len(reranked),
                    "results": result_analysis
                }

            except Exception as e:
                results[query] = {"error": str(e)}

        return results

    def check_specific_urls(self) -> Dict[str, Any]:
        """Проверяет наличие конкретных URL в коллекции"""
        test_urls = [
            "https://docs-chatcenter.edna.ru/docs/start/whatis",
            "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features",
            "https://docs-chatcenter.edna.ru/docs/sdk/sdk-mobilechat"
        ]

        results = {}

        for url in test_urls:
            try:
                filter_result = self.client.scroll(
                    collection_name=self.collection,
                    scroll_filter=Filter(
                        must=[
                            {'key': 'url', 'match': {'text': url}}
                        ]
                    ),
                    limit=5,
                    with_payload=True
                )

                found_docs = filter_result[0]
                results[url] = {
                    "found": len(found_docs),
                    "documents": [
                        {
                            "title": doc.payload.get("title", "Без названия"),
                            "content_length": len(str(doc.payload.get("content", ""))),
                            "has_russian": any(ord(c) > 127 for c in str(doc.payload.get("content", ""))[:200]),
                            "indexed_via": doc.payload.get("indexed_via", "unknown")
                        }
                        for doc in found_docs
                    ]
                }

            except Exception as e:
                results[url] = {"error": str(e)}

        return results


async def main():
    """Основная функция отладки"""
    debugger = CollectionDebugger()

    print("🔍 ОТЛАДКА КОЛЛЕКЦИИ")
    print("="*60)

    # 1. Базовая информация о коллекции
    print("\n1️⃣ Базовая информация о коллекции:")
    info = debugger.check_collection_info()

    if info.get("exists"):
        print(f"   ✅ Коллекция существует: {info['points_count']} документов")
        print(f"   📊 Статус: {info['status']}")
        print(f"   ⚙️ Конфигурация векторов: {len(info['vectors_config'])} типов")
    else:
        print(f"   ❌ Коллекция не существует: {info.get('error', 'Unknown error')}")
        return

    # 2. Образцы документов
    print("\n2️⃣ Образцы документов:")
    samples = debugger.sample_documents(5)

    for i, doc in enumerate(samples, 1):
        if "error" in doc:
            print(f"   ❌ Ошибка: {doc['error']}")
            continue

        print(f"\n   📄 Документ {i}:")
        print(f"      ID: {doc['id']}")
        print(f"      Заголовок: {doc['title']}")
        print(f"      URL: {doc['url']}")
        print(f"      Тип: {doc['page_type']}")
        print(f"      Язык: {doc['language']}")
        print(f"      Источник: {doc['source']}")
        print(f"      Длина: {doc['content_length']} символов")
        print(f"      {'✅' if doc['has_russian'] else '❌'} Русский текст")
        print(f"      {'❌' if doc['is_empty'] else '✅'} Не пустой")
        print(f"      Индексирован через: {doc['indexed_via']}")
        print(f"      Превью: {doc['content_preview']}")

    # 3. Качество контента
    print("\n3️⃣ Анализ качества контента:")
    quality = debugger.check_content_quality()

    if "error" not in quality:
        print(f"   📊 Всего документов: {quality['total_documents']}")
        print(f"   🇷🇺 Русских: {quality['russian_documents']} ({quality['russian_percentage']:.1f}%)")
        print(f"   🇬🇧 Английских: {quality['english_documents']}")
        print(f"   ❌ Пустых: {quality['empty_documents']} ({quality['empty_percentage']:.1f}%)")
        print(f"   📏 Средняя длина: {quality['average_content_length']:.0f} символов")
        print(f"   📏 Мин/Макс: {quality['min_content_length']}/{quality['max_content_length']}")

        print(f"\n   📂 Источники:")
        for source, count in quality['sources'].items():
            print(f"      {source}: {count}")

        print(f"\n   📄 Типы страниц:")
        for page_type, count in quality['page_types'].items():
            print(f"      {page_type}: {count}")

        print(f"\n   🌐 Языки:")
        for language, count in quality['languages'].items():
            print(f"      {language}: {count}")

        print(f"\n   🔧 Методы индексации:")
        for method, count in quality['indexed_via'].items():
            print(f"      {method}: {count}")

    # 4. Тестирование поиска
    print("\n4️⃣ Тестирование поиска:")
    search_results = debugger.test_search_functionality()

    for query, result in search_results.items():
        if "error" in result:
            print(f"   ❌ {query}: {result['error']}")
        else:
            print(f"   🔍 {query}: найдено {result['total_found']}, после реранкинга {result['reranked_count']}")
            for doc in result['results']:
                print(f"      {doc['rank']}. {doc['title'][:50]}... (длина: {doc['content_length']}, {'🇷🇺' if doc['has_russian'] else '🇬🇧'})")

    # 5. Проверка конкретных URL
    print("\n5️⃣ Проверка конкретных URL:")
    url_results = debugger.check_specific_urls()

    for url, result in url_results.items():
        if "error" in result:
            print(f"   ❌ {url}: {result['error']}")
        else:
            print(f"   {'✅' if result['found'] > 0 else '❌'} {url}: найдено {result['found']} документов")
            for doc in result['documents']:
                print(f"      - {doc['title']} (длина: {doc['content_length']}, {'🇷🇺' if doc['has_russian'] else '🇬🇧'}, {doc['indexed_via']})")

    # 6. Диагностика проблем
    print("\n6️⃣ Диагностика проблем:")

    if quality.get('russian_percentage', 0) < 50:
        print("   ❌ ПРОБЛЕМА: Мало русских документов")
        print("   💡 РЕШЕНИЕ: Переиндексировать с Jina Reader")

    if quality.get('empty_percentage', 0) > 50:
        print("   ❌ ПРОБЛЕМА: Много пустых документов")
        print("   💡 РЕШЕНИЕ: Проверить процесс извлечения контента")

    if quality.get('average_content_length', 0) < 100:
        print("   ❌ ПРОБЛЕМА: Слишком короткий контент")
        print("   💡 РЕШЕНИЕ: Проверить настройки чанкинга")

    if not any("jina" in str(method) for method in quality.get('indexed_via', {}).keys()):
        print("   ❌ ПРОБЛЕМА: Jina Reader не использовался")
        print("   💡 РЕШЕНИЕ: Запустить переиндексацию с --strategy jina")

    # Сохраняем полный отчет (без несериализуемых объектов)
    full_report = {
        "collection_info": {
            "exists": info.get("exists", False),
            "points_count": info.get("points_count", 0),
            "status": info.get("status", "unknown")
        },
        "samples": samples,
        "content_quality": quality,
        "search_results": search_results,
        "url_results": url_results
    }

    report_file = Path("collection_debug_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Полный отчет сохранен в: {report_file}")
    print("\n" + "="*60)
    print("✅ ОТЛАДКА ЗАВЕРШЕНА!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
