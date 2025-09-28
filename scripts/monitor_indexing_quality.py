#!/usr/bin/env python3
"""
Мониторинг качества индексации в реальном времени
"""
import asyncio
import time
import sys
from typing import Dict, List
from pathlib import Path
from loguru import logger

# Добавляем путь к модулю app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieval import client, COLLECTION
from app.services.bge_embeddings import embed_unified
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from qdrant_client.models import Filter


class IndexingQualityMonitor:
    """Мониторинг качества индексации"""

    def __init__(self):
        self.collection = COLLECTION
        self.client = client
        self.test_queries = [
            "Какие каналы поддерживаются в чат-центре?",
            "Как настроить Telegram бота?",
            "Что такое веб-виджет?",
            "Как работает edna Chat Center?",
            "Настройка маршрутизации"
        ]

    async def check_russian_content_percentage(self) -> float:
        """Проверяет процент документов с русским текстом"""
        try:
            results = self.client.scroll(
                collection_name=self.collection,
                limit=100,
                with_payload=True
            )

            docs = results[0]
            russian_docs = 0

            for doc in docs:
                content = str(doc.payload.get("content", ""))
                if content and any(ord(c) > 127 for c in content[:200]):
                    russian_docs += 1

            return (russian_docs / len(docs) * 100) if docs else 0

        except Exception as e:
            logger.error(f"Ошибка при проверке русского контента: {e}")
            return 0

    async def check_key_terms_availability(self) -> Dict[str, bool]:
        """Проверяет доступность ключевых терминов"""
        key_terms = ["канал", "telegram", "виджет", "чат-центр", "edna"]
        results = {}

        for term in key_terms:
            try:
                filter_result = self.client.scroll(
                    collection_name=self.collection,
                    scroll_filter=Filter(
                        must=[
                            {'key': 'content', 'match': {'text': term}}
                        ]
                    ),
                    limit=1,
                    with_payload=True
                )
                results[term] = len(filter_result[0]) > 0
            except Exception as e:
                logger.error(f"Ошибка при поиске термина '{term}': {e}")
                results[term] = False

        return results

    async def test_search_quality(self) -> Dict[str, float]:
        """Тестирует качество поиска"""
        results = {}

        for query in self.test_queries:
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

                # Оцениваем качество по количеству найденных результатов
                quality_score = min(1.0, len(reranked) / 5.0)
                results[query] = quality_score

            except Exception as e:
                logger.error(f"Ошибка при тестировании поиска для '{query}': {e}")
                results[query] = 0.0

        return results

    async def get_health_status(self) -> Dict[str, any]:
        """Получает общий статус здоровья индекса"""
        try:
            # Проверяем базовую статистику
            info = self.client.get_collection(self.collection)
            total_docs = info.points_count

            # Проверяем процент русского контента
            russian_pct = await self.check_russian_content_percentage()

            # Проверяем ключевые термины
            key_terms = await self.check_key_terms_availability()
            available_terms = sum(key_terms.values())
            total_terms = len(key_terms)

            # Тестируем качество поиска
            search_quality = await self.test_search_quality()
            avg_search_quality = sum(search_quality.values()) / len(search_quality)

            # Определяем общий статус
            if russian_pct >= 80 and available_terms >= total_terms * 0.8 and avg_search_quality >= 0.7:
                status = "HEALTHY"
                status_emoji = "✅"
            elif russian_pct >= 50 and available_terms >= total_terms * 0.5 and avg_search_quality >= 0.5:
                status = "WARNING"
                status_emoji = "⚠️"
            else:
                status = "CRITICAL"
                status_emoji = "❌"

            return {
                "status": status,
                "status_emoji": status_emoji,
                "total_documents": total_docs,
                "russian_content_percentage": russian_pct,
                "key_terms_available": f"{available_terms}/{total_terms}",
                "average_search_quality": avg_search_quality,
                "key_terms_details": key_terms,
                "search_quality_details": search_quality,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Ошибка при получении статуса здоровья: {e}")
            return {
                "status": "ERROR",
                "status_emoji": "💥",
                "error": str(e),
                "timestamp": time.time()
            }

    async def monitor_continuously(self, interval: int = 300):
        """Непрерывный мониторинг с заданным интервалом"""
        logger.info(f"🔄 Запускаем мониторинг с интервалом {interval} секунд")

        while True:
            try:
                health = await self.get_health_status()

                print(f"\n{health['status_emoji']} СТАТУС ИНДЕКСА: {health['status']}")
                print(f"📊 Документов: {health.get('total_documents', 'N/A')}")
                print(f"🇷🇺 Русский контент: {health.get('russian_content_percentage', 0):.1f}%")
                print(f"🔑 Ключевые термины: {health.get('key_terms_available', 'N/A')}")
                print(f"🔍 Качество поиска: {health.get('average_search_quality', 0):.2f}")

                if health['status'] == 'CRITICAL':
                    print("🚨 КРИТИЧЕСКИЙ СТАТУС! Требуется немедленная переиндексация!")
                elif health['status'] == 'WARNING':
                    print("⚠️ ВНИМАНИЕ! Рекомендуется переиндексация.")
                else:
                    print("✅ Все в порядке!")

                # Ждем до следующей проверки
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                print("\n🛑 Мониторинг остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка в мониторинге: {e}")
                await asyncio.sleep(interval)


async def main():
    """Основная функция"""
    monitor = IndexingQualityMonitor()

    # Получаем текущий статус
    health = await monitor.get_health_status()

    print("="*60)
    print("📊 МОНИТОРИНГ КАЧЕСТВА ИНДЕКСАЦИИ")
    print("="*60)

    print(f"\n{health['status_emoji']} СТАТУС: {health['status']}")

    if 'error' not in health:
        print(f"📊 Всего документов: {health['total_documents']}")
        print(f"🇷🇺 Русский контент: {health['russian_content_percentage']:.1f}%")
        print(f"🔑 Ключевые термины: {health['key_terms_available']}")
        print(f"🔍 Среднее качество поиска: {health['average_search_quality']:.2f}")

        print(f"\n🔑 ДЕТАЛИ КЛЮЧЕВЫХ ТЕРМИНОВ:")
        for term, available in health['key_terms_details'].items():
            print(f"   {'✅' if available else '❌'} {term}")

        print(f"\n🔍 ДЕТАЛИ КАЧЕСТВА ПОИСКА:")
        for query, quality in health['search_quality_details'].items():
            print(f"   {quality:.2f} {query}")

    else:
        print(f"❌ Ошибка: {health['error']}")

    print("="*60)

    # Спрашиваем, нужно ли запустить непрерывный мониторинг
    try:
        response = input("\n🔄 Запустить непрерывный мониторинг? (y/n): ").lower().strip()
        if response in ['y', 'yes', 'да']:
            await monitor.monitor_continuously(interval=300)  # 5 минут
    except KeyboardInterrupt:
        print("\n👋 До свидания!")


if __name__ == "__main__":
    asyncio.run(main())
