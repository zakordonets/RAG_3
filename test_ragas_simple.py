#!/usr/bin/env python3
"""
Простой тест RAGAS с коротким timeout
"""

import asyncio
import os
from app.services.ragas_evaluator import ragas_evaluator

async def test_ragas_simple():
    """Простой тест RAGAS"""

    print("🧪 Простой тест RAGAS (60 сек timeout)")
    print("=" * 50)

    # Простые тестовые данные
    query = "Что такое edna Chat Center?"
    response = "edna Chat Center - это платформа для управления клиентскими обращениями через различные каналы связи."
    contexts = [
        "edna Chat Center - это комплексное решение для управления клиентскими обращениями",
        "Система позволяет работать с различными каналами связи в едином интерфейсе"
    ]
    sources = ["https://docs-chatcenter.edna.ru/overview"]

    print(f"📝 Запрос: {query}")
    print(f"💬 Ответ: {response}")
    print(f"📚 Контекстов: {len(contexts)}")

    try:
        print("\n🔄 Запускаем RAGAS оценку (60 сек timeout)...")
        start_time = asyncio.get_event_loop().time()

        scores = await ragas_evaluator.evaluate_interaction(
            query=query,
            response=response,
            contexts=contexts,
            sources=sources
        )

        end_time = asyncio.get_event_loop().time()
        evaluation_time = end_time - start_time

        print(f"✅ RAGAS оценка завершена за {evaluation_time:.2f} секунд")
        print("\n📊 Результаты:")
        print(f"  🎯 Faithfulness: {scores.get('faithfulness', 'N/A')}")
        print(f"  📋 Context Precision: {scores.get('context_precision', 'N/A')}")
        print(f"  🔗 Answer Relevancy: {scores.get('answer_relevancy', 'N/A')}")
        print(f"  📈 Overall Score: {scores.get('overall_score', 'N/A')}")

        # Проверяем, были ли это fallback значения
        if scores.get('faithfulness') == 0.8999999999999999:
            print("\n⚠️  Использованы fallback значения")
        else:
            print("\n🎯 Получены реальные RAGAS значения!")

    except Exception as e:
        print(f"❌ Ошибка RAGAS: {e}")

if __name__ == "__main__":
    asyncio.run(test_ragas_simple())
