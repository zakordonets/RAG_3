"""
Circuit Breaker для внешних сервисов RAG системы.
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, Optional
from loguru import logger


class CircuitState(Enum):
    """Состояния Circuit Breaker."""
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # Блокировка вызовов
    HALF_OPEN = "half_open"  # Тестирование восстановления


class CircuitBreakerError(Exception):
    """Ошибка Circuit Breaker."""
    pass


class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных сбоев.

    Принцип работы:
    - CLOSED: Нормальная работа, все вызовы проходят
    - OPEN: После failure_threshold ошибок переходит в OPEN, блокирует вызовы
    - HALF_OPEN: Через timeout секунд переходит в HALF_OPEN, разрешает тестовые вызовы
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "circuit_breaker"
    ):
        """
        Инициализация Circuit Breaker.

        Args:
            failure_threshold: Количество ошибок для перехода в OPEN
            timeout: Время в секундах до перехода в HALF_OPEN
            expected_exception: Тип исключения для отслеживания
            name: Имя для логирования
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.name = name

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

        logger.info(f"Circuit breaker '{name}' initialized: threshold={failure_threshold}, timeout={timeout}s")

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнить функцию через Circuit Breaker.

        Args:
            func: Функция для выполнения
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции

        Returns:
            Результат выполнения функции

        Raises:
            CircuitBreakerError: Если Circuit Breaker в состоянии OPEN
            Exception: Оригинальное исключение от функции
        """
        # Проверяем состояние
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            # Выполняем функцию
            result = func(*args, **kwargs)

            # Успешный вызов - сбрасываем счетчик ошибок
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

            return result

        except self.expected_exception as e:
            # Обрабатываем ожидаемое исключение
            self._record_failure()
            logger.warning(f"Circuit breaker '{self.name}' recorded failure: {e}")
            raise
        except Exception as e:
            # Неожиданное исключение - не считаем как failure
            logger.error(f"Circuit breaker '{self.name}' unexpected error: {e}")
            raise

    def _record_failure(self) -> None:
        """Записать ошибку."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker '{self.name}' opened after {self.failure_count} failures")

    def _should_attempt_reset(self) -> bool:
        """Проверить, можно ли попытаться сбросить Circuit Breaker."""
        if self.last_failure_time is None:
            return True

        return time.time() - self.last_failure_time >= self.timeout

    def reset(self) -> None:
        """Принудительно сбросить Circuit Breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit breaker '{self.name}' manually reset")

    def get_state(self) -> dict[str, Any]:
        """Получить текущее состояние Circuit Breaker."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "threshold": self.failure_threshold,
            "timeout": self.timeout
        }


# Глобальные Circuit Breakers для разных сервисов
llm_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    name="llm_service"
)

embedding_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=60,
    name="embedding_service"
)

qdrant_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    name="qdrant_service"
)


def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """
    Декоратор для применения Circuit Breaker к функции.

    Args:
        circuit_breaker: Экземпляр Circuit Breaker
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def get_all_circuit_breakers() -> dict[str, dict[str, Any]]:
    """Получить состояние всех Circuit Breakers."""
    return {
        "llm": llm_circuit_breaker.get_state(),
        "embedding": embedding_circuit_breaker.get_state(),
        "qdrant": qdrant_circuit_breaker.get_state(),
    }


def reset_all_circuit_breakers() -> None:
    """Сбросить все Circuit Breakers."""
    llm_circuit_breaker.reset()
    embedding_circuit_breaker.reset()
    qdrant_circuit_breaker.reset()
    logger.info("All circuit breakers reset")
