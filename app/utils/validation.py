"""
Модуль валидации входных данных для RAG системы.
"""
from __future__ import annotations

import html
import re
from typing import Any
from marshmallow import Schema, fields, validate, ValidationError
from loguru import logger


class SecurityConfig:
    """Конфигурация безопасности."""
    MAX_MESSAGE_LENGTH = 2000
    ALLOWED_CHANNELS = ["telegram", "web", "api"]
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW = 300  # 5 минут

    # Список запрещенных паттернов
    BLOCKED_PATTERNS = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'data:text/html',
        r'vbscript:',
        r'<iframe.*?>.*?</iframe>',
        r'<object.*?>.*?</object>',
        r'<embed.*?>',
        r'<link.*?>',
        r'<meta.*?>',
    ]


class QuerySchema(Schema):
    """Схема валидации для запросов чата."""
    message = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=SecurityConfig.MAX_MESSAGE_LENGTH),
            validate.Regexp(r'^[^<>]*$', error="Message contains invalid characters")
        ],
        error_messages={
            'required': 'Message is required',
            'invalid': 'Invalid message format'
        }
    )
    channel = fields.Str(
        missing="telegram",
        validate=validate.OneOf(SecurityConfig.ALLOWED_CHANNELS),
        error_messages={
            'validator_failed': f'Channel must be one of: {", ".join(SecurityConfig.ALLOWED_CHANNELS)}'
        }
    )
    chat_id = fields.Raw(
        missing="",
        error_messages={
            'invalid': 'Invalid chat_id format'
        }
    )


class AdminReindexSchema(Schema):
    """Схема валидации для админских операций."""
    incremental = fields.Bool(missing=True)
    force = fields.Bool(missing=False)


def sanitize_input(text: str) -> str:
    """
    Санитизация пользовательского ввода.

    Args:
        text: Исходный текст

    Returns:
        Очищенный текст
    """
    if not text:
        return ""

    # HTML экранирование
    text = html.escape(text)

    # Удаление потенциально опасных паттернов
    for pattern in SecurityConfig.BLOCKED_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

    # Ограничение длины
    if len(text) > SecurityConfig.MAX_MESSAGE_LENGTH:
        text = text[:SecurityConfig.MAX_MESSAGE_LENGTH]
        logger.warning(f"Message truncated to {SecurityConfig.MAX_MESSAGE_LENGTH} characters")

    # Удаление лишних пробелов
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def validate_query_data(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Валидация данных запроса.

    Args:
        data: Словарь с данными запроса

    Returns:
        Tuple (validated_data, errors)
    """
    try:
        # Валидация схемы
        validated = QuerySchema().load(data)

        # Дополнительная санитизация
        validated["message"] = sanitize_input(validated["message"])

        # Проверка на пустое сообщение после санитизации
        if not validated["message"]:
            return {}, ["Message cannot be empty after sanitization"]

        return validated, []

    except ValidationError as e:
        logger.warning(f"Validation error: {e.messages}")
        return {}, list(e.messages.values())[0] if e.messages else ["Validation failed"]


def validate_admin_data(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Валидация данных админских операций.

    Args:
        data: Словарь с данными админской операции

    Returns:
        Tuple (validated_data, errors)
    """
    try:
        validated = AdminReindexSchema().load(data)
        return validated, []
    except ValidationError as e:
        logger.warning(f"Admin validation error: {e.messages}")
        return {}, list(e.messages.values())[0] if e.messages else ["Validation failed"]


def is_safe_text(text: str) -> bool:
    """
    Проверка безопасности текста.

    Args:
        text: Текст для проверки

    Returns:
        True если текст безопасен
    """
    if not text:
        return True

    # Проверка на опасные паттерны
    for pattern in SecurityConfig.BLOCKED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            logger.warning(f"Unsafe pattern detected: {pattern}")
            return False

    return True


def validate_telegram_message(message: str) -> tuple[str, bool]:
    """
    Валидация сообщения от Telegram.

    Args:
        message: Сообщение от пользователя

    Returns:
        Tuple (sanitized_message, is_valid)
    """
    if not message:
        return "", False

    # Базовая проверка длины
    if len(message) > SecurityConfig.MAX_MESSAGE_LENGTH:
        logger.warning(f"Message too long: {len(message)} characters")
        return "", False

    # Санитизация
    sanitized = sanitize_input(message)

    # Проверка на пустоту после санитизации
    if not sanitized:
        return "", False

    return sanitized, True
