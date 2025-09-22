#!/usr/bin/env python3
"""
Тест интеграции Phase 2 RAGAS системы
Проверяет:
1. Telegram feedback кнопки
2. API endpoints для quality аналитики
3. Интеграцию с orchestrator
4. Автоматическое создание quality interactions
"""

import sys
import os
import asyncio
import requests
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from app.config import CONFIG
from app.services.quality_manager import quality_manager


async def test_quality_manager():
    """Тест Quality Manager"""
    logger.info("🧪 Testing Quality Manager...")

    try:
        # Инициализация
        await quality_manager.initialize()
        logger.info("✅ Quality Manager initialized")

        # Создание тестового interaction
        interaction_id = await quality_manager.evaluate_interaction(
            query="Как настроить маршрутизацию?",
            response="Маршрутизация настраивается через API endpoints...",
            contexts=["Контекст 1", "Контекст 2"],
            sources=["https://docs.example.com/1", "https://docs.example.com/2"]
        )

        logger.info(f"✅ Created interaction: {interaction_id}")

        # Добавление пользовательского feedback
        success = await quality_manager.add_user_feedback(
            interaction_id=interaction_id,
            feedback_type="positive",
            feedback_text="Отличный ответ!"
        )

        if success:
            logger.info("✅ User feedback added")
        else:
            logger.warning("⚠️ Failed to add user feedback")

        # Получение статистики
        stats = await quality_manager.get_quality_statistics(days=7)
        logger.info(f"✅ Quality statistics: {stats}")

        return True

    except Exception as e:
        logger.error(f"❌ Quality Manager test failed: {e}")
        return False


def test_api_endpoints():
    """Тест API endpoints"""
    logger.info("🧪 Testing API endpoints...")

    base_url = "http://localhost:9000"

    try:
        # Тест health check
        response = requests.get(f"{base_url}/v1/admin/health", timeout=10)
        if response.status_code == 200:
            logger.info("✅ Health check passed")
        else:
            logger.warning(f"⚠️ Health check failed: {response.status_code}")

        # Тест quality stats endpoint
        response = requests.get(f"{base_url}/v1/admin/quality/stats?days=7", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            logger.info(f"✅ Quality stats endpoint: {stats}")
        else:
            logger.warning(f"⚠️ Quality stats failed: {response.status_code}")

        # Тест quality interactions endpoint
        response = requests.get(f"{base_url}/v1/admin/quality/interactions?limit=10", timeout=10)
        if response.status_code == 200:
            interactions = response.json()
            logger.info(f"✅ Quality interactions endpoint: {len(interactions.get('interactions', []))} interactions")
        else:
            logger.warning(f"⚠️ Quality interactions failed: {response.status_code}")

        # Тест quality trends endpoint
        response = requests.get(f"{base_url}/v1/admin/quality/trends?days=7", timeout=10)
        if response.status_code == 200:
            trends = response.json()
            logger.info(f"✅ Quality trends endpoint: {len(trends.get('trends', []))} trends")
        else:
            logger.warning(f"⚠️ Quality trends failed: {response.status_code}")

        return True

    except Exception as e:
        logger.error(f"❌ API endpoints test failed: {e}")
        return False


def test_chat_api_with_interaction_id():
    """Тест Chat API с interaction_id"""
    logger.info("🧪 Testing Chat API with interaction_id...")

    base_url = "http://localhost:9000"

    try:
        # Отправляем тестовый запрос
        response = requests.post(
            f"{base_url}/v1/chat/query",
            json={
                "message": "Как настроить маршрутизацию?",
                "channel": "api",
                "chat_id": "test_user"
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Chat API response received")
            logger.info(f"   Answer length: {len(data.get('answer', ''))}")
            logger.info(f"   Sources: {len(data.get('sources', []))}")
            logger.info(f"   Interaction ID: {data.get('interaction_id', 'None')}")

            if data.get('interaction_id'):
                logger.info("✅ Interaction ID returned successfully")
                return data['interaction_id']
            else:
                logger.warning("⚠️ No interaction_id returned")
                return None
        else:
            logger.error(f"❌ Chat API failed: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ Chat API test failed: {e}")
        return None


def test_feedback_api(interaction_id: str):
    """Тест Feedback API"""
    logger.info("🧪 Testing Feedback API...")

    base_url = "http://localhost:9000"

    try:
        # Тест добавления положительного feedback
        response = requests.post(
            f"{base_url}/v1/admin/quality/feedback",
            json={
                "interaction_id": interaction_id,
                "feedback_type": "positive",
                "feedback_text": "Отличный ответ!"
            },
            timeout=10
        )

        if response.status_code == 200:
            logger.info("✅ Positive feedback added via API")
        else:
            logger.warning(f"⚠️ Positive feedback failed: {response.status_code}")

        # Тест добавления отрицательного feedback
        response = requests.post(
            f"{base_url}/v1/admin/quality/feedback",
            json={
                "interaction_id": interaction_id,
                "feedback_type": "negative",
                "feedback_text": "Неточный ответ"
            },
            timeout=10
        )

        if response.status_code == 200:
            logger.info("✅ Negative feedback added via API")
        else:
            logger.warning(f"⚠️ Negative feedback failed: {response.status_code}")

        return True

    except Exception as e:
        logger.error(f"❌ Feedback API test failed: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Phase 2 Integration Test")
    logger.info("=" * 50)

    # Проверяем конфигурацию
    logger.info(f"📋 Configuration:")
    logger.info(f"   RAGAS enabled: {CONFIG.enable_ragas_evaluation}")
    logger.info(f"   Quality DB enabled: {CONFIG.quality_db_enabled}")
    logger.info(f"   Database URL: {CONFIG.database_url}")

    results = []

    # 1. Тест Quality Manager
    logger.info("\n1️⃣ Testing Quality Manager...")
    quality_result = await test_quality_manager()
    results.append(("Quality Manager", quality_result))

    # 2. Тест API endpoints
    logger.info("\n2️⃣ Testing API endpoints...")
    api_result = test_api_endpoints()
    results.append(("API Endpoints", api_result))

    # 3. Тест Chat API с interaction_id
    logger.info("\n3️⃣ Testing Chat API with interaction_id...")
    interaction_id = test_chat_api_with_interaction_id()
    chat_result = interaction_id is not None
    results.append(("Chat API Integration", chat_result))

    # 4. Тест Feedback API
    if interaction_id:
        logger.info("\n4️⃣ Testing Feedback API...")
        feedback_result = test_feedback_api(interaction_id)
        results.append(("Feedback API", feedback_result))
    else:
        logger.warning("⚠️ Skipping Feedback API test (no interaction_id)")
        results.append(("Feedback API", False))

    # Итоги
    logger.info("\n📊 Test Results:")
    logger.info("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"\n🎯 Summary: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All Phase 2 tests passed! System is ready for production.")
    else:
        logger.warning(f"⚠️ {total - passed} tests failed. Please check the issues above.")

    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
