"""
Улучшенный Telegram адаптер с rate limiting и форматированием.
"""
from __future__ import annotations

import time
import requests
from typing import Dict, Any, Optional
from loguru import logger
import telegramify_markdown

from app.config import CONFIG
from adapters.rate_limiter import rate_limiter
from app.metrics import metrics_collector


class TelegramBot:
    """
    Улучшенный Telegram бот с rate limiting и форматированием.
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

        logger.info(f"Telegram bot initialized: {bot_token[:10]}...")
        logger.info(f"API base: {api_base}")
        logger.info(f"Poll interval: {poll_interval}s")
        logger.info(f"Timeout: {timeout}s")

    def _send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "MarkdownV2",
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Отправляет сообщение в Telegram.

        Args:
            chat_id: ID чата
            text: Текст сообщения
            parse_mode: Режим парсинга
            reply_to_message_id: ID сообщения для ответа

        Returns:
            True если сообщение отправлено успешно
        """
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
            }
            # Передаём parse_mode только если он задан (Telegram не принимает null)
            if parse_mode:
                payload["parse_mode"] = parse_mode

            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=15
            )

            if response.status_code == 200:
                logger.debug(f"Message sent to chat {chat_id}")
                return True
            else:
                logger.error(f"Failed to send message: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending message to chat {chat_id}: {e}")
            return False

    def _send_message_with_fallback(
        self,
        chat_id: str,
        text: str,
        reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Отправляет сообщение с fallback на простой текст.

        Args:
            chat_id: ID чата
            text: Текст сообщения
            reply_to_message_id: ID сообщения для ответа

        Returns:
            True если сообщение отправлено успешно
        """
        # Пробуем отправить с MarkdownV2
        if self._send_message(chat_id, text, "MarkdownV2", reply_to_message_id):
            return True

        # Fallback: отправляем без форматирования
        logger.warning(f"MarkdownV2 failed for chat {chat_id}, trying plain text")
        return self._send_message(chat_id, text, None, reply_to_message_id)

    def _format_response(self, response: Dict[str, Any]) -> str:
        """
        Форматирует ответ для Telegram.

        Args:
            response: Ответ от RAG системы

        Returns:
            Отформатированный текст
        """
        answer = response.get("answer", "")
        sources = response.get("sources", [])

        if not answer:
            return "Извините, не удалось сформировать ответ."

        # Форматируем ответ с помощью telegramify-markdown
        try:
            formatted_answer = telegramify_markdown.markdownify(answer)
        except Exception as e:
            logger.warning(f"Markdown formatting failed: {e}")
            # Fallback к простому форматированию
            formatted_answer = self._simple_format(answer)

        # Добавляем источники
        if sources:
            sources_text = self._format_sources(sources)
            formatted_answer += f"\n\n{sources_text}"

        return formatted_answer

    def _simple_format(self, text: str) -> str:
        """
        Простое форматирование без MarkdownV2.

        Args:
            text: Исходный текст

        Returns:
            Отформатированный текст
        """
        # Заменяем markdown на простой текст
        text = text.replace("**", "*")  # Жирный текст
        text = text.replace("### ", "🔹 ")  # Заголовки
        text = text.replace("## ", "🔸 ")  # Заголовки
        text = text.replace("# ", "🔸 ")  # Заголовки
        text = text.replace("`", "")  # Убираем код
        return text

    def _format_sources(self, sources: list[Dict[str, Any]]) -> str:
        """
        Форматирует источники для Telegram.

        Args:
            sources: Список источников

        Returns:
            Отформатированный текст источников
        """
        if not sources:
            return ""

        sources_text = "📚 *Источники:*\n"
        for i, source in enumerate(sources[:3], 1):  # Ограничиваем 3 источниками
            title = source.get("title", "Документация")
            url = source.get("url", "")

            if url:
                # Экранируем специальные символы для MarkdownV2
                title_escaped = title.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")
                sources_text += f"{i}\\. [{title_escaped}]({url})\n"

        return sources_text

    def _process_message(self, message: Dict[str, Any]) -> None:
        """
        Обрабатывает сообщение от пользователя.

        Args:
            message: Сообщение от Telegram
        """
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "").strip()
        message_id = message.get("message_id")

        if not text or not chat_id:
            logger.warning("Empty message or chat_id")
            return

        # Проверяем rate limiting
        if not rate_limiter.is_allowed(chat_id):
            logger.warning(f"Rate limit exceeded for user {chat_id}")
            self._send_message_with_fallback(
                chat_id,
                "⏰ Слишком много запросов. Попробуйте позже.",
                message_id
            )
            return

        # Отправляем сообщение о начале обработки
        self._send_message_with_fallback(
            chat_id,
            "🤔 Обрабатываю ваш запрос...",
            message_id
        )

        # Обрабатываем запрос через RAG систему
        try:
            logger.info(f"Processing message from chat {chat_id}: {text[:50]}...")

            # Отправляем запрос в Core API
            response = requests.post(
                f"{self.api_base}/v1/chat/query",
                json={
                    "channel": "telegram",
                    "chat_id": chat_id,
                    "message": text
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()

                # Проверяем на ошибки
                if "error" in data:
                    error_message = data.get("message", "Произошла ошибка")
                    self._send_message_with_fallback(
                        chat_id,
                        f"❌ {error_message}",
                        message_id
                    )
                    return

                # Форматируем и отправляем ответ
                formatted_response = self._format_response(data)
                self._send_message_with_fallback(
                    chat_id,
                    formatted_response,
                    message_id
                )

                # Записываем метрики
                metrics_collector.record_query("telegram", "success")

            else:
                logger.error(f"Core API error: {response.status_code} - {response.text}")
                self._send_message_with_fallback(
                    chat_id,
                    "❌ Ошибка сервера. Попробуйте позже.",
                    message_id
                )
                metrics_collector.record_query("telegram", "error", "api_error")

        except requests.exceptions.Timeout:
            logger.error(f"Timeout processing message for chat {chat_id}")
            self._send_message_with_fallback(
                chat_id,
                "⏰ Обработка запроса занимает больше времени, чем ожидалось. Попробуйте позже.",
                message_id
            )
            metrics_collector.record_query("telegram", "error", "timeout")

        except Exception as e:
            logger.error(f"Error processing message for chat {chat_id}: {e}")
            self._send_message_with_fallback(
                chat_id,
                "❌ Произошла ошибка при обработке вашего сообщения. Попробуйте позже.",
                message_id
            )
            metrics_collector.record_query("telegram", "error", "processing_error")

    def _get_updates(self) -> list[Dict[str, Any]]:
        """
        Получает обновления от Telegram API.

        Returns:
            Список обновлений
        """
        try:
            params = {
                "timeout": 25,
                "offset": self.offset
            }

            response = requests.get(
                f"{self.api_url}/getUpdates",
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("result", [])
            else:
                logger.error(f"Failed to get updates: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []

    def run_polling(self) -> None:
        """
        Запускает long polling для получения сообщений.
        """
        logger.info("Starting Telegram bot polling...")

        while True:
            try:
                updates = self._get_updates()

                for update in updates:
                    self.offset = update["update_id"] + 1
                    message = update.get("message")

                    if message:
                        self._process_message(message)

                # Небольшая пауза между опросами
                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(self.poll_interval)


def run_enhanced_polling_loop(api_base: str = "http://localhost:9000") -> None:
    """
    Запускает улучшенный polling loop.

    Args:
        api_base: Базовый URL API
    """
    if not CONFIG.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    bot = TelegramBot(
        bot_token=CONFIG.telegram_bot_token,
        api_base=api_base,
        poll_interval=CONFIG.telegram_poll_interval,
        timeout=120
    )

    try:
        bot.run_polling()
    except Exception as e:
        logger.error(f"Failed to start enhanced bot: {e}")
        raise


if __name__ == "__main__":
    try:
        logger.info("Starting enhanced Telegram bot...")
        run_enhanced_polling_loop()
    except Exception as e:
        logger.error(f"Failed to start enhanced bot: {e}")
        import traceback
        traceback.print_exc()
