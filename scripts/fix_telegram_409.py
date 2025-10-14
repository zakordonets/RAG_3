"""
Скрипт для исправления ошибки 409 (Conflict) в Telegram Bot API.

Ошибка 409 возникает когда:
1. Несколько экземпляров бота используют long polling одновременно
2. У бота установлен webhook, который конфликтует с polling
3. Предыдущий процесс бота не завершился корректно

Этот скрипт:
- Удаляет webhook (если установлен)
- Очищает pending updates
- Проверяет статус бота
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from loguru import logger
from app.config import CONFIG


BOT_TOKEN = CONFIG.telegram_bot_token
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_webhook_info() -> dict:
    """Получить информацию о webhook."""
    try:
        response = requests.get(f"{API_URL}/getWebhookInfo", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return data.get("result", {})
        logger.error(f"Failed to get webhook info: {response.status_code}")
        return {}
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return {}


def delete_webhook() -> bool:
    """Удалить webhook если он установлен."""
    try:
        # Удаляем webhook и включаем параметр drop_pending_updates
        response = requests.post(
            f"{API_URL}/deleteWebhook",
            json={"drop_pending_updates": True},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                logger.info("✅ Webhook successfully deleted")
                return True
        logger.error(f"Failed to delete webhook: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return False


def get_me() -> dict:
    """Проверить статус бота."""
    try:
        response = requests.get(f"{API_URL}/getMe", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return data.get("result", {})
        logger.error(f"Failed to get bot info: {response.status_code}")
        return {}
    except Exception as e:
        logger.error(f"Error getting bot info: {e}")
        return {}


def test_get_updates() -> bool:
    """Попытаться получить обновления для проверки."""
    try:
        response = requests.get(
            f"{API_URL}/getUpdates",
            params={"timeout": 1, "limit": 1},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                logger.info("✅ getUpdates работает корректно")
                return True
        elif response.status_code == 409:
            logger.error("❌ Ошибка 409: Conflict - другой экземпляр бота всё ещё активен")
            return False

        logger.error(f"Failed to get updates: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error testing getUpdates: {e}")
        return False


def main() -> None:
    """Основная логика исправления."""
    logger.info("=" * 60)
    logger.info("🔧 Telegram Bot 409 Conflict Fix Tool")
    logger.info("=" * 60)

    # 1. Проверяем статус бота
    logger.info("\n📋 Шаг 1: Проверка статуса бота...")
    bot_info = get_me()
    if bot_info:
        logger.info(f"✅ Бот активен: @{bot_info.get('username', 'unknown')}")
        logger.info(f"   ID: {bot_info.get('id', 'unknown')}")
        logger.info(f"   Имя: {bot_info.get('first_name', 'unknown')}")
    else:
        logger.error("❌ Не удалось получить информацию о боте. Проверьте токен!")
        sys.exit(1)

    # 2. Проверяем webhook
    logger.info("\n📋 Шаг 2: Проверка webhook...")
    webhook_info = get_webhook_info()
    if webhook_info:
        webhook_url = webhook_info.get("url", "")
        pending_count = webhook_info.get("pending_update_count", 0)

        if webhook_url:
            logger.warning(f"⚠️  Webhook установлен: {webhook_url}")
            logger.info(f"   Pending updates: {pending_count}")
            logger.info("\n🔄 Удаление webhook...")
            if delete_webhook():
                logger.info("✅ Webhook успешно удалён")
            else:
                logger.error("❌ Не удалось удалить webhook")
                sys.exit(1)
        else:
            logger.info("✅ Webhook не установлен")
            if pending_count > 0:
                logger.info(f"⚠️  Pending updates: {pending_count}")
                logger.info("🔄 Очистка pending updates через deleteWebhook...")
                delete_webhook()  # Это очистит pending updates

    # 3. Тестируем getUpdates
    logger.info("\n📋 Шаг 3: Проверка getUpdates...")
    if test_get_updates():
        logger.info("\n" + "=" * 60)
        logger.info("✅ Всё исправлено! Можно запускать бота.")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("\n" + "=" * 60)
        logger.error("❌ Проблема не решена!")
        logger.error("")
        logger.error("Возможные причины:")
        logger.error("1. Другой экземпляр бота всё ещё запущен")
        logger.error("2. Бот запущен в Docker/Kubernetes")
        logger.error("3. Webhook установлен на другом сервере")
        logger.error("")
        logger.error("Рекомендации:")
        logger.error("- Проверьте запущенные процессы: Get-Process python")
        logger.error("- Проверьте Docker: docker ps | grep telegram")
        logger.error("- Подождите 1-2 минуты и попробуйте снова")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
