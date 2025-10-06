from __future__ import annotations

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import requests
import json
import asyncio
from loguru import logger
from app.config import CONFIG
from app.log_utils import write_debug_event
from app.services.quality.quality_manager import quality_manager


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
            # Извлекаем тип feedback и interaction_id
            # Формат: feedback_<positive|negative>_<interaction_id>
            parts = callback_data.split("_", 2)
            if len(parts) == 3:
                feedback_type = parts[1]  # positive или negative
                interaction_id = parts[2]

                # Сохраняем feedback синхронно, так как мы в sync-коде
                asyncio.run(save_user_feedback(interaction_id, feedback_type))

                # Отправляем подтверждение пользователю
                if feedback_type == "positive":
                    response_text = "✅ Спасибо за положительную оценку!"
                else:
                    response_text = "✅ Спасибо за обратную связь! Мы учтем ваше мнение."

                # Отправляем ответ на callback query
                requests.post(f"{API_URL}/answerCallbackQuery",
                            json={
                                "callback_query_id": callback_query["id"],
                                "text": response_text,
                                "show_alert": False
                            },
                            timeout=10)

                # Удаляем кнопки после использования
                requests.post(f"{API_URL}/editMessageReplyMarkup",
                            json={
                                "chat_id": chat_id,
                                "message_id": message_id,
                                "reply_markup": {"inline_keyboard": []}
                            },
                            timeout=10)

                logger.info(f"Processed feedback: {feedback_type} for interaction {interaction_id}")
    except Exception as e:
        logger.error(f"Error handling callback query: {type(e).__name__}: {e}. data={callback_query}")


async def save_user_feedback(interaction_id: str, feedback_type: str) -> None:
    """Асинхронно сохраняет пользовательский feedback"""
    try:
        await quality_manager.add_user_feedback(
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            feedback_text=f"User {feedback_type} feedback via Telegram"
        )
        logger.info(f"Saved user feedback: {feedback_type} for {interaction_id}")
    except Exception as e:
        logger.error(f"Failed to save user feedback: {e}")


def run_polling_loop(api_base: str = "http://localhost:9000") -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    logger.info(f"Bot token: {BOT_TOKEN[:10]}...")
    logger.info(f"API base: {api_base}")
    logger.info(f"Polling interval: {POLL_INTERVAL}s")

    offset = None
    while True:
        try:
            resp = requests.get(f"{API_URL}/getUpdates", params={"timeout": 25, "offset": offset}, timeout=30)
            resp.raise_for_status()
            updates = resp.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1

                # Обработка callback queries (feedback кнопки)
                if "callback_query" in upd:
                    handle_callback_query(upd["callback_query"])
                    continue

                # Обработка обычных сообщений
                message = upd.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                text = message.get("text") or ""
                if not text or chat_id is None:
                    continue
                # Проксируем в Core API
                logger.info(f"Processing message from chat {chat_id}: {text[:50]}...")
                try:
                    logger.info(f"Making request to {api_base}/v1/chat/query")
                    r = requests.post(
                        f"{api_base}/v1/chat/query",
                        json={"channel": "telegram", "chat_id": str(chat_id), "message": text},
                        timeout=120,  # Увеличиваем timeout до 2 минут
                    )
                    logger.info(f"Core API response status: {r.status_code}")
                    r.raise_for_status()

                    response_data = r.json()
                    logger.info(f"Core API response keys: {list(response_data.keys())}")

                    ans = response_data.get("answer")
                    interaction_id = response_data.get("interaction_id")  # Получаем interaction_id от API

                    if ans:
                        logger.info(f"Answer length: {len(ans)} chars")
                        logger.info(f"Answer preview: {ans[:100]}...")
                        logger.info(f"Interaction ID: {interaction_id}")

                        # Отправляем с поддержкой MarkdownV2 (telegramify_markdown уже экранирует спецсимволы)
                        logger.info(f"Sending reply to chat {chat_id}")
                        # Диагностика: логируем перед отправкой
                        write_debug_event("telegram.send_attempt", {"chat_id": str(chat_id), "len": len(ans), "preview": ans[:500], "interaction_id": interaction_id})

                        # Подготавливаем данные для отправки
                        message_data = {
                            "chat_id": chat_id,
                            "text": ans,
                            "parse_mode": "MarkdownV2",
                            "disable_web_page_preview": True
                        }

                        # Добавляем feedback кнопки если есть interaction_id
                        if interaction_id:
                            message_data["reply_markup"] = create_feedback_keyboard(interaction_id)
                            logger.info(f"Added feedback buttons for interaction {interaction_id}")

                        send_response = requests.post(f"{API_URL}/sendMessage",
                                    json=message_data,
                                    timeout=15)
                        logger.info(f"Telegram send response: {send_response.status_code}")
                        if send_response.status_code != 200:
                            logger.error(f"Telegram MarkdownV2 error: {send_response.text}")
                            write_debug_event("telegram.send_error", {"status": send_response.status_code, "body": send_response.text})
                            # Fallback: отправляем без форматирования
                            logger.info(f"Trying fallback without formatting...")
                            fallback_data = {
                                "chat_id": chat_id,
                                "text": ans
                            }
                            # Добавляем feedback кнопки в fallback тоже
                            if interaction_id:
                                fallback_data["reply_markup"] = create_feedback_keyboard(interaction_id)

                            fallback_response = requests.post(f"{API_URL}/sendMessage",
                                        json=fallback_data,
                                        timeout=15)
                            logger.info(f"Telegram fallback response: {fallback_response.status_code}")
                            if fallback_response.status_code != 200:
                                logger.error(f"Telegram fallback error: {fallback_response.text}")
                                write_debug_event("telegram.fallback_error", {"status": fallback_response.status_code, "body": fallback_response.text})
                    else:
                        logger.warning(f"No answer received for chat {chat_id}")
                except requests.exceptions.Timeout as e:
                    logger.error(f"Timeout error for chat {chat_id}: {e}")
                    # Отправляем сообщение о таймауте
                    try:
                        requests.post(f"{API_URL}/sendMessage",
                                    json={"chat_id": chat_id, "text": "⏰ Обработка запроса занимает больше времени, чем ожидалось. Попробуйте позже."},
                                    timeout=15)
                    except:
                        pass
                except Exception as e:
                    logger.error(f"Failed to process message for chat {chat_id}: {type(e).__name__}: {e}")
                    # Отправляем сообщение об ошибке пользователю
                    try:
                        requests.post(f"{API_URL}/sendMessage",
                                    json={"chat_id": chat_id, "text": "❌ Извините, произошла ошибка при обработке вашего сообщения. Попробуйте позже."},
                                    timeout=15)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(POLL_INTERVAL)
            continue


if __name__ == "__main__":
    try:
        logger.info("Starting Telegram bot polling...")
        run_polling_loop()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
