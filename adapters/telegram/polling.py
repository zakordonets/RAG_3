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
import json
import requests
from loguru import logger
import telegramify_markdown

from app.config import CONFIG
from app.utils import write_debug_event


BOT_TOKEN = CONFIG.telegram_bot_token
POLL_INTERVAL = CONFIG.telegram_poll_interval
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2.
    Escapes: _ * [ ] ( ) ~ ` > # + - = | { } . ! and backslash.
    """
    if not text:
        return ""
    # Escape backslash first
    text = text.replace("\\", "\\\\")
    # Escape special characters
    specials = r"_ * [ ] ( ) ~ ` > # + - = | { } . !".split()
    for ch in specials:
        text = text.replace(ch, f"\\{ch}")
    return text


def _to_markdown_v2(text: str) -> str:
    """Convert/escape text to Telegram-safe MarkdownV2.
    Tries telegramify_markdown (markdownify/convert) then falls back to escaping.
    """
    try:
        fn = getattr(telegramify_markdown, "markdownify", None)
        if callable(fn):
            out = fn(text)
            if out:
                return out
        fn2 = getattr(telegramify_markdown, "convert", None)
        if callable(fn2):
            out = fn2(text)
            if out:
                return out
    except Exception as e:
        logger.warning(f"telegramify_markdown failed: {type(e).__name__}: {e}")
    return _escape_markdown_v2(text)


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
    """Send a formatted message to Telegram using MarkdownV2 (safely escaped)."""
    try:
        answer = answer_data.get("answer", "") or ""
        sources = answer_data.get("sources", []) or []
        interaction_id = answer_data.get("interaction_id", "") or ""

        # Build readable Markdown message, then convert to safe MarkdownV2
        message_text = answer

        if sources:
            message_text += "\n\n**Источники:**\n"
            for i, source in enumerate(sources[:3], 1):
                url = source.get("url", "")
                title = source.get("title", "Источник")
                message_text += f"{i}. [{title}]({url})\n"

        # Escape/convert to Telegram MarkdownV2
        safe_text = _to_markdown_v2(message_text)

        payload: dict = {
            "chat_id": chat_id,
            "text": safe_text,
            "parse_mode": "MarkdownV2",
        }

        if interaction_id:
            payload["reply_markup"] = json.dumps(create_feedback_keyboard(interaction_id))

        resp = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=30)
        if resp.status_code != 200:
            logger.error(
                f"Failed to send message to chat {chat_id}: {resp.status_code} - {resp.text}"
            )
        else:
            logger.debug(f"Message sent to chat {chat_id}")

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
