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
            True если запрос разрешен, False если превышен лимит
        """
        now = time.time()

        # Очищаем старые запросы
        self._cleanup_old_requests(user_id, now)

        # Проверяем burst лимит
        if not self._check_burst_limit(user_id, now):
            logger.warning(f"Burst limit exceeded for user {user_id}")
            return False

        # Проверяем основной лимит
        if not self._check_main_limit(user_id, now):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False

        # Записываем новый запрос
        self.user_requests[user_id].append(now)
        self.user_burst_requests[user_id].append(now)

        return True

    def _cleanup_old_requests(self, user_id: str, now: float) -> None:
        """Удаляет старые запросы из истории."""
        # Очищаем основной лимит
        main_requests = self.user_requests[user_id]
        while main_requests and main_requests[0] < now - self.window_seconds:
            main_requests.popleft()

        # Очищаем burst лимит
        burst_requests = self.user_burst_requests[user_id]
        while burst_requests and burst_requests[0] < now - self.burst_window:
            burst_requests.popleft()

    def _check_burst_limit(self, user_id: str, now: float) -> bool:
        """Проверяет burst лимит."""
        burst_requests = self.user_burst_requests[user_id]
        return len(burst_requests) < self.burst_limit

    def _check_main_limit(self, user_id: str, now: float) -> bool:
        """Проверяет основной лимит."""
        main_requests = self.user_requests[user_id]
        return len(main_requests) < self.max_requests

    def get_remaining_requests(self, user_id: str) -> int:
        """
        Возвращает количество оставшихся запросов для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество оставшихся запросов
        """
        now = time.time()
        self._cleanup_old_requests(user_id, now)

        main_requests = self.user_requests[user_id]
        return max(0, self.max_requests - len(main_requests))

    def get_reset_time(self, user_id: str) -> Optional[float]:
        """
        Возвращает время сброса лимита для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Время сброса лимита или None если лимит не превышен
        """
        now = time.time()
        self._cleanup_old_requests(user_id, now)

        main_requests = self.user_requests[user_id]
        if len(main_requests) < self.max_requests:
            return None

        # Возвращаем время самого старого запроса + окно
        return main_requests[0] + self.window_seconds

    def get_user_stats(self, user_id: str) -> Dict[str, any]:
        """
        Возвращает статистику пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой
        """
        now = time.time()
        self._cleanup_old_requests(user_id, now)

        main_requests = self.user_requests[user_id]
        burst_requests = self.user_burst_requests[user_id]

        return {
            "user_id": user_id,
            "main_requests": len(main_requests),
            "main_limit": self.max_requests,
            "burst_requests": len(burst_requests),
            "burst_limit": self.burst_limit,
            "remaining_requests": self.get_remaining_requests(user_id),
            "reset_time": self.get_reset_time(user_id)
        }

    def reset_user(self, user_id: str) -> None:
        """
        Сбрасывает лимиты для пользователя.

        Args:
            user_id: ID пользователя
        """
        if user_id in self.user_requests:
            del self.user_requests[user_id]
        if user_id in self.user_burst_requests:
            del self.user_burst_requests[user_id]

        logger.info(f"Rate limits reset for user {user_id}")

    def get_all_stats(self) -> Dict[str, Dict[str, any]]:
        """
        Возвращает статистику всех пользователей.

        Returns:
            Словарь со статистикой всех пользователей
        """
        now = time.time()
        stats = {}

        # Получаем всех пользователей
        all_users = set(self.user_requests.keys()) | set(self.user_burst_requests.keys())

        for user_id in all_users:
            self._cleanup_old_requests(user_id, now)
            stats[user_id] = self.get_user_stats(user_id)

        return stats


# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter()
