from __future__ import annotations

from flask import Blueprint, jsonify, request
from loguru import logger
from ingestion.run import run_unified_indexing
from app.infrastructure import get_metrics_summary, reset_metrics, get_all_circuit_breakers, reset_all_circuit_breakers, get_cache_stats
from adapters.telegram import RateLimiter

# Создаем глобальный экземпляр rate limiter
rate_limiter = RateLimiter()
from app.infrastructure import security_monitor

bp = Blueprint("admin", __name__)


@bp.post("/reindex")
def reindex():
    """
    Запуск переиндексации документации.

    Выполняет индексацию документов в векторную базу данных Qdrant:
    - При force_full=false: индексирует только измененные документы (инкрементальная)
    - При force_full=true: полная переиндексация с очисткой коллекции

    Процесс включает: парсинг документов, чанкинг, генерацию эмбеддингов,
    сохранение в Qdrant с метаданными.

    .. versionadded:: 4.0.0
    .. versionchanged:: 4.3.0
       Используется единая DAG архитектура индексации

    ---
    tags:
      - Admin
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            force_full:
              type: boolean
              description: |
                Принудительная полная переиндексация с очисткой коллекции.
                false (по умолчанию) - индексировать только измененные документы.
                true - полная переиндексация всех документов.
              default: false
              example: false
          example:
            force_full: false
    responses:
      200:
        description: Индексация успешно завершена
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [done]
              description: Статус выполнения
            force_full:
              type: boolean
              description: Был ли выполнен полный reindex
            total_docs:
              type: integer
              description: Общее количество обработанных документов
            processed_docs:
              type: integer
              description: Количество успешно обработанных документов
            failed_docs:
              type: integer
              description: Количество документов с ошибками
            duration:
              type: number
              format: float
              description: Длительность индексации в секундах
          required: [status, force_full]
        examples:
          application/json:
            status: "done"
            force_full: false
            total_docs: 156
            processed_docs: 156
            failed_docs: 0
            duration: 245.32
      500:
        description: Ошибка переиндексации
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [reindex_failed]
            message:
              type: string
              description: Описание ошибки
          required: [error, message]
        examples:
          application/json:
            error: "reindex_failed"
            message: "Failed to connect to Qdrant service"
    """
    try:
        force_full = bool((request.get_json(silent=True) or {}).get("force_full", False))

        # Используем новую единую функцию индексации
        from app.config.app_config import CONFIG
        config = {
            "docs_root": CONFIG.docs_root,
            "site_base_url": CONFIG.site_base_url,
            "site_docs_prefix": CONFIG.site_docs_prefix,
            "collection_name": CONFIG.qdrant_collection,
            "chunk_max_tokens": CONFIG.chunk_max_tokens,
            "chunk_min_tokens": CONFIG.chunk_min_tokens
        }

        res = run_unified_indexing(
            source_type="docusaurus",
            config=config,
            reindex_mode="full" if force_full else "changed",
            clear_collection=force_full
        )

        return jsonify({"status": "done", "force_full": force_full, **res})
    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        return jsonify({"error": "reindex_failed", "message": str(e)}), 500


@bp.get("/health")
def health():
    """
    Проверка состояния системы и всех зависимых сервисов.

    Выполняет health check для:
    - Circuit Breakers (LLM, Embedding, Qdrant, Sparse сервисы)
    - Redis кэш
    - Общее состояние приложения

    Используется для мониторинга и Kubernetes liveness/readiness probes.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Система работает нормально
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [ok]
              description: Общий статус системы
            circuit_breakers:
              type: object
              description: Состояние Circuit Breakers для каждого сервиса
              properties:
                llm_service:
                  type: object
                  properties:
                    state:
                      type: string
                      enum: [closed, open, half_open]
                      description: |
                        closed - нормальная работа
                        open - сервис недоступен
                        half_open - тестирование восстановления
                    failure_count:
                      type: integer
                      description: Количество последовательных ошибок
                embedding_service:
                  type: object
                qdrant_service:
                  type: object
            cache:
              type: object
              description: Состояние кэша
              properties:
                redis_available:
                  type: boolean
                  description: Доступность Redis
                stats:
                  type: object
                  description: Статистика использования кэша
          required: [status]
        examples:
          application/json:
            status: "ok"
            circuit_breakers:
              llm_service:
                state: "closed"
                failure_count: 0
              embedding_service:
                state: "closed"
                failure_count: 0
              qdrant_service:
                state: "closed"
                failure_count: 0
            cache:
              redis_available: true
              stats:
                hits: 1523
                misses: 456
      500:
        description: Ошибка проверки здоровья системы
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [error]
            error:
              type: string
          required: [status, error]
        examples:
          application/json:
            status: "error"
            error: "Failed to check circuit breakers"
    """
    try:
        # Базовая проверка здоровья
        health_status = {"status": "ok"}

        # Проверка Circuit Breakers
        circuit_breakers = get_all_circuit_breakers()
        health_status["circuit_breakers"] = circuit_breakers

        # Проверка кэша
        cache_stats = get_cache_stats()
        health_status["cache"] = cache_stats

        return jsonify(health_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@bp.get("/metrics")
def metrics():
    """
    Получить метрики Prometheus в JSON формате.

    Возвращает агрегированные метрики для мониторинга производительности:
    - Общее количество запросов по каналам и статусам
    - Средняя длительность обработки запросов
    - Метрики производительности компонентов (embedding, search, LLM)
    - Статистика кэша (hit rate)
    - Количество ошибок

    Для экспорта в Prometheus используйте /v1/admin/metrics/raw

    ---
    tags:
      - Admin
    produces:
      - application/json
    responses:
      200:
        description: Агрегированные метрики в JSON формате
        schema:
          type: object
          properties:
            queries_total:
              type: integer
              description: Общее количество обработанных запросов
            queries_by_channel:
              type: object
              description: Количество запросов по каналам
              properties:
                telegram:
                  type: integer
                web:
                  type: integer
                api:
                  type: integer
            queries_by_status:
              type: object
              description: Количество запросов по статусам
              properties:
                success:
                  type: integer
                error:
                  type: integer
            avg_query_duration:
              type: number
              format: float
              description: Средняя длительность обработки запроса (секунды)
            avg_embedding_duration:
              type: number
              format: float
              description: Среднее время генерации эмбеддингов (секунды)
            avg_search_duration:
              type: number
              format: float
              description: Среднее время поиска в Qdrant (секунды)
            avg_llm_duration:
              type: number
              format: float
              description: Среднее время генерации ответа LLM (секунды)
            cache_hit_rate:
              type: number
              format: float
              description: Процент попаданий в кэш (0.0-1.0)
            errors_total:
              type: integer
              description: Общее количество ошибок
        examples:
          application/json:
            queries_total: 1523
            queries_by_channel:
              telegram: 1200
              web: 323
              api: 0
            queries_by_status:
              success: 1450
              error: 73
            avg_query_duration: 2.34
            avg_embedding_duration: 0.45
            avg_search_duration: 0.23
            avg_llm_duration: 1.56
            cache_hit_rate: 0.67
            errors_total: 73
      500:
        description: Ошибка получения метрик
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "metrics_failed"
            message: "Failed to retrieve metrics from Prometheus"
    """
    try:
        metrics_summary = get_metrics_summary()
        return jsonify(metrics_summary)
    except Exception as e:
        logger.error(f"Metrics retrieval failed: {e}")
        return jsonify({"error": "metrics_failed", "message": str(e)}), 500


@bp.get("/metrics/raw")
def metrics_raw():
    """Получить сырые метрики Prometheus в текстовом формате.

    ---
    tags:
      - Admin
    produces:
      - text/plain
    responses:
      200:
        description: Сырые метрики Prometheus
      500:
        description: Ошибка
    """
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from flask import Response

        data = generate_latest()
        return Response(data, mimetype=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Raw metrics retrieval failed: {e}")
        return jsonify({"error": "raw_metrics_failed", "message": str(e)}), 500


@bp.post("/metrics/reset")
def metrics_reset():
    """Сбросить все метрики (только для тестирования).

    ---
    tags:
      - Admin
    responses:
      200:
        description: Метрики сброшены
      500:
        description: Ошибка
    """
    try:
        reset_metrics()
        return jsonify({"status": "metrics_reset"})
    except Exception as e:
        logger.error(f"Metrics reset failed: {e}")
        return jsonify({"error": "metrics_reset_failed", "message": str(e)}), 500


@bp.get("/circuit-breakers")
def circuit_breakers():
    """Получить состояние Circuit Breakers.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Состояние Circuit Breakers
      500:
        description: Ошибка
    """
    try:
        breakers = get_all_circuit_breakers()
        return jsonify(breakers)
    except Exception as e:
        logger.error(f"Circuit breakers status failed: {e}")
        return jsonify({"error": "circuit_breakers_failed", "message": str(e)}), 500


@bp.post("/circuit-breakers/reset")
def circuit_breakers_reset():
    """Сбросить все Circuit Breakers.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Circuit Breakers сброшены
      500:
        description: Ошибка
    """
    try:
        reset_all_circuit_breakers()
        return jsonify({"status": "circuit_breakers_reset"})
    except Exception as e:
        logger.error(f"Circuit breakers reset failed: {e}")
        return jsonify({"error": "circuit_breakers_reset_failed", "message": str(e)}), 500


@bp.get("/cache")
def cache_status():
    """Получить состояние кэша.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Статистика кэша
      500:
        description: Ошибка
    """
    try:
        stats = get_cache_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Cache status failed: {e}")
        return jsonify({"error": "cache_status_failed", "message": str(e)}), 500


@bp.get("/rate-limiter")
def rate_limiter_status():
    """
    Получить глобальное состояние Rate Limiter.

    Возвращает статистику лимитирования запросов:
    - Общее количество отслеживаемых пользователей
    - Количество заблокированных пользователей
    - Настройки лимитов (запросы в окне, burst protection)
    - Активные пользователи за последний час

    Rate Limiter защищает систему от злоупотреблений:
    - Основной лимит: 10 запросов за 5 минут
    - Burst protection: 3 запроса в минуту

    ---
    tags:
      - Admin
    produces:
      - application/json
    responses:
      200:
        description: Глобальная статистика Rate Limiter
        schema:
          type: object
          properties:
            total_users:
              type: integer
              description: Общее количество пользователей в системе rate limiting
            blocked_users:
              type: integer
              description: Количество пользователей, превысивших лимит
            limits:
              type: object
              description: Настройки лимитов
              properties:
                requests_per_window:
                  type: integer
                  description: Максимум запросов в основном окне
                window_seconds:
                  type: integer
                  description: Размер основного окна в секундах
                burst_limit:
                  type: integer
                  description: Максимум запросов в burst окне
                burst_window_seconds:
                  type: integer
                  description: Размер burst окна в секундах
            active_users_last_hour:
              type: integer
              description: Количество активных пользователей за последний час
        examples:
          application/json:
            total_users: 245
            blocked_users: 3
            limits:
              requests_per_window: 10
              window_seconds: 300
              burst_limit: 3
              burst_window_seconds: 60
            active_users_last_hour: 156
      500:
        description: Ошибка получения статистики
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "rate_limiter_status_failed"
            message: "Failed to retrieve rate limiter stats"
    """
    try:
        stats = rate_limiter.get_all_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Rate limiter status failed: {e}")
        return jsonify({"error": "rate_limiter_status_failed", "message": str(e)}), 500


@bp.get("/rate-limiter/<user_id>")
def rate_limiter_user_status(user_id: str):
    """
    Получить состояние Rate Limiter для конкретного пользователя.

    Показывает детальную информацию о лимитах пользователя:
    - Количество запросов в текущем окне
    - Осталось доступных запросов
    - Статус блокировки
    - Время начала окна и сброса лимитов

    ---
    tags:
      - Admin
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
        description: Уникальный идентификатор пользователя (обычно chat_id)
        example: "123456789"
    produces:
      - application/json
    responses:
      200:
        description: Статистика лимитов для пользователя
        schema:
          type: object
          properties:
            user_id:
              type: string
              description: ID пользователя
            requests_count:
              type: integer
              description: Количество запросов в текущем окне
            window_start:
              type: string
              format: date-time
              description: Начало текущего окна лимитирования
            is_limited:
              type: boolean
              description: Превышен ли лимит (пользователь заблокирован)
            remaining:
              type: integer
              description: Осталось доступных запросов в текущем окне
            reset_at:
              type: string
              format: date-time
              description: Время сброса лимитов
        examples:
          application/json:
            user_id: "123456789"
            requests_count: 5
            window_start: "2025-10-09T10:00:00Z"
            is_limited: false
            remaining: 5
            reset_at: "2025-10-09T10:05:00Z"
      500:
        description: Ошибка получения статистики пользователя
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "rate_limiter_user_status_failed"
            message: "Failed to retrieve user stats"
    """
    try:
        stats = rate_limiter.get_user_stats(user_id)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Rate limiter user status failed: {e}")
        return jsonify({"error": "rate_limiter_user_status_failed", "message": str(e)}), 500


@bp.post("/rate-limiter/<user_id>/reset")
def rate_limiter_reset_user(user_id: str):
    """Сбросить лимиты для конкретного пользователя.

    ---
    tags:
      - Admin
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
    responses:
      200:
        description: Лимиты сброшены
      500:
        description: Ошибка
    """
    try:
        rate_limiter.reset_user(user_id)
        return jsonify({"status": "rate_limits_reset", "user_id": user_id})
    except Exception as e:
        logger.error(f"Rate limiter reset failed: {e}")
        return jsonify({"error": "rate_limiter_reset_failed", "message": str(e)}), 500


@bp.get("/security")
def security_status():
    """
    Получить общую статистику системы безопасности.

    Мониторинг безопасности системы:
    - Отслеживание пользователей по уровням риска
    - Подсчет заблокированных пользователей
    - События безопасности за последние 24 часа

    Уровни риска:
    - low (0-3): нормальная активность
    - medium (4-6): повышенное внимание
    - high (7-10): подозрительная активность, автоблокировка

    ---
    tags:
      - Admin
    produces:
      - application/json
    responses:
      200:
        description: Общая статистика безопасности системы
        schema:
          type: object
          properties:
            total_users:
              type: integer
              description: Общее количество пользователей в системе
            blocked_users:
              type: integer
              description: Количество заблокированных пользователей
            high_risk_users:
              type: integer
              description: Пользователи с высоким уровнем риска (7-10)
            medium_risk_users:
              type: integer
              description: Пользователи со средним уровнем риска (4-6)
            low_risk_users:
              type: integer
              description: Пользователи с низким уровнем риска (0-3)
            security_events_24h:
              type: integer
              description: Количество событий безопасности за последние 24 часа
            blocked_requests_24h:
              type: integer
              description: Количество заблокированных запросов за 24 часа
        examples:
          application/json:
            total_users: 1523
            blocked_users: 12
            high_risk_users: 34
            medium_risk_users: 156
            low_risk_users: 1321
            security_events_24h: 145
            blocked_requests_24h: 23
      500:
        description: Ошибка получения статистики безопасности
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "security_status_failed"
            message: "Failed to retrieve security statistics"
    """
    try:
        stats = security_monitor.get_security_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Security status failed: {e}")
        return jsonify({"error": "security_status_failed", "message": str(e)}), 500


@bp.get("/security/user/<user_id>")
def security_user_status(user_id: str):
    """
    Получить состояние безопасности для конкретного пользователя.

    Детальная информация о безопасности пользователя:
    - Оценка риска (0-10)
    - Статус блокировки
    - История активности
    - Обнаруженные подозрительные паттерны

    ---
    tags:
      - Admin
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
        description: Уникальный идентификатор пользователя
        example: "123456789"
    produces:
      - application/json
    responses:
      200:
        description: Состояние безопасности пользователя
        schema:
          type: object
          properties:
            user_id:
              type: string
              description: ID пользователя
            risk_score:
              type: integer
              description: Оценка риска (0-10, где 10 - максимальный риск)
            is_blocked:
              type: boolean
              description: Заблокирован ли пользователь
            risk_level:
              type: string
              enum: [low, medium, high]
              description: Уровень риска (low/medium/high)
            last_activity:
              type: string
              format: date-time
              description: Время последней активности
            total_requests:
              type: integer
              description: Общее количество запросов от пользователя
            failed_requests:
              type: integer
              description: Количество неудачных запросов
            suspicious_patterns:
              type: array
              description: Обнаруженные подозрительные паттерны поведения
              items:
                type: string
        examples:
          application/json:
            user_id: "123456789"
            risk_score: 5
            is_blocked: false
            risk_level: "medium"
            last_activity: "2025-10-09T10:00:00Z"
            total_requests: 156
            failed_requests: 3
            suspicious_patterns: []
      500:
        description: Ошибка получения данных пользователя
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "security_user_status_failed"
            message: "Failed to retrieve user security status"
    """
    try:
        risk_score = security_monitor.get_user_risk_score(user_id)
        is_blocked = security_monitor.is_user_blocked(user_id)

        return jsonify({
            "user_id": user_id,
            "risk_score": risk_score,
            "is_blocked": is_blocked,
            "risk_level": "high" if risk_score > 10 else "medium" if risk_score > 5 else "low"
        })
    except Exception as e:
        logger.error(f"Security user status failed: {e}")
        return jsonify({"error": "security_user_status_failed", "message": str(e)}), 500


@bp.post("/security/user/<user_id>/block")
def security_block_user(user_id: str):
    """
    Заблокировать пользователя вручную.

    Административная блокировка пользователя:
    - Немедленная блокировка всех запросов от пользователя
    - Опциональная причина блокировки для логирования
    - Блокировка действует до ручной разблокировки

    Используйте для блокировки злоумышленников или нарушителей ToS.

    ---
    tags:
      - Admin
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
        description: ID пользователя для блокировки
        example: "123456789"
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            reason:
              type: string
              description: Причина блокировки (опционально, для логов)
              example: "Suspicious activity detected"
          example:
            reason: "Multiple failed security checks"
    produces:
      - application/json
    responses:
      200:
        description: Пользователь успешно заблокирован
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [user_blocked]
            user_id:
              type: string
              description: ID заблокированного пользователя
            reason:
              type: string
              description: Причина блокировки
            blocked_at:
              type: string
              format: date-time
              description: Время блокировки
        examples:
          application/json:
            status: "user_blocked"
            user_id: "123456789"
            reason: "Suspicious activity detected"
            blocked_at: "2025-10-09T10:00:00Z"
      500:
        description: Ошибка блокировки пользователя
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "security_block_user_failed"
            message: "Failed to block user"
    """
    try:
        payload = request.get_json(silent=True) or {}
        reason = payload.get("reason", "Manual block")

        security_monitor.block_user(user_id, reason)
        return jsonify({"status": "user_blocked", "user_id": user_id, "reason": reason})
    except Exception as e:
        logger.error(f"Security block user failed: {e}")
        return jsonify({"error": "security_block_user_failed", "message": str(e)}), 500
