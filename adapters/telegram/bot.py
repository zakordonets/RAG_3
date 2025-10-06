"""
Основной Telegram бот с rate limiting и форматированием.
"""

from __future__ import annotations

import time
import requests
from typing import Dict, Any, Optional
from loguru import logger
import telegramify_markdown

from app.config import CONFIG
from .rate_limiter import RateLimiter
from app.infrastructure import get_metrics_collector


class TelegramBot:
    """
    Основной Telegram бот с rate limiting и форматированием.
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

    def send_message(self, chat_id: str, text: str, parse_mode: str = "MarkdownV2") -> bool:
        """
        Отправляет сообщение в Telegram.

        Args:
            chat_id: ID чата
            text: Текст сообщения
            parse_mode: Режим парсинга (MarkdownV2, HTML)

        Returns:
            True если сообщение отправлено успешно
        """
        try:
            # Проверяем rate limit
            if not self.rate_limiter.is_allowed(chat_id):
                logger.warning(f"Rate limit exceeded for user {chat_id}")
                return False

            # Форматируем текст для Telegram
            if parse_mode == "MarkdownV2":
                formatted_text = telegramify_markdown.convert(text)
            else:
                formatted_text = text

            # Отправляем сообщение
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": formatted_text,
                    "parse_mode": parse_mode
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                self.metrics.increment_counter("telegram_messages_sent_total")
                logger.debug(f"Message sent to {chat_id}")
                return True
            else:
                logger.error(f"Failed to send message to {chat_id}: {response.status_code} - {response.text}")
                return False

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
            # Формируем текст ответа
            text = answer.get("answer", "")
            sources = answer.get("sources", [])

            if sources:
                text += "\n\n**Источники:**\n"
                for i, source in enumerate(sources[:3], 1):  # Ограничиваем 3 источниками
                    url = source.get("url", "")
                    title = source.get("title", "Без названия")
                    text += f"{i}. [{title}]({url})\n"

            # Отправляем сообщение
            return self.send_message(chat_id, text)

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
                    "query": text,
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
            chat_id = callback_query["message"]["chat"]["id"]
            message_id = callback_query["message"]["message_id"]

            if callback_data.startswith("feedback_"):
                # Отправляем feedback в RAG API
                feedback_type = "positive" if "positive" in callback_data else "negative"
                interaction_id = callback_data.split("_")[-1]

                requests.post(
                    f"{self.api_base}/v1/quality/feedback",
                    json={
                        "interaction_id": interaction_id,
                        "feedback": feedback_type,
                        "chat_id": chat_id
                    },
                    timeout=self.timeout
                )

                # Отвечаем на callback query
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
