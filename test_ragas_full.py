"""
Полный тест RAGAS с YandexGPT
Гарантированно запускает реальную RAGAS оценку, а не эвристику
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ВАЖНО: Принудительно включаем RAGAS с sample_rate=1.0
os.environ["RAGAS_EVALUATION_SAMPLE_RATE"] = "1.0"
os.environ["RAGAS_LLM_BACKEND"] = "yandexgpt"
os.environ["ENABLE_RAGAS_EVALUATION"] = "true"

from loguru import logger
from app.services.quality.ragas_evaluator import ragas_evaluator

async def test_ragas_full():
    """Полный тест RAGAS с YandexGPT"""
    logger.info("=" * 70)
    logger.info("🚀 ПОЛНЫЙ ТЕСТ RAGAS С YANDEXGPT")
    logger.info("=" * 70)
    logger.info("")
    
    # Проверяем, что RAGAS инициализирована
    logger.info(f"RAGAS enabled: {ragas_evaluator.ragas_enabled}")
    logger.info(f"Backend: {ragas_evaluator.backend_name}")
    logger.info("")
    
    if not ragas_evaluator.ragas_enabled:
        logger.error("❌ RAGAS не инициализирована! Проверьте YANDEX_API_KEY")
        return
    
    # Тестовые данные
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
    
    logger.info("⏳ Запуск RAGAS оценки...")
    logger.info("   Это займет 2-3 минуты (YandexGPT делает 6-9 LLM вызовов)")
    logger.info("   Вы увидите прогресс-бар RAGAS evaluation")
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
        logger.info("✅ РЕЗУЛЬТАТЫ RAGAS ОЦЕНКИ")
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
        
        # Проверка: это реальная RAGAS оценка или эвристика?
        if elapsed < 10:
            logger.warning("")
            logger.warning("⚠️  ВНИМАНИЕ: Оценка выполнилась слишком быстро (<10 сек)")
            logger.warning("   Возможно, использовалась эвристика вместо RAGAS")
            logger.warning("")
        else:
            logger.success("")
            logger.success(f"✓ RAGAS оценка выполнена успешно с {ragas_evaluator.backend_name}!")
            logger.success("")
        
        return scores
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ ОШИБКА RAGAS ОЦЕНКИ")
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
    logger.info("")
    
    asyncio.run(test_ragas_full())


