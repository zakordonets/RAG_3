"""
Telegram polling адаптер для RAG-системы.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
import requests
import json
import asyncio
from loguru import logger
from app.config import CONFIG
from app.utils import write_debug_event
from app.services.quality.quality_manager import quality_manager
# from .bot import TelegramBot  # Не используется в этом файле


BOT_TOKEN = CONFIG.telegram_bot_token
POLL_INTERVAL = CONFIG.telegram_poll_interval
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def create_feedback_keyboard(interaction_id: str) -> dict:
    """Создает клавиатуру с кнопками feedback"""
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "👍",
                    "callback_data": f"feedback_positive_{interaction_id}"
                },
                {
                    "text": "👎",
                    "callback_data": f"feedback_negative_{interaction_id}"
                }
            ]
        ]
    }
    return keyboard


def handle_callback_query(callback_query: dict) -> None:
    """Обрабатывает callback query от feedback кнопок"""
    try:
        callback_data = callback_query.get("data", "")
        chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]

        if callback_data.startswith("feedback_"):
            # Отправляем feedback в RAG API
            feedback_type = "positive" if "positive" in callback_data else "negative"
            interaction_id = callback_data.split("_")[-1]

            try:
                response = requests.post(
                    f"{CONFIG.api_base_url}/v1/quality/feedback",
                    json={
                        "interaction_id": interaction_id,
                        "feedback": feedback_type,
                        "chat_id": chat_id
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    logger.info(f"Feedback recorded: {feedback_type} for interaction {interaction_id}")
                else:
                    logger.error(f"Failed to record feedback: {response.status_code}")

            except Exception as e:
                logger.error(f"Error recording feedback: {e}")

            # Отвечаем на callback query
            try:
                requests.post(
                    f"{API_URL}/answerCallbackQuery",
                    json={
                        "callback_query_id": callback_query["id"],
                        "text": "Спасибо за обратную связь!"
                    },
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Error answering callback query: {e}")

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")


def handle_message(message: dict) -> None:
    """Обрабатывает входящее сообщение"""
    try:
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        if not text:
            return

        # Логируем входящее сообщение
        write_debug_event("telegram_message_received", {
            "chat_id": chat_id,
            "text_length": len(text),
            "timestamp": time.time()
        })

        # Отправляем запрос в RAG API
        try:
            response = requests.post(
                f"{CONFIG.api_base_url}/v1/chat/query",
                json={
                    "message": text,
                    "channel": "telegram",
                    "chat_id": chat_id
                },
                timeout=120
            )

            if response.status_code == 200:
                answer_data = response.json()

                # Отправляем ответ
                send_telegram_message(chat_id, answer_data)

                # Логируем ответ
                write_debug_event("telegram_message_sent", {
                    "chat_id": chat_id,
                    "answer_length": len(answer_data.get("answer", "")),
                    "sources_count": len(answer_data.get("sources", [])),
                    "timestamp": time.time()
                })

            else:
                logger.error(f"RAG API error: {response.status_code} - {response.text}")
                send_telegram_message(chat_id, {
                    "answer": "❌ Произошла ошибка при обработке запроса. Попробуйте позже.",
                    "sources": []
                })

        except Exception as e:
            logger.error(f"Error calling RAG API: {e}")
            send_telegram_message(chat_id, {
                "answer": "❌ Произошла ошибка при обработке запроса. Попробуйте позже.",
                "sources": []
            })

    except Exception as e:
        logger.error(f"Error handling message: {e}")


def send_telegram_message(chat_id, answer_data: dict) -> None:
    """Отправляет сообщение в Telegram"""
    try:
        answer = answer_data.get("answer", "")
        sources = answer_data.get("sources", [])
        interaction_id = answer_data.get("interaction_id", "")

        # Формируем текст ответа
        message_text = answer

        # Добавляем источники
        if sources:
            message_text += "\n\n**Источники:**\n"
            for i, source in enumerate(sources[:3], 1):  # Ограничиваем 3 источниками
                url = source.get("url", "")
                title = source.get("title", "Без названия")
                message_text += f"{i}. [{title}]({url})\n"

        # Создаем клавиатуру с feedback кнопками
        keyboard = None
        if interaction_id:
            keyboard = create_feedback_keyboard(interaction_id)

        # Отправляем сообщение
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "MarkdownV2"
        }

        if keyboard:
            payload["reply_markup"] = json.dumps(keyboard)

        response = requests.post(
            f"{API_URL}/sendMessage",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            logger.debug(f"Message sent to chat {chat_id}")
        else:
            logger.error(f"Failed to send message to chat {chat_id}: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")


def get_updates(offset: int = None) -> list:
    """Получает обновления от Telegram API"""
    try:
        params = {
            "timeout": 30,
            "offset": offset
        }

        response = requests.get(
            f"{API_URL}/getUpdates",
            params=params,
            timeout=40
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return data.get("result", [])
            else:
                logger.error(f"Telegram API error: {data}")
                return []
        else:
            logger.error(f"Failed to get updates: {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return []


def run_polling_loop() -> None:
    """Запускает основной polling цикл"""
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


def main():
    """Главная функция для запуска из командной строки"""
    try:
        run_polling_loop()
    except Exception as e:
        logger.error(f"Fatal error in Telegram polling: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
