#!/usr/bin/env python3
"""
Comprehensive indexing quality checker
Проверяет качество индексации русских документов
"""
import asyncio
import json
import re
import sys
from typing import Dict, List, Any
from pathlib import Path
from loguru import logger

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from app.services.bge_embeddings import embed_unified
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from qdrant_client.models import Filter


class IndexingQualityChecker:
    """Проверяет качество индексации документов"""

    def __init__(self):
        self.collection = COLLECTION
        self.client = client

    def check_basic_stats(self) -> Dict[str, Any]:
        """Проверяет базовую статистику индекса"""
        try:
            info = self.client.get_collection(self.collection)
            total_docs = info.points_count

            # Получаем несколько документов для анализа
            results = self.client.scroll(
                collection_name=self.collection,
                limit=100,
                with_payload=True
            )

            docs = results[0]

            # Анализируем содержимое
            russian_docs = 0
            empty_docs = 0
            total_content_length = 0
            sample_titles = []

            for doc in docs:
                payload = doc.payload
                content = str(payload.get("content", ""))
                title = payload.get("title", "Без названия")

                if len(content) > 0:
                    total_content_length += len(content)
                    sample_titles.append(title[:50])

                    # Проверяем наличие русского текста
                    if any(ord(c) > 127 for c in content[:200]):
                        russian_docs += 1
                else:
                    empty_docs += 1

            avg_content_length = total_content_length / len(docs) if docs else 0

            return {
                "total_documents": total_docs,
                "sampled_documents": len(docs),
                "russian_documents": russian_docs,
                "empty_documents": empty_docs,
                "russian_percentage": (russian_docs / len(docs) * 100) if docs else 0,
                "average_content_length": avg_content_length,
                "sample_titles": sample_titles[:10]
            }

        except Exception as e:
            logger.error(f"Ошибка при проверке статистики: {e}")
            return {"error": str(e)}

    def check_specific_content(self, search_terms: List[str]) -> Dict[str, Any]:
        """Проверяет наличие конкретного контента"""
        results = {}

        for term in search_terms:
            try:
                # Поиск по содержимому
                filter_result = self.client.scroll(
                    collection_name=self.collection,
                    scroll_filter=Filter(
                        must=[
                            {'key': 'content', 'match': {'text': term}}
                        ]
                    ),
                    limit=10,
                    with_payload=True
                )

                found_docs = filter_result[0]
                results[term] = {
                    "found": len(found_docs),
                    "documents": [
                        {
                            "title": doc.payload.get("title", "Без названия"),
                            "url": doc.payload.get("url", "Без URL"),
                            "content_preview": str(doc.payload.get("content", ""))[:200]
                        }
                        for doc in found_docs[:5]
                    ]
                }

            except Exception as e:
                results[term] = {"error": str(e)}

        return results

    def test_search_quality(self, test_queries: List[str]) -> Dict[str, Any]:
        """Тестирует качество поиска"""
        results = {}

        for query in test_queries:
            try:
                # Генерируем эмбеддинги
                embeddings = embed_unified(query, return_dense=True, return_sparse=True)

                # Выполняем поиск
                search_results = hybrid_search(
                    query_dense=embeddings['dense_vecs'][0],
                    query_sparse=embeddings['sparse_vecs'][0],
                    k=10
                )

                # Реранкинг
                reranked = rerank(query, search_results, top_n=5)

                results[query] = {
                    "total_found": len(search_results),
                    "top_results": [
                        {
                            "title": doc.get("payload", {}).get("title", "Без названия"),
                            "url": doc.get("payload", {}).get("url", "Без URL"),
                            "score": doc.get("boosted_score", 0.0),
                            "content_preview": str(doc.get("payload", {}).get("content", ""))[:200]
                        }
                        for doc in reranked
                    ]
                }

            except Exception as e:
                results[query] = {"error": str(e)}

        return results

    def check_encoding_issues(self) -> Dict[str, Any]:
        """Проверяет проблемы с кодировкой"""
        try:
            # Получаем несколько документов
            results = self.client.scroll(
                collection_name=self.collection,
                limit=20,
                with_payload=True
            )

            encoding_issues = []
            russian_content = []

            for doc in results[0]:
                payload = doc.payload
                content = str(payload.get("content", ""))
                title = payload.get("title", "Без названия")
                url = payload.get("url", "Без URL")

                # Проверяем на проблемы с кодировкой
                if content:
                    # Ищем символы, которые могут указывать на проблемы с кодировкой
                    if 'â€' in content or 'â€™' in content or 'â€œ' in content:
                        encoding_issues.append({
                            "title": title,
                            "url": url,
                            "issue": "UTF-8 encoding problems detected"
                        })

                    # Проверяем наличие русского текста
                    if any(ord(c) > 127 for c in content[:500]):
                        russian_content.append({
                            "title": title,
                            "url": url,
                            "russian_chars": len([c for c in content if ord(c) > 127]),
                            "content_preview": content[:200]
                        })

            return {
                "encoding_issues": encoding_issues,
                "russian_content_found": len(russian_content),
                "russian_samples": russian_content[:5]
            }

        except Exception as e:
            return {"error": str(e)}

    def generate_report(self) -> Dict[str, Any]:
        """Генерирует полный отчет о качестве индексации"""
        logger.info("🔍 Начинаем проверку качества индексации...")

        # Базовая статистика
        logger.info("📊 Проверяем базовую статистику...")
        basic_stats = self.check_basic_stats()

        # Проверка конкретного контента
        logger.info("🔍 Проверяем наличие конкретного контента...")
        search_terms = ["канал", "telegram", "виджет", "чат-центр", "edna"]
        content_check = self.check_specific_content(search_terms)

        # Тестирование поиска
        logger.info("🔎 Тестируем качество поиска...")
        test_queries = [
            "Какие каналы поддерживаются в чат-центре?",
            "Как настроить Telegram бота?",
            "Что такое веб-виджет?",
            "Как работает edna Chat Center?"
        ]
        search_quality = self.test_search_quality(test_queries)

        # Проверка кодировки
        logger.info("🔤 Проверяем проблемы с кодировкой...")
        encoding_check = self.check_encoding_issues()

        # Формируем отчет
        report = {
            "timestamp": asyncio.get_event_loop().time(),
            "basic_stats": basic_stats,
            "content_check": content_check,
            "search_quality": search_quality,
            "encoding_check": encoding_check,
            "recommendations": self._generate_recommendations(basic_stats, content_check, encoding_check)
        }

        return report

    def _generate_recommendations(self, basic_stats: Dict, content_check: Dict, encoding_check: Dict) -> List[str]:
        """Генерирует рекомендации на основе анализа"""
        recommendations = []

        # Проверяем процент русских документов
        russian_pct = basic_stats.get("russian_percentage", 0)
        if russian_pct < 50:
            recommendations.append(f"❌ КРИТИЧНО: Только {russian_pct:.1f}% документов содержат русский текст. Необходима переиндексация.")
        elif russian_pct < 80:
            recommendations.append(f"⚠️ ВНИМАНИЕ: {russian_pct:.1f}% документов содержат русский текст. Рекомендуется переиндексация.")
        else:
            recommendations.append(f"✅ ХОРОШО: {russian_pct:.1f}% документов содержат русский текст.")

        # Проверяем наличие ключевых терминов
        missing_terms = []
        for term, result in content_check.items():
            if isinstance(result, dict) and result.get("found", 0) == 0:
                missing_terms.append(term)

        if missing_terms:
            recommendations.append(f"❌ КРИТИЧНО: Не найдены документы с терминами: {', '.join(missing_terms)}")

        # Проверяем проблемы с кодировкой
        encoding_issues = encoding_check.get("encoding_issues", [])
        if encoding_issues:
            recommendations.append(f"⚠️ ВНИМАНИЕ: Обнаружено {len(encoding_issues)} документов с проблемами кодировки.")

        # Проверяем среднюю длину контента
        avg_length = basic_stats.get("average_content_length", 0)
        if avg_length < 100:
            recommendations.append("⚠️ ВНИМАНИЕ: Средняя длина контента очень мала. Возможно, документы не полностью индексируются.")

        return recommendations


async def main():
    """Основная функция"""
    checker = IndexingQualityChecker()

    # Генерируем отчет
    report = checker.generate_report()

    # Выводим результаты
    print("\n" + "="*80)
    print("📋 ОТЧЕТ О КАЧЕСТВЕ ИНДЕКСАЦИИ")
    print("="*80)

    # Базовая статистика
    basic_stats = report["basic_stats"]
    if "error" not in basic_stats:
        print(f"\n📊 БАЗОВАЯ СТАТИСТИКА:")
        print(f"   Всего документов: {basic_stats['total_documents']}")
        print(f"   Проанализировано: {basic_stats['sampled_documents']}")
        print(f"   Русских документов: {basic_stats['russian_documents']} ({basic_stats['russian_percentage']:.1f}%)")
        print(f"   Пустых документов: {basic_stats['empty_documents']}")
        print(f"   Средняя длина контента: {basic_stats['average_content_length']:.0f} символов")

        print(f"\n📝 ПРИМЕРЫ ЗАГОЛОВКОВ:")
        for i, title in enumerate(basic_stats['sample_titles'], 1):
            print(f"   {i:2d}. {title}")

    # Проверка контента
    print(f"\n🔍 ПРОВЕРКА КОНТЕНТА:")
    for term, result in report["content_check"].items():
        if isinstance(result, dict) and "error" not in result:
            print(f"   '{term}': найдено {result['found']} документов")
            if result['found'] == 0:
                print(f"      ❌ НЕ НАЙДЕНО!")
        else:
            print(f"   '{term}': ОШИБКА - {result.get('error', 'Unknown error')}")

    # Проблемы с кодировкой
    encoding_check = report["encoding_check"]
    if "error" not in encoding_check:
        print(f"\n🔤 ПРОВЕРКА КОДИРОВКИ:")
        print(f"   Проблем с кодировкой: {len(encoding_check['encoding_issues'])}")
        print(f"   Документов с русским текстом: {encoding_check['russian_content_found']}")

    # Рекомендации
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"   {i}. {rec}")

    # Сохраняем отчет
    report_file = Path("indexing_quality_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Полный отчет сохранен в: {report_file}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
