"""
Telegram polling worker for RAG backend.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
import requests
from loguru import logger
from typing import Optional
from app.config import CONFIG
from app.utils import write_debug_event
from adapters.telegram_adapter import render_html, split_for_telegram, send as send_html


BOT_TOKEN = CONFIG.telegram_bot_token
POLL_INTERVAL = CONFIG.telegram_poll_interval
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def create_feedback_keyboard(interaction_id: str) -> dict:
    """Build inline keyboard for simple feedback."""
    return {
        "inline_keyboard": [
            [
                {"text": "👍", "callback_data": f"feedback_positive_{interaction_id}"},
                {"text": "👎", "callback_data": f"feedback_negative_{interaction_id}"},
            ]
        ]
    }


def extract_interaction_id(callback_data: str) -> Optional[str]:
    """Extract interaction ID from callback payload."""
    prefixes = ("feedback_positive_", "feedback_negative_")
    for prefix in prefixes:
        if callback_data.startswith(prefix):
            suffix = callback_data[len(prefix):]
            return suffix or None
    return None


def handle_callback_query(callback_query: dict) -> None:
    """Process callback buttons (used for feedback)."""
    try:
        callback_data = callback_query.get("data", "")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")

        if not callback_data or not chat_id:
            return

        if callback_data.startswith("feedback_"):
            feedback_type = "positive" if callback_data.startswith("feedback_positive_") else "negative"
            interaction_id = extract_interaction_id(callback_data)
            if not interaction_id:
                logger.warning(f"Callback without interaction_id: {callback_data!r}")
                return

            try:
                requests.post(
                    f"{CONFIG.api_base_url}/v1/admin/quality/feedback",
                    json={
                        "interaction_id": interaction_id,
                        "feedback_type": feedback_type,
                        "chat_id": chat_id,
                    },
                    timeout=30,
                )
            except Exception as e:
                logger.error(f"Error recording feedback: {e}")

            # Acknowledge callback to Telegram
            try:
                requests.post(
                    f"{API_URL}/answerCallbackQuery",
                    json={
                        "callback_query_id": callback_query.get("id"),
                        "text": "Спасибо, учтём ваш отзыв!",
                    },
                    timeout=10,
                )
            except Exception as e:
                logger.error(f"Error answering callback query: {e}")

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")


def send_telegram_message(chat_id: str, answer_data: dict) -> None:
    """Send a formatted message to Telegram using HTML render pipeline."""
    try:
        answer_markdown = (
            answer_data.get("answer_markdown")
            or answer_data.get("answer")
            or ""
        )
        sources = answer_data.get("sources", []) or []
        interaction_id = answer_data.get("interaction_id", "") or ""
        reply_markup = answer_data.get("reply_markup")

        html_text = render_html(answer_markdown, sources)
        parts = split_for_telegram(html_text)

        if interaction_id and not reply_markup:
            reply_markup = create_feedback_keyboard(interaction_id)

        send_html(chat_id, parts, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")


def handle_message(message: dict) -> None:
    """Process an incoming Telegram message and call RAG API."""
    try:
        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()

        if not chat_id or not text:
            return

        write_debug_event(
            "telegram_message_received",
            {"chat_id": chat_id, "text_length": len(text), "timestamp": time.time()},
        )

        try:
            response = requests.post(
                f"{CONFIG.api_base_url}/v1/chat/query",
                json={
                    "message": text,
                    "channel": "telegram",
                    "chat_id": chat_id,
                },
                timeout=120,
            )

            if response.status_code == 200:
                answer_data = response.json()
                send_telegram_message(str(chat_id), answer_data)

                write_debug_event(
                    "telegram_message_sent",
                    {
                        "chat_id": chat_id,
                        "answer_length": len(answer_data.get("answer", "")),
                        "sources_count": len(answer_data.get("sources", [])),
                        "timestamp": time.time(),
                    },
                )
            else:
                logger.error(
                    f"RAG API error: {response.status_code} - {response.text}"
                )
                send_telegram_message(
                    str(chat_id),
                    {
                        "answer": "Внутренняя ошибка сервера. Попробуйте позже.",
                        "sources": [],
                    },
                )
        except Exception as e:
            logger.error(f"Error calling RAG API: {e}")
            send_telegram_message(
                str(chat_id),
                {
                    "answer": "Внутренняя ошибка сервера. Попробуйте позже.",
                    "sources": [],
                },
            )
    except Exception as e:
        logger.error(f"Error handling message: {e}")


def delete_webhook() -> bool:
    """
    Удаляет webhook и очищает pending updates.

    Returns:
        True если webhook успешно удалён
    """
    try:
        resp = requests.post(
            f"{API_URL}/deleteWebhook",
            json={"drop_pending_updates": True},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                logger.info("✅ Webhook successfully deleted")
                return True
        logger.error(f"Failed to delete webhook: {resp.status_code} - {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return False


def handle_409_conflict() -> bool:
    """
    Обрабатывает ошибку 409 (Conflict).

    Ошибка 409 возникает когда:
    - Несколько экземпляров бота используют long polling одновременно
    - У бота установлен webhook
    - Предыдущий процесс бота не завершился корректно

    Returns:
        True если проблема решена
    """
    logger.warning("⚠️ Обнаружена ошибка 409 (Conflict)")
    logger.info("Попытка исправления: удаление webhook...")

    if delete_webhook():
        logger.info("✅ Webhook удалён, ожидание 2 секунды...")
        time.sleep(2)
        return True

    logger.error("❌ Не удалось удалить webhook")
    logger.error("Возможные причины:")
    logger.error("  - Другой экземпляр бота всё ещё запущен")
    logger.error("  - Бот запущен в Docker/Kubernetes")
    logger.error("Подождите 1-2 минуты и перезапустите бота")
    return False


def get_updates(offset: int | None = None) -> list:
    """Fetch updates from Telegram API (long polling)."""
    try:
        params = {"timeout": 30, "offset": offset}
        resp = requests.get(f"{API_URL}/getUpdates", params=params, timeout=40)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return data.get("result", [])
            logger.error(f"Telegram API error: {data}")
            return []

        if resp.status_code == 409:
            # Конфликт: пытаемся исправить
            if handle_409_conflict():
                # Повторная попытка после исправления
                logger.info("Повторная попытка получения updates...")
                resp = requests.get(f"{API_URL}/getUpdates", params=params, timeout=40)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        return data.get("result", [])
            return []

        logger.error(f"Failed to get updates: {resp.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return []


def verify_bot_ready() -> bool:
    """
    Проверяет готовность бота к запуску.

    Удаляет webhook если он установлен и проверяет доступность API.

    Returns:
        True если бот готов к запуску
    """
    try:
        # Проверяем статус бота
        resp = requests.get(f"{API_URL}/getMe", timeout=10)
        if resp.status_code != 200:
            logger.error(f"❌ Не удалось получить информацию о боте: {resp.status_code}")
            return False

        data = resp.json()
        if not data.get("ok"):
            logger.error(f"❌ API вернул ошибку: {data}")
            return False

        bot_info = data.get("result", {})
        logger.info(f"✅ Бот активен: @{bot_info.get('username', 'unknown')}")

        # Проверяем webhook
        resp = requests.get(f"{API_URL}/getWebhookInfo", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                webhook_info = data.get("result", {})
                webhook_url = webhook_info.get("url", "")

                if webhook_url:
                    logger.warning(f"⚠️ Обнаружен webhook: {webhook_url}")
                    logger.info("Удаление webhook для использования polling...")
                    if not delete_webhook():
                        logger.error("❌ Не удалось удалить webhook")
                        return False
                else:
                    logger.info("✅ Webhook не установлен")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке готовности бота: {e}")
        return False


def run_polling_loop() -> None:
    """Main polling loop."""
    logger.info("Starting Telegram polling loop...")
    logger.info(f"Bot token: {BOT_TOKEN[:10]}...")
    logger.info(f"API base: {CONFIG.api_base_url}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")

    # Проверяем готовность бота перед запуском
    logger.info("\n" + "=" * 60)
    logger.info("Проверка готовности бота...")
    logger.info("=" * 60)
    if not verify_bot_ready():
        logger.error("\n❌ Бот не готов к запуску. Исправьте ошибки и попробуйте снова.")
        return
    logger.info("=" * 60 + "\n")

    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
                elif "callback_query" in update:
                    handle_callback_query(update["callback_query"])
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Telegram polling stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in polling loop: {e}")
            time.sleep(POLL_INTERVAL)


def main() -> None:
    try:
        run_polling_loop()
    except Exception as e:
        logger.error(f"Fatal error in Telegram polling: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
