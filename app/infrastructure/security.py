"""
Утилиты безопасности для RAG API:
- базовая проверка входящих запросов (канал, chat_id, текст);
- санитация текста от потенциально опасных конструкций (HTML/JS инъекции);
- лёгкий in-memory мониторинг активности и блокировок пользователей.

Модуль специально сделан компактным и без внешних зависимостей, но при этом
сохраняет публичный API, на который завязан остальной код:
SecurityValidator, SecurityMonitor, validate_request, security_monitor.
"""
from __future__ import annotations

import re
import html
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List
from loguru import logger


class SecurityConfig:
    """Константы и настройки, связанные с безопасностью на уровне входящих сообщений."""

    MAX_MESSAGE_LENGTH = 2000
    ALLOWED_CHANNELS = ["telegram", "web", "api"]

    # Very conservative blocked patterns for HTML/JS injection vectors
    BLOCKED_PATTERNS = [
        r"<script.*?>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"data:text/html",
        r"vbscript:",
        r"<iframe.*?>.*?</iframe>",
        r"<object.*?>.*?</object>",
        r"<embed.*?>",
        r"<link.*?>",
        r"<meta.*?>",
        r"<style.*?>.*?</style>",
        r"<form.*?>.*?</form>",
    ]


@dataclass
class ValidationResult:
    """
    Структурированный результат валидации/санитации сообщения.

    Поля:
    - is_valid: итоговый флаг валидности (False, если есть критические ошибки);
    - sanitized_message: уже очищенный/усечённый текст сообщения;
    - warnings: мягкие предупреждения (например, «сообщение было очищено»);
    - errors: ошибки валидации (пустое сообщение, запрещённый канал и т.п.);
    - risk_score: числовая оценка риска (пока всегда 0, зарезервировано под будущее).
    """

    is_valid: bool = True
    sanitized_message: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    risk_score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "sanitized_message": self.sanitized_message,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "risk_score": self.risk_score,
        }


@dataclass
class SecurityEvent:
    """
    Событие безопасности, которое фиксируется монитором.

    Используется только в памяти, чтобы иметь краткую историю активности
    и на её основе считать risk_score.
    """

    timestamp: float
    event_type: str
    details: Dict[str, Any]
    risk_score: int = 0


class SecurityValidator:
    """
    Отвечает за валидацию и санитацию полей входящего запроса.

    Основные задачи:
    - зачистка текста сообщения от потенциально опасных конструкций;
    - проверка разрешённости канала;
    - базовая проверка chat_id.
    """

    def __init__(self) -> None:
        self._blocked_regexes = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in SecurityConfig.BLOCKED_PATTERNS]

    def sanitize_message(self, message: str) -> str:
        """
        HTML-экранирует текст, вырезает потенциально опасные куски и ограничивает длину.

        Это не полноценный WAF, но работает как «грубый фильтр», чтобы убрать
        очевидные HTML/JS инъекции и чрезмерно длинные сообщения.
        """
        if not message:
            return ""
        # HTML escape first
        sanitized = html.escape(message)
        # Strip blocked patterns
        for rx in self._blocked_regexes:
            sanitized = rx.sub("", sanitized)
        # Length clamp
        if len(sanitized) > SecurityConfig.MAX_MESSAGE_LENGTH:
            sanitized = sanitized[: SecurityConfig.MAX_MESSAGE_LENGTH]
        # Whitespace normalize
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def validate_channel(self, channel: str) -> bool:
        """
        Проверяет, разрешён ли канал (telegram/web/api).

        Не занимается авторизацией, только грубой проверкой допустимых значений.
        """
        return channel in SecurityConfig.ALLOWED_CHANNELS

    def validate_chat_id(self, chat_id: Any) -> bool:
        """
        Проверяет chat_id на базовую «безопасность».

        Допустимо:
        - пустое значение (None / пустая строка);
        - строка разумной длины без спецсимволов < > " '.
        """
        # Allow empty/none
        if chat_id is None or chat_id == "":
            return True
        s = str(chat_id)
        if len(s) > 100:
            return False
        if re.search(r"[<>\"']", s):
            return False
        return True

    def validate_message(self, message: str) -> ValidationResult:
        """
        Валидирует и санитизирует текст сообщения.

        - Если сообщение пустое, помечает результат как невалидный;
        - в остальных случаях возвращает ValidationResult с очищенным текстом
          и, при необходимости, предупреждением о модификации.
        """
        result = ValidationResult(sanitized_message=message or "")
        if not message or not message.strip():
            result.is_valid = False
            result.errors.append("Empty message")
            return result

        sanitized = self.sanitize_message(message)
        result.sanitized_message = sanitized
        if sanitized != message:
            result.warnings.append("Message sanitized")

        return result


class SecurityMonitor:
    """
    Лёгкий in-memory монитор активности и блокировок.

    Не претендует на полноценную систему аудита, но позволяет:
    - фиксировать ключевые события по пользователю (тип, детали, риск);
    - проверять, заблокирован ли пользователь;
    - вычислять агрегированный риск за последний час;
    - отдавать короткую сводку для /admin API.
    """

    def __init__(self) -> None:
        self.suspicious_activity: Dict[str, List[SecurityEvent]] = {}
        self.blocked_users: set[str] = set()
        self.alert_threshold: int = 5

    def log_activity(self, user_id: str, activity_type: str, details: Dict[str, Any], risk_score: int = 0) -> None:
        event = SecurityEvent(
            timestamp=time.time(),
            event_type=activity_type,
            details=details,
            risk_score=int(risk_score) if isinstance(risk_score, int) else 0,
        )
        self.suspicious_activity.setdefault(str(user_id), []).append(event)

    def block_user(self, user_id: str, reason: str = "") -> None:
        self.blocked_users.add(str(user_id))
        logger.warning(f"User {user_id} blocked: {reason}")

    def is_user_blocked(self, user_id: str) -> bool:
        return str(user_id) in self.blocked_users

    def get_user_risk_score(self, user_id: str) -> int:
        uid = str(user_id)
        if uid not in self.suspicious_activity:
            return 0
        cutoff = time.time() - 3600
        return sum(event.risk_score for event in self.suspicious_activity.get(uid, []) if event.timestamp >= cutoff)

    def get_security_stats(self) -> Dict[str, Any]:
        """
        Возвращает агрегированную статистику для административных панелей.

        Показывает количество пользователей с активностью, количество блокировок
        и число «высокорисковых» пользователей по текущему порогу.
        """
        total_users = len(self.suspicious_activity)
        blocked_users = len(self.blocked_users)
        high_risk_users = sum(1 for uid in self.suspicious_activity if self.get_user_risk_score(uid) > 10)
        return {
            "total_users": total_users,
            "blocked_users": blocked_users,
            "high_risk_users": high_risk_users,
            "alert_threshold": self.alert_threshold,
        }


security_validator = SecurityValidator()
security_monitor = SecurityMonitor()


def validate_request(user_id: str, message: str, channel: str, chat_id: Any) -> Dict[str, Any]:
    """
    Высокоуровневая валидация входящего запроса и логирование активности.

    Последовательность проверок:
    1. Пользователь не заблокирован (SecurityMonitor);
    2. Канал входит в разрешённый список (telegram/web/api);
    3. chat_id выглядит безопасно;
    4. Текст сообщения проходит через санитацию/валидацию.

    В любом случае записывает событие в SecurityMonitor с базовыми деталями.
    Возвращает dict в формате ValidationResult.to_dict(), чтобы не ломать API.
    """
    user_id_str = str(user_id)
    result = ValidationResult(sanitized_message=message or "")

    if security_monitor.is_user_blocked(user_id_str):
        result.is_valid = False
        result.errors.append("User is blocked")
        return result.to_dict()

    if not security_validator.validate_channel(channel):
        result.is_valid = False
        result.errors.append(f"Invalid channel: {channel}")
        return result.to_dict()

    if not security_validator.validate_chat_id(chat_id):
        result.is_valid = False
        result.errors.append(f"Invalid chat_id: {chat_id}")
        return result.to_dict()

    msg_validation = security_validator.validate_message(message)
    merged = msg_validation.to_dict()
    merged["is_valid"] = merged["is_valid"] and result.is_valid
    merged["warnings"] = result.warnings + merged["warnings"]
    merged["errors"] = result.errors + merged["errors"]
    result = ValidationResult(
        is_valid=merged["is_valid"],
        sanitized_message=merged["sanitized_message"],
        warnings=merged["warnings"],
        errors=merged["errors"],
        risk_score=merged["risk_score"],
    )

    security_monitor.log_activity(
        user_id=user_id_str,
        activity_type="message_validation",
        details={
            "channel": channel,
            "chat_id": str(chat_id),
            "message_length": len(message or ""),
            "warnings": list(msg_validation.warnings),
            "errors": list(msg_validation.errors),
        },
        risk_score=msg_validation.risk_score,
    )

    return result.to_dict()
