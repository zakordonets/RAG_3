"""
Security utilities: validation and basic monitoring used across the RAG API.
This is a compact reconstruction that preserves the public API expected by the
rest of the codebase (SecurityValidator, SecurityMonitor, validate_request,
security_monitor).
"""
from __future__ import annotations

import re
import html
import time
from typing import Any, Dict, List
from loguru import logger


class SecurityConfig:
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


class SecurityValidator:
    def __init__(self) -> None:
        self._blocked_regexes = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in SecurityConfig.BLOCKED_PATTERNS]

    def sanitize_message(self, message: str) -> str:
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
        return channel in SecurityConfig.ALLOWED_CHANNELS

    def validate_chat_id(self, chat_id: Any) -> bool:
        # Allow empty/none
        if chat_id is None or chat_id == "":
            return True
        s = str(chat_id)
        if len(s) > 100:
            return False
        if re.search(r"[<>\"']", s):
            return False
        return True

    def validate_message(self, message: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "is_valid": True,
            "sanitized_message": message,
            "warnings": [],
            "errors": [],
            "risk_score": 0,
        }

        if not message or not message.strip():
            result["is_valid"] = False
            result["errors"].append("Empty message")
            return result

        sanitized = self.sanitize_message(message)
        result["sanitized_message"] = sanitized
        if sanitized != message:
            result["warnings"].append("Message sanitized")

        return result


class SecurityMonitor:
    """Lightweight in-memory monitoring of suspicious activity and blocks."""

    def __init__(self) -> None:
        self.suspicious_activity: Dict[str, List[Dict[str, Any]]] = {}
        self.blocked_users: set[str] = set()
        self.alert_threshold: int = 5

    def log_activity(self, user_id: str, activity_type: str, details: Dict[str, Any], risk_score: int = 0) -> None:
        rec = {
            "timestamp": time.time(),
            "type": activity_type,
            "details": details,
            "risk_score": int(risk_score) if isinstance(risk_score, int) else 0,
        }
        self.suspicious_activity.setdefault(str(user_id), []).append(rec)

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
        return sum(int(a.get("risk_score", 0)) for a in self.suspicious_activity.get(uid, []) if a.get("timestamp", 0) >= cutoff)

    def get_security_stats(self) -> Dict[str, Any]:
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
    """Validate incoming request payload and record basic activity."""
    result: Dict[str, Any] = {
        "is_valid": True,
        "sanitized_message": message,
        "warnings": [],
        "errors": [],
        "risk_score": 0,
    }

    if security_monitor.is_user_blocked(str(user_id)):
        result["is_valid"] = False
        result["errors"].append("User is blocked")
        return result

    if not security_validator.validate_channel(channel):
        result["is_valid"] = False
        result["errors"].append(f"Invalid channel: {channel}")
        return result

    if not security_validator.validate_chat_id(chat_id):
        result["is_valid"] = False
        result["errors"].append(f"Invalid chat_id: {chat_id}")
        return result

    msg_validation = security_validator.validate_message(message)
    result.update(msg_validation)

    security_monitor.log_activity(
        user_id=str(user_id),
        activity_type="message_validation",
        details={
            "channel": channel,
            "chat_id": str(chat_id),
            "message_length": len(message or ""),
            "warnings": msg_validation.get("warnings", []),
            "errors": msg_validation.get("errors", []),
        },
        risk_score=msg_validation.get("risk_score", 0),
    )

    return result

