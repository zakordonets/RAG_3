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


def handle_callback_query(callback_query: dict) -> None:
    """Process callback buttons (used for feedback)."""
    try:
        callback_data = callback_query.get("data", "")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")

        if not callback_data or not chat_id:
            return

        if callback_data.startswith("feedback_"):
            feedback_type = "positive" if "positive" in callback_data else "negative"
            interaction_id = callback_data.split("_")[-1]

            try:
                requests.post(
                    f"{CONFIG.api_base_url}/v1/quality/feedback",
                    json={
                        "interaction_id": interaction_id,
                        "feedback": feedback_type,
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
        logger.error(f"Failed to get updates: {resp.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return []


def run_polling_loop() -> None:
    """Main polling loop."""
    logger.info("Starting Telegram polling loop...")
    logger.info(f"Bot token: {BOT_TOKEN[:10]}...")
    logger.info(f"API base: {CONFIG.api_base_url}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")

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
