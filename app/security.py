"""
Модуль безопасности для RAG системы.
"""
from __future__ import annotations

import re
import html
import hashlib
import time
from typing import List, Dict, Any, Optional
from loguru import logger
from app.config import CONFIG


class SecurityConfig:
    """Конфигурация безопасности."""

    # Ограничения на входные данные
    MAX_MESSAGE_LENGTH = 2000
    MAX_QUERY_LENGTH = 1000
    MAX_SOURCES_COUNT = 10

    # Разрешенные каналы
    ALLOWED_CHANNELS = ["telegram", "web", "api"]

    # Rate limiting
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW = 300  # 5 минут
    BURST_LIMIT = 3
    BURST_WINDOW = 60  # 1 минута

    # Запрещенные паттерны
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
        r'<style.*?>.*?</style>',
        r'<form.*?>.*?</form>',
        r'<input.*?>',
        r'<textarea.*?>.*?</textarea>',
        r'<select.*?>.*?</select>',
        r'<button.*?>.*?</button>',
        r'<a\s+href\s*=\s*["\']javascript:',
        r'<a\s+href\s*=\s*["\']data:',
        r'<a\s+href\s*=\s*["\']vbscript:',
    ]

    # Подозрительные паттерны
    SUSPICIOUS_PATTERNS = [
        r'<.*?>',  # HTML теги
        r'http[s]?://',  # URL
        r'ftp://',  # FTP URL
        r'file://',  # File URL
        r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',  # IP адреса
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Email адреса
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',  # Email адреса (другой вариант)
    ]

    # Список запрещенных слов/фраз
    BLOCKED_WORDS = [
        'admin', 'root', 'password', 'secret', 'token', 'key',
        'sql', 'injection', 'xss', 'csrf', 'exploit', 'hack',
        'malware', 'virus', 'trojan', 'backdoor', 'payload'
    ]


class SecurityValidator:
    """Валидатор безопасности для входных данных."""

    def __init__(self):
        self.blocked_patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in SecurityConfig.BLOCKED_PATTERNS]
        self.suspicious_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in SecurityConfig.SUSPICIOUS_PATTERNS]
        self.blocked_words = [word.lower() for word in SecurityConfig.BLOCKED_WORDS]

    def validate_message(self, message: str) -> Dict[str, Any]:
        """
        Валидирует сообщение пользователя.

        Args:
            message: Сообщение для валидации

        Returns:
            Словарь с результатами валидации
        """
        result = {
            "is_valid": True,
            "sanitized_message": message,
            "warnings": [],
            "errors": [],
            "risk_score": 0
        }

        if not message or not message.strip():
            result["is_valid"] = False
            result["errors"].append("Empty message")
            return result

        # Проверка длины
        if len(message) > SecurityConfig.MAX_MESSAGE_LENGTH:
            result["is_valid"] = False
            result["errors"].append(f"Message too long: {len(message)} > {SecurityConfig.MAX_MESSAGE_LENGTH}")
            return result

        # Проверка запрещенных паттернов
        for pattern in self.blocked_patterns:
            if pattern.search(message):
                result["is_valid"] = False
                result["errors"].append(f"Blocked pattern detected: {pattern.pattern}")
                result["risk_score"] += 10
                break

        # Проверка подозрительных паттернов
        for pattern in self.suspicious_patterns:
            if pattern.search(message):
                result["warnings"].append(f"Suspicious pattern detected: {pattern.pattern}")
                result["risk_score"] += 1

        # Проверка запрещенных слов
        message_lower = message.lower()
        for word in self.blocked_words:
            if word in message_lower:
                result["warnings"].append(f"Blocked word detected: {word}")
                result["risk_score"] += 2

        # Санитизация
        result["sanitized_message"] = self.sanitize_message(message)

        return result

    def sanitize_message(self, message: str) -> str:
        """
        Санитизирует сообщение пользователя.

        Args:
            message: Исходное сообщение

        Returns:
            Санитизированное сообщение
        """
        if not message:
            return ""

        # HTML экранирование
        sanitized = html.escape(message)

        # Удаление запрещенных паттернов
        for pattern in self.blocked_patterns:
            sanitized = pattern.sub('', sanitized)

        # Ограничение длины
        if len(sanitized) > SecurityConfig.MAX_MESSAGE_LENGTH:
            sanitized = sanitized[:SecurityConfig.MAX_MESSAGE_LENGTH]

        # Удаление лишних пробелов
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        return sanitized

    def validate_channel(self, channel: str) -> bool:
        """
        Валидирует канал связи.

        Args:
            channel: Канал для валидации

        Returns:
            True если канал разрешен
        """
        return channel in SecurityConfig.ALLOWED_CHANNELS

    def validate_chat_id(self, chat_id: str) -> bool:
        """
        Валидирует ID чата.

        Args:
            chat_id: ID чата для валидации

        Returns:
            True если ID чата валиден
        """
        if not chat_id:
            return True  # Пустой chat_id разрешен

        # Проверяем, что это число или строка с разумной длиной
        if len(chat_id) > 100:
            return False

        # Проверяем, что не содержит подозрительных символов
        if re.search(r'[<>"\']', chat_id):
            return False

        return True


class SecurityMonitor:
    """Монитор безопасности для отслеживания подозрительной активности."""

    def __init__(self):
        self.suspicious_activity: Dict[str, List[Dict[str, Any]]] = {}
        self.blocked_users: set[str] = set()
        self.alert_threshold = 5  # Количество подозрительных действий для алерта

    def log_activity(
        self,
        user_id: str,
        activity_type: str,
        details: Dict[str, Any],
        risk_score: int = 0
    ) -> None:
        """
        Логирует активность пользователя.

        Args:
            user_id: ID пользователя
            activity_type: Тип активности
            details: Детали активности
            risk_score: Оценка риска
        """
        if user_id not in self.suspicious_activity:
            self.suspicious_activity[user_id] = []

        activity = {
            "timestamp": time.time(),
            "type": activity_type,
            "details": details,
            "risk_score": risk_score
        }

        self.suspicious_activity[user_id].append(activity)

        # Очищаем старые записи (старше 1 часа)
        cutoff_time = time.time() - 3600
        self.suspicious_activity[user_id] = [
            a for a in self.suspicious_activity[user_id]
            if a["timestamp"] > cutoff_time
        ]

        # Проверяем на алерты
        if self._should_alert(user_id):
            self._send_alert(user_id)

    def _should_alert(self, user_id: str) -> bool:
        """Проверяет, нужно ли отправить алерт."""
        if user_id not in self.suspicious_activity:
            return False

        activities = self.suspicious_activity[user_id]
        recent_activities = [a for a in activities if time.time() - a["timestamp"] < 300]  # Последние 5 минут

        if len(recent_activities) >= self.alert_threshold:
            return True

        # Проверяем общий риск
        total_risk = sum(a["risk_score"] for a in recent_activities)
        if total_risk >= 20:
            return True

        return False

    def _send_alert(self, user_id: str) -> None:
        """Отправляет алерт о подозрительной активности."""
        logger.warning(f"Security alert: Suspicious activity detected for user {user_id}")

        # В реальной системе здесь можно отправить уведомление в Slack, email, etc.
        # Пока просто логируем

        activities = self.suspicious_activity.get(user_id, [])
        recent_activities = [a for a in activities if time.time() - a["timestamp"] < 300]

        logger.warning(f"Recent activities for user {user_id}: {len(recent_activities)}")
        for activity in recent_activities[-3:]:  # Последние 3 активности
            logger.warning(f"  - {activity['type']}: {activity['details']} (risk: {activity['risk_score']})")

    def block_user(self, user_id: str, reason: str) -> None:
        """
        Блокирует пользователя.

        Args:
            user_id: ID пользователя
            reason: Причина блокировки
        """
        self.blocked_users.add(user_id)
        logger.warning(f"User {user_id} blocked: {reason}")

    def is_user_blocked(self, user_id: str) -> bool:
        """
        Проверяет, заблокирован ли пользователь.

        Args:
            user_id: ID пользователя

        Returns:
            True если пользователь заблокирован
        """
        return user_id in self.blocked_users

    def get_user_risk_score(self, user_id: str) -> int:
        """
        Возвращает оценку риска пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Оценка риска
        """
        if user_id not in self.suspicious_activity:
            return 0

        activities = self.suspicious_activity[user_id]
        recent_activities = [a for a in activities if time.time() - a["timestamp"] < 3600]  # Последний час

        return sum(a["risk_score"] for a in recent_activities)

    def get_security_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику безопасности.

        Returns:
            Словарь со статистикой
        """
        total_users = len(self.suspicious_activity)
        blocked_users = len(self.blocked_users)

        high_risk_users = 0
        for user_id in self.suspicious_activity:
            if self.get_user_risk_score(user_id) > 10:
                high_risk_users += 1

        return {
            "total_users": total_users,
            "blocked_users": blocked_users,
            "high_risk_users": high_risk_users,
            "alert_threshold": self.alert_threshold
        }


# Глобальные экземпляры
security_validator = SecurityValidator()
security_monitor = SecurityMonitor()


def validate_request(user_id: str, message: str, channel: str, chat_id: str) -> Dict[str, Any]:
    """
    Валидирует запрос пользователя.

    Args:
        user_id: ID пользователя
        message: Сообщение
        channel: Канал связи
        chat_id: ID чата

    Returns:
        Словарь с результатами валидации
    """
    result = {
        "is_valid": True,
        "sanitized_message": message,
        "warnings": [],
        "errors": [],
        "risk_score": 0
    }

    # Проверяем, не заблокирован ли пользователь
    if security_monitor.is_user_blocked(user_id):
        result["is_valid"] = False
        result["errors"].append("User is blocked")
        return result

    # Валидируем канал
    if not security_validator.validate_channel(channel):
        result["is_valid"] = False
        result["errors"].append(f"Invalid channel: {channel}")
        return result

    # Валидируем chat_id
    if not security_validator.validate_chat_id(chat_id):
        result["is_valid"] = False
        result["errors"].append(f"Invalid chat_id: {chat_id}")
        return result

    # Валидируем сообщение
    message_validation = security_validator.validate_message(message)
    result.update(message_validation)

    # Логируем активность
    security_monitor.log_activity(
        user_id=user_id,
        activity_type="message_validation",
        details={
            "channel": channel,
            "chat_id": chat_id,
            "message_length": len(message),
            "warnings": message_validation["warnings"],
            "errors": message_validation["errors"]
        },
        risk_score=message_validation["risk_score"]
    )

    return result
