"""
Полный тест RAGAS с Deepseek
Сравнение с YandexGPT по скорости и качеству
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ВАЖНО: Настраиваем Deepseek для RAGAS
os.environ["RAGAS_EVALUATION_SAMPLE_RATE"] = "1.0"
os.environ["RAGAS_LLM_BACKEND"] = "deepseek"
os.environ["ENABLE_RAGAS_EVALUATION"] = "true"

from loguru import logger
from app.config import CONFIG

# Проверяем наличие Deepseek API key
if not CONFIG.deepseek_api_key:
    logger.error("❌ DEEPSEEK_API_KEY не установлен!")
    logger.error("   Добавьте в .env файл:")
    logger.error("   DEEPSEEK_API_KEY=your_key_here")
    logger.error("   DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions")
    logger.error("   DEEPSEEK_MODEL=deepseek-chat")
    sys.exit(1)

from app.services.quality.ragas_evaluator import ragas_evaluator

async def test_ragas_deepseek():
    """Полный тест RAGAS с Deepseek"""
    logger.info("=" * 70)
    logger.info("🚀 ПОЛНЫЙ ТЕСТ RAGAS С DEEPSEEK")
    logger.info("=" * 70)
    logger.info("")
    
    # Проверяем, что RAGAS инициализирована
    logger.info(f"RAGAS enabled: {ragas_evaluator.ragas_enabled}")
    logger.info(f"Backend: {ragas_evaluator.backend_name}")
    logger.info(f"Model: {CONFIG.deepseek_model}")
    logger.info(f"API URL: {CONFIG.deepseek_api_url}")
    logger.info("")
    
    if not ragas_evaluator.ragas_enabled:
        logger.error("❌ RAGAS не инициализирована!")
        return
    
    # Те же тестовые данные, что и для YandexGPT (для сравнения)
    query = "Как настроить webhook для получения сообщений в edna Chat Center?"
    response = """
    Для настройки webhook в edna Chat Center необходимо:
    
    1. Перейти в раздел Настройки → Webhooks
    2. Указать URL вашего сервера, который будет принимать события
    3. Выбрать типы событий: incoming_message, message_status
    4. Добавить секретный ключ для проверки подписи
    5. Сохранить настройки
    
    API метод для программной настройки: POST /api/v1/webhooks/configure
    
    Пример запроса:
    {
      "url": "https://your-server.com/webhook",
      "events": ["incoming_message", "message_status"],
      "secret": "your_secret_key"
    }
    
    После настройки система будет отправлять POST-запросы на указанный URL
    при возникновении выбранных событий.
    """
    
    contexts = [
        "Webhook позволяет получать уведомления о событиях в Chat Center в реальном времени. Для настройки webhook перейдите в раздел Настройки → Webhooks и укажите URL вашего сервера.",
        "API метод POST /api/v1/webhooks/configure используется для программной настройки webhook. Параметры: url (обязательный), events (массив), secret (для проверки подписи).",
        "Доступные типы событий webhook: incoming_message, message_status, thread_created, thread_closed, operator_assigned.",
        "Webhook отправляет POST-запросы с JSON-payload, содержащим информацию о событии. Подпись запроса проверяется с помощью HMAC-SHA256."
    ]
    
    sources = [
        "https://docs-chatcenter.edna.ru/docs/api/webhooks/configure",
        "https://docs-chatcenter.edna.ru/docs/advanced-settings/webhooks"
    ]
    
    logger.info("📋 Тестовые данные:")
    logger.info(f"   Query: {query}")
    logger.info(f"   Response length: {len(response)} chars")
    logger.info(f"   Contexts: {len(contexts)}")
    logger.info(f"   Sources: {len(sources)}")
    logger.info("")
    
    logger.info("⏳ Запуск RAGAS оценки с Deepseek...")
    logger.info("   Ожидаемое время: 20-60 секунд (быстрее YandexGPT)")
    logger.info("")
    
    import time
    start_time = time.time()
    
    try:
        # Запускаем RAGAS оценку
        scores = await ragas_evaluator.evaluate_interaction(
            query=query,
            response=response,
            contexts=contexts,
            sources=sources
        )
        
        elapsed = time.time() - start_time
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ РЕЗУЛЬТАТЫ RAGAS ОЦЕНКИ С DEEPSEEK")
        logger.info("=" * 70)
        logger.info("")
        logger.info(f"   ⏱️  Время выполнения: {elapsed:.1f} секунд ({elapsed/60:.1f} минут)")
        logger.info("")
        logger.info(f"   📊 Faithfulness:        {scores.get('faithfulness', 0.0):.3f}")
        logger.info(f"      ↳ Насколько ответ соответствует контексту")
        logger.info("")
        logger.info(f"   📊 Context Precision:   {scores.get('context_precision', 0.0):.3f}")
        logger.info(f"      ↳ Насколько релевантен извлеченный контекст")
        logger.info("")
        logger.info(f"   📊 Answer Relevancy:    {scores.get('answer_relevancy', 0.0):.3f}")
        logger.info(f"      ↳ Насколько релевантен ответ запросу")
        logger.info("")
        logger.info(f"   🎯 Overall Score:       {scores.get('overall_score', 0.0):.3f}")
        logger.info("")
        logger.info("=" * 70)
        
        # Сравнение с YandexGPT результатами
        logger.info("")
        logger.info("📊 СРАВНЕНИЕ С YANDEXGPT:")
        logger.info("")
        logger.info("   Метрика              | YandexGPT | Deepseek | Разница")
        logger.info("   " + "-" * 60)
        
        yandex_results = {
            'faithfulness': 1.000,
            'context_precision': 0.000,
            'answer_relevancy': 0.965,
            'overall_score': 0.655,
            'time': 14.0
        }
        
        logger.info(f"   Faithfulness         | {yandex_results['faithfulness']:.3f}     | {scores.get('faithfulness', 0.0):.3f}    | {scores.get('faithfulness', 0.0) - yandex_results['faithfulness']:+.3f}")
        logger.info(f"   Context Precision    | {yandex_results['context_precision']:.3f}     | {scores.get('context_precision', 0.0):.3f}    | {scores.get('context_precision', 0.0) - yandex_results['context_precision']:+.3f}")
        logger.info(f"   Answer Relevancy     | {yandex_results['answer_relevancy']:.3f}     | {scores.get('answer_relevancy', 0.0):.3f}    | {scores.get('answer_relevancy', 0.0) - yandex_results['answer_relevancy']:+.3f}")
        logger.info(f"   Overall Score        | {yandex_results['overall_score']:.3f}     | {scores.get('overall_score', 0.0):.3f}    | {scores.get('overall_score', 0.0) - yandex_results['overall_score']:+.3f}")
        logger.info(f"   Время (секунд)       | {yandex_results['time']:.1f}     | {elapsed:.1f}    | {elapsed - yandex_results['time']:+.1f}")
        logger.info("")
        
        # Анализ скорости
        speedup = yandex_results['time'] / elapsed if elapsed > 0 else 0
        logger.info(f"   🚀 Ускорение: {speedup:.1f}x быстрее")
        logger.info("")
        
        if elapsed < yandex_results['time']:
            logger.success(f"✓ Deepseek работает БЫСТРЕЕ YandexGPT!")
        
        logger.success("")
        logger.success(f"✓ RAGAS оценка с Deepseek выполнена успешно!")
        logger.success("")
        
        return scores
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ ОШИБКА RAGAS ОЦЕНКИ С DEEPSEEK")
        logger.error("=" * 70)
        logger.error(f"   Время до ошибки: {elapsed:.1f} секунд")
        logger.error(f"   Ошибка: {e}")
        logger.error("")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    logger.info("")
    logger.info("🔧 Конфигурация:")
    logger.info(f"   RAGAS_EVALUATION_SAMPLE_RATE: {os.getenv('RAGAS_EVALUATION_SAMPLE_RATE')}")
    logger.info(f"   RAGAS_LLM_BACKEND: {os.getenv('RAGAS_LLM_BACKEND')}")
    logger.info(f"   ENABLE_RAGAS_EVALUATION: {os.getenv('ENABLE_RAGAS_EVALUATION')}")
    logger.info(f"   DEEPSEEK_MODEL: {CONFIG.deepseek_model}")
    logger.info("")
    
    asyncio.run(test_ragas_deepseek())


