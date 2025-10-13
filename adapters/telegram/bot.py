"""
Основной Telegram бот с rate limiting и форматированием.
"""

from __future__ import annotations

import time
import requests
from typing import Dict, Any, Optional
from loguru import logger
from app.config import CONFIG
from .rate_limiter import RateLimiter
from app.infrastructure import get_metrics_collector
from adapters.telegram_adapter import render_html, split_for_telegram, send as send_html


def create_feedback_keyboard(interaction_id: str) -> dict:
    """Build inline keyboard with feedback buttons."""
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


class TelegramBot:
    """
    Основной Telegram бот с rate limiting и форматированием.

    Deprecated: prefer ``adapters.telegram.polling`` for production deployments.
    """

    def __init__(
        self,
        bot_token: str,
        api_base: str = "http://localhost:9000",
        poll_interval: float = 1.0,
        timeout: int = 120
    ):
        """
        Инициализация Telegram бота.

        Args:
            bot_token: Токен бота
            api_base: Базовый URL API
            poll_interval: Интервал опроса в секундах
            timeout: Таймаут запросов в секундах
        """
        self.bot_token = bot_token
        self.api_base = api_base
        self.poll_interval = poll_interval
        self.timeout = timeout

        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.offset = None

        # Инициализируем rate limiter
        self.rate_limiter = RateLimiter(
            max_requests=CONFIG.telegram_rate_limit_requests,
            window_seconds=CONFIG.telegram_rate_limit_window,
            burst_limit=CONFIG.telegram_rate_limit_burst,
            burst_window=CONFIG.telegram_rate_limit_burst_window
        )

        # Инициализируем метрики
        self.metrics = get_metrics_collector()

        logger.info(f"Telegram bot initialized: {bot_token[:10]}...")
        logger.info(f"API base: {api_base}")
        logger.info(f"Poll interval: {poll_interval}s")
        logger.info(f"Timeout: {timeout}s")

    def send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """
        Отправляет сообщение в Telegram.

        Args:
            chat_id: ID чата
            text: Текст сообщения
            reply_markup: Объект клавиатуры

        Returns:
            True если сообщение отправлено успешно
        """
        try:
            # Проверяем rate limit
            if not self.rate_limiter.is_allowed(chat_id):
                logger.warning(f"Rate limit exceeded for user {chat_id}")
                return False

            html_text = render_html(text or "", [])
            parts = split_for_telegram(html_text)
            send_html(chat_id, parts, reply_markup=reply_markup)
            self.metrics.increment_counter("telegram_messages_sent_total")
            logger.debug(f"Message sent to {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return False

    def send_rich_answer(self, chat_id: str, answer: Dict[str, Any]) -> bool:
        """
        Отправляет структурированный ответ с источниками.

        Args:
            chat_id: ID чата
            answer: Словарь с ответом и метаданными

        Returns:
            True если сообщение отправлено успешно
        """
        try:
            answer_markdown = answer.get("answer_markdown") or answer.get("answer") or ""
            sources = answer.get("sources", []) or []
            reply_markup = answer.get("reply_markup")
            interaction_id = answer.get("interaction_id") or ""

            html_text = render_html(answer_markdown, sources)
            parts = split_for_telegram(html_text)

            if interaction_id and not reply_markup:
                reply_markup = create_feedback_keyboard(str(interaction_id))

            send_html(chat_id, parts, reply_markup=reply_markup)
            self.metrics.increment_counter("telegram_messages_sent_total")
            logger.debug(f"Rich answer sent to {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending rich answer to {chat_id}: {e}")
            return False

    def get_updates(self) -> list:
        """
        Получает обновления от Telegram API.

        Returns:
            Список обновлений
        """
        try:
            params = {
                "timeout": self.timeout,
                "offset": self.offset
            }

            response = requests.get(
                f"{self.api_url}/getUpdates",
                params=params,
                timeout=self.timeout + 10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates:
                        self.offset = updates[-1]["update_id"] + 1
                    return updates
                else:
                    logger.error(f"Telegram API error: {data}")
                    return []
            else:
                logger.error(f"Failed to get updates: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []

    def process_message(self, message: Dict[str, Any]) -> None:
        """
        Обрабатывает входящее сообщение.

        Args:
            message: Сообщение от Telegram
        """
        try:
            chat_id = str(message["chat"]["id"])
            text = message.get("text", "").strip()

            if not text:
                return

            # Проверяем rate limit
            if not self.rate_limiter.is_allowed(chat_id):
                self.send_message(chat_id, "⚠️ Слишком много запросов. Подождите немного.")
                return

            # Отправляем запрос в RAG API
            response = requests.post(
                f"{self.api_base}/v1/chat/query",
                json={
                    "message": text,
                    "channel": "telegram",
                    "chat_id": chat_id
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                answer = response.json()
                self.send_rich_answer(chat_id, answer)
            else:
                logger.error(f"RAG API error: {response.status_code}")
                self.send_message(chat_id, "❌ Произошла ошибка при обработке запроса.")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run_polling(self) -> None:
        """
        Запускает polling цикл.
        """
        logger.info("Starting Telegram bot polling...")

        while True:
            try:
                updates = self.get_updates()

                for update in updates:
                    if "message" in update:
                        self.process_message(update["message"])
                    elif "callback_query" in update:
                        # Обработка callback query (feedback кнопки)
                        self.handle_callback_query(update["callback_query"])

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Telegram bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                time.sleep(self.poll_interval)

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """
        Обрабатывает callback query от feedback кнопок.

        Args:
            callback_query: Callback query от Telegram
        """
        try:
            callback_data = callback_query.get("data", "")
            chat = callback_query.get("message", {}).get("chat", {})
            chat_id = chat.get("id")

            if not callback_data or chat_id is None:
                return

            if callback_data.startswith("feedback_"):
                # ���������� feedback � RAG API
                feedback_type = "positive" if callback_data.startswith("feedback_positive_") else "negative"
                interaction_id = extract_interaction_id(callback_data)
                if not interaction_id:
                    logger.warning(f"Callback without interaction_id: {callback_data!r}")
                    return

                requests.post(
                    f"{self.api_base}/v1/admin/quality/feedback",
                    json={
                        "interaction_id": interaction_id,
                        "feedback_type": feedback_type,
                        "chat_id": chat_id
                    },
                    timeout=self.timeout
                )

                # �������� �� callback query
                requests.post(
                    f"{self.api_url}/answerCallbackQuery",
                    json={
                        "callback_query_id": callback_query["id"],
                        "text": "Спасибо за обратную связь!"
                    },
                    timeout=self.timeout
                )

        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
