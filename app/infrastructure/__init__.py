"""
Инфраструктурные компоненты RAG-системы.
"""

from .caching import CacheManager, get_cache_stats, cache_embedding
from .circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState, get_all_circuit_breakers, reset_all_circuit_breakers
from .metrics import MetricsCollector, get_metrics_collector, get_metrics_summary, reset_metrics, chunk_created_total, chunk_size_words_hist, chunk_size_tokens_hist, chunk_optimal_ratio_gauge, indexing_last_pages, indexing_last_chunks
from .security import SecurityMonitor, security_monitor, validate_request

__all__ = [
    'CacheManager',
    'get_cache_stats',
    'cache_embedding',
    'CircuitBreaker',
    'CircuitBreakerError',
    'CircuitState',
    'get_all_circuit_breakers',
    'reset_all_circuit_breakers',
    'MetricsCollector',
    'get_metrics_collector',
    'get_metrics_summary',
    'reset_metrics',
    'chunk_created_total',
    'chunk_size_words_hist',
    'chunk_size_tokens_hist',
    'chunk_optimal_ratio_gauge',
    'indexing_last_pages',
    'indexing_last_chunks',
    'SecurityMonitor',
    'security_monitor',
    'validate_request',
]
