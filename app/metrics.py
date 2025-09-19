"""
Модуль метрик Prometheus для RAG системы.
"""
from __future__ import annotations

import time
from typing import Any, Dict
from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
from loguru import logger


# Основные метрики
query_counter = Counter(
    'rag_queries_total',
    'Total queries processed',
    ['channel', 'status', 'error_type']
)

query_duration = Histogram(
    'rag_query_duration_seconds',
    'Query processing duration in seconds',
    ['stage']
)

embedding_duration = Histogram(
    'rag_embedding_duration_seconds',
    'Embedding generation duration in seconds',
    ['type']  # dense, sparse
)

search_duration = Histogram(
    'rag_search_duration_seconds',
    'Search duration in seconds',
    ['type']  # dense, sparse, hybrid
)

llm_duration = Histogram(
    'rag_llm_duration_seconds',
    'LLM generation duration in seconds',
    ['provider']
)

active_connections = Gauge(
    'rag_active_connections',
    'Number of active connections'
)

cache_hits = Counter(
    'rag_cache_hits_total',
    'Total cache hits',
    ['type']  # embedding, search, llm
)

cache_misses = Counter(
    'rag_cache_misses_total',
    'Total cache misses',
    ['type']
)

circuit_breaker_state = Gauge(
    'rag_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service']
)

search_results_count = Histogram(
    'rag_search_results_count',
    'Number of search results returned',
    ['type']
)

llm_tokens_used = Counter(
    'rag_llm_tokens_total',
    'Total LLM tokens used',
    ['provider', 'type']  # input, output
)

error_counter = Counter(
    'rag_errors_total',
    'Total errors by type',
    ['error_type', 'component']
)

# Информационные метрики
app_info = Info(
    'rag_app_info',
    'Application information'
)

# Инициализация информационных метрик
app_info.info({
    'version': '1.0.0',
    'component': 'rag-system',
    'description': 'RAG System for edna Chat Center'
})


class MetricsCollector:
    """Коллектор метрик для RAG системы."""

    def __init__(self, enable_http_server: bool = True, port: int = 9001):
        """
        Инициализация коллектора метрик.

        Args:
            enable_http_server: Запустить HTTP сервер для метрик
            port: Порт для HTTP сервера
        """
        self.enable_http_server = enable_http_server
        self.port = port

        if enable_http_server:
            try:
                start_http_server(port)
                logger.info(f"Prometheus metrics server started on port {port}")
            except Exception as e:
                logger.warning(f"Failed to start metrics server: {e}")

    def record_query(self, channel: str, status: str, error_type: str = None) -> None:
        """Записать метрику запроса."""
        query_counter.labels(
            channel=channel,
            status=status,
            error_type=error_type or 'none'
        ).inc()

    def record_query_duration(self, stage: str, duration: float) -> None:
        """Записать длительность этапа запроса."""
        query_duration.labels(stage=stage).observe(duration)

    def record_embedding_duration(self, embedding_type: str, duration: float) -> None:
        """Записать длительность создания эмбеддинга."""
        embedding_duration.labels(type=embedding_type).observe(duration)

    def record_search_duration(self, search_type: str, duration: float) -> None:
        """Записать длительность поиска."""
        search_duration.labels(type=search_type).observe(duration)

    def record_llm_duration(self, provider: str, duration: float) -> None:
        """Записать длительность работы LLM."""
        llm_duration.labels(provider=provider).observe(duration)

    def record_cache_hit(self, cache_type: str) -> None:
        """Записать попадание в кэш."""
        cache_hits.labels(type=cache_type).inc()

    def record_cache_miss(self, cache_type: str) -> None:
        """Записать промах кэша."""
        cache_misses.labels(type=cache_type).inc()

    def record_circuit_breaker_state(self, service: str, state: str) -> None:
        """Записать состояние Circuit Breaker."""
        state_value = {
            'closed': 0,
            'open': 1,
            'half_open': 2
        }.get(state, 0)

        circuit_breaker_state.labels(service=service).set(state_value)

    def record_search_results(self, search_type: str, count: int) -> None:
        """Записать количество результатов поиска."""
        search_results_count.labels(type=search_type).observe(count)

    def record_llm_tokens(self, provider: str, token_type: str, count: int) -> None:
        """Записать количество токенов LLM."""
        llm_tokens_used.labels(provider=provider, type=token_type).inc(count)

    def record_error(self, error_type: str, component: str) -> None:
        """Записать ошибку."""
        error_counter.labels(error_type=error_type, component=component).inc()

    def set_active_connections(self, count: int) -> None:
        """Установить количество активных соединений."""
        active_connections.set(count)


# Глобальный экземпляр коллектора
metrics_collector = MetricsCollector()


def track_query_duration(stage: str):
    """Декоратор для отслеживания длительности этапов запроса."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics_collector.record_query_duration(stage, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics_collector.record_query_duration(stage, duration)
                metrics_collector.record_error(type(e).__name__, stage)
                raise
        return wrapper
    return decorator


def track_llm_tokens(provider: str):
    """Декоратор для отслеживания токенов LLM."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Попытка извлечь информацию о токенах из результата
            if isinstance(result, dict):
                input_tokens = result.get('input_tokens', 0)
                output_tokens = result.get('output_tokens', 0)

                if input_tokens:
                    metrics_collector.record_llm_tokens(provider, 'input', input_tokens)
                if output_tokens:
                    metrics_collector.record_llm_tokens(provider, 'output', output_tokens)

            return result
        return wrapper
    return decorator


def get_metrics_summary() -> Dict[str, Any]:
    """Получить сводку метрик."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from prometheus_client.parser import text_string_to_metric_families

        # Получаем метрики в текстовом формате
        metrics_text = generate_latest().decode('utf-8')

        # Парсим метрики
        metrics_data = {}
        for family in text_string_to_metric_families(metrics_text):
            metrics_data[family.name] = {
                'type': family.type,
                'help': family.help,
                'samples': len(family.samples)
            }

        return {
            'status': 'ok',
            'metrics_count': len(metrics_data),
            'metrics': metrics_data
        }
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


def reset_metrics() -> None:
    """Сбросить все метрики (только для тестирования)."""
    logger.warning("Resetting all metrics - this should only be used in testing")

    # Сбрасываем счетчики
    for metric in [query_counter, cache_hits, cache_misses, llm_tokens_used, error_counter]:
        metric._value.set(0)

    # Сбрасываем гистограммы
    for metric in [query_duration, embedding_duration, search_duration, llm_duration, search_results_count]:
        metric._sum.set(0)
        metric._count.set(0)
        metric._buckets.clear()

    # Сбрасываем gauges
    active_connections.set(0)

    logger.info("All metrics reset")
