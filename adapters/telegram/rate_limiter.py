"""
Rate Limiter для Telegram адаптера.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Dict, Optional
from loguru import logger


class RateLimiter:
    """
    Rate Limiter для ограничения частоты запросов от пользователей.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 300,  # 5 минут
        burst_limit: int = 3,
        burst_window: int = 60  # 1 минута
    ):
        """
        Инициализация Rate Limiter.

        Args:
            max_requests: Максимальное количество запросов в окне
            window_seconds: Размер окна в секундах
            burst_limit: Максимальное количество запросов в burst окне
            burst_window: Размер burst окна в секундах
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit
        self.burst_window = burst_window

        # Хранилище запросов по пользователям
        self.user_requests: Dict[str, deque] = defaultdict(deque)
        self.user_burst_requests: Dict[str, deque] = defaultdict(deque)

        logger.info(f"Rate limiter initialized: {max_requests} requests per {window_seconds}s, burst: {burst_limit} per {burst_window}s")

    def is_allowed(self, user_id: str) -> bool:
        """
        Проверяет, разрешен ли запрос от пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            True если запрос разрешен
        """
        current_time = time.time()

        # Очищаем старые запросы
        self._cleanup_old_requests(user_id, current_time)

        # Проверяем burst limit
        if not self._check_burst_limit(user_id, current_time):
            return False

        # Проверяем общий limit
        if not self._check_general_limit(user_id, current_time):
            return False

        # Добавляем новый запрос
        self.user_requests[user_id].append(current_time)
        self.user_burst_requests[user_id].append(current_time)

        return True

    def _cleanup_old_requests(self, user_id: str, current_time: float) -> None:
        """Очищает старые запросы."""
        # Очищаем общие запросы
        while (self.user_requests[user_id] and
               current_time - self.user_requests[user_id][0] > self.window_seconds):
            self.user_requests[user_id].popleft()

        # Очищаем burst запросы
        while (self.user_burst_requests[user_id] and
               current_time - self.user_burst_requests[user_id][0] > self.burst_window):
            self.user_burst_requests[user_id].popleft()

    def _check_burst_limit(self, user_id: str, current_time: float) -> bool:
        """Проверяет burst limit."""
        return len(self.user_burst_requests[user_id]) < self.burst_limit

    def _check_general_limit(self, user_id: str, current_time: float) -> bool:
        """Проверяет общий limit."""
        return len(self.user_requests[user_id]) < self.max_requests

    def get_user_stats(self, user_id: str) -> Dict[str, int]:
        """
        Получает статистику по пользователю.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой
        """
        current_time = time.time()
        self._cleanup_old_requests(user_id, current_time)

        return {
            "total_requests": len(self.user_requests[user_id]),
            "burst_requests": len(self.user_burst_requests[user_id]),
            "max_requests": self.max_requests,
            "burst_limit": self.burst_limit
        }

    def reset_user(self, user_id: str) -> None:
        """
        Сбрасывает лимиты для пользователя.

        Args:
            user_id: ID пользователя
        """
        self.user_requests[user_id].clear()
        self.user_burst_requests[user_id].clear()
        logger.info(f"Rate limits reset for user {user_id}")

    def get_stats(self) -> Dict[str, int]:
        """
        Получает общую статистику.

        Returns:
            Словарь со статистикой
        """
        return {
            "active_users": len(self.user_requests),
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "burst_limit": self.burst_limit,
            "burst_window": self.burst_window
        }
