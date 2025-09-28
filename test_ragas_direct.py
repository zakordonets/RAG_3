#!/usr/bin/env python3
"""
Прямой тест RAGAS evaluator
"""

import asyncio
import os
from app.services.ragas_evaluator import ragas_evaluator

async def test_ragas_direct():
    """Прямой тест RAGAS evaluator"""

    print("🧪 Прямой тест RAGAS evaluator")
    print("=" * 50)

    # Тестовые данные
    query = "Какие каналы поддерживаются в edna Chat Center?"
    response = "В edna Chat Center поддерживаются следующие каналы: Telegram, WhatsApp, Viber, SMS, веб-виджет."
    contexts = [
        "edna Chat Center поддерживает интеграцию с различными каналами связи включая мессенджеры и SMS",
        "Система позволяет работать с Telegram, WhatsApp, Viber через единый интерфейс",
        "Веб-виджет позволяет интегрировать чат на сайт компании"
    ]
    sources = ["https://docs-chatcenter.edna.ru/channels"]

    print(f"📝 Запрос: {query}")
    print(f"💬 Ответ: {response}")
    print(f"📚 Контекстов: {len(contexts)}")

    try:
        print("\n🔄 Запускаем RAGAS оценку...")
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

        if evaluation_time < 10:
            print("🎯 Отлично: Быстрая оценка!")
        elif evaluation_time < 20:
            print("✅ Хорошо: Приемлемое время")
        else:
            print("⚠️  Медленно: Требуется оптимизация")

    except Exception as e:
        print(f"❌ Ошибка RAGAS: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ragas_direct())
