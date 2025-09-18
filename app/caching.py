"""
Модуль кэширования для RAG системы.
"""
from __future__ import annotations

import json
import hashlib
import time
from typing import Any, Optional
from functools import wraps
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache")

from app.config import CONFIG


class CacheConfig:
    """Конфигурация кэширования."""
    EMBEDDING_TTL = 3600  # 1 час
    SEARCH_TTL = 1800     # 30 минут
    LLM_TTL = 600         # 10 минут
    MAX_MEMORY_ITEMS = 1000


class InMemoryCache:
    """Простой in-memory кэш как fallback."""

    def __init__(self, max_items: int = 1000):
        self.cache: dict[str, tuple[Any, float]] = {}
        self.max_items = max_items

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, expiry = self.cache[key]
            if time.time() < expiry:
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        # Удаляем старые элементы если кэш переполнен
        if len(self.cache) >= self.max_items:
            # Удаляем 20% самых старых элементов
            items_to_remove = len(self.cache) // 5
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1][1])
            for old_key, _ in sorted_items[:items_to_remove]:
                del self.cache[old_key]

        expiry = time.time() + ttl
        self.cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        self.cache.pop(key, None)

    def clear(self) -> None:
        self.cache.clear()


class CacheManager:
    """Менеджер кэширования с поддержкой Redis и in-memory fallback."""

    def __init__(self):
        self.redis_client = None
        self.memory_cache = InMemoryCache(CacheConfig.MAX_MEMORY_ITEMS)

        if REDIS_AVAILABLE and CONFIG.redis_url:
            try:
                self.redis_client = redis.from_url(CONFIG.redis_url)
                # Проверяем подключение
                self.redis_client.ping()
                logger.info("Redis cache initialized")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using memory cache")
                self.redis_client = None
        else:
            logger.info("Using in-memory cache")

    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша."""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    return json.loads(value)
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        """Установить значение в кэш."""
        try:
            if self.redis_client:
                self.redis_client.setex(key, ttl, json.dumps(value))
            else:
                self.memory_cache.set(key, value, ttl)
        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    def delete(self, key: str) -> None:
        """Удалить значение из кэша."""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self.memory_cache.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")

    def clear(self) -> None:
        """Очистить весь кэш."""
        try:
            if self.redis_client:
                self.redis_client.flushdb()
            else:
                self.memory_cache.clear()
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")


# Глобальный экземпляр кэш-менеджера
cache_manager = CacheManager()


def cache_key(prefix: str, *args) -> str:
    """Генерация ключа кэша."""
    content = "|".join(str(arg) for arg in args)
    hash_obj = hashlib.md5(content.encode())
    return f"{prefix}:{hash_obj.hexdigest()}"


def cached(prefix: str, ttl: int = 3600):
    """
    Декоратор для кэширования результатов функций.

    Args:
        prefix: Префикс для ключей кэша
        ttl: Время жизни в секундах
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем ключ кэша из аргументов функции
            key = cache_key(prefix, func.__name__, args, tuple(sorted(kwargs.items())))

            # Пытаемся получить из кэша
            cached_result = cache_manager.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result

            # Выполняем функцию и кэшируем результат
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            cache_manager.set(key, result, ttl)

            return result
        return wrapper
    return decorator


def cache_embedding(ttl: int = CacheConfig.EMBEDDING_TTL):
    """Декоратор для кэширования эмбеддингов."""
    return cached("embedding", ttl)


def cache_search(ttl: int = CacheConfig.SEARCH_TTL):
    """Декоратор для кэширования результатов поиска."""
    return cached("search", ttl)


def cache_llm(ttl: int = CacheConfig.LLM_TTL):
    """Декоратор для кэширования ответов LLM."""
    return cached("llm", ttl)


def invalidate_pattern(pattern: str) -> None:
    """Удалить все ключи кэша, соответствующие паттерну."""
    try:
        if cache_manager.redis_client:
            keys = cache_manager.redis_client.keys(pattern)
            if keys:
                cache_manager.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache keys matching {pattern}")
        else:
            # Для in-memory кэша удаляем все ключи, содержащие паттерн
            keys_to_delete = [key for key in cache_manager.memory_cache.cache.keys() if pattern in key]
            for key in keys_to_delete:
                cache_manager.memory_cache.delete(key)
            logger.info(f"Invalidated {len(keys_to_delete)} cache keys matching {pattern}")
    except Exception as e:
        logger.warning(f"Cache invalidation error: {e}")


def get_cache_stats() -> dict[str, Any]:
    """Получить статистику кэша."""
    try:
        if cache_manager.redis_client:
            info = cache_manager.redis_client.info()
            return {
                "type": "redis",
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        else:
            return {
                "type": "memory",
                "items": len(cache_manager.memory_cache.cache),
                "max_items": cache_manager.memory_cache.max_items,
            }
    except Exception as e:
        logger.warning(f"Cache stats error: {e}")
        return {"type": "unknown", "error": str(e)}
