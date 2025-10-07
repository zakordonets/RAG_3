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
    """Запуск переиндексации документации.

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
              description: Принудительная полная переиндексация
              default: false
    responses:
      200:
        description: Запуск индексирования
      500:
        description: Ошибка переиндексации
    """
    try:
        force_full = bool((request.get_json(silent=True) or {}).get("force_full", False))
        
        # Используем новую единую функцию индексации
        from app.config.app_config import CONFIG
        config = {
            "docs_root": CONFIG.docs_root,
            "site_base_url": CONFIG.site_base_url,
            "site_docs_prefix": CONFIG.site_docs_prefix,
            "collection_name": CONFIG.qdrant_collection
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
    """Проверка состояния системы.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Состояние системы
      500:
        description: Ошибка
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
    """Получить метрики Prometheus.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Метрики
      500:
        description: Ошибка
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
    """Получить состояние Rate Limiter.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Статистика Rate Limiter
      500:
        description: Ошибка
    """
    try:
        stats = rate_limiter.get_all_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Rate limiter status failed: {e}")
        return jsonify({"error": "rate_limiter_status_failed", "message": str(e)}), 500


@bp.get("/rate-limiter/<user_id>")
def rate_limiter_user_status(user_id: str):
    """Получить состояние Rate Limiter для конкретного пользователя.

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
        description: Статистика пользователя
      500:
        description: Ошибка
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
    """Получить состояние системы безопасности.

    ---
    tags:
      - Admin
    responses:
      200:
        description: Статистика безопасности
      500:
        description: Ошибка
    """
    try:
        stats = security_monitor.get_security_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Security status failed: {e}")
        return jsonify({"error": "security_status_failed", "message": str(e)}), 500


@bp.get("/security/user/<user_id>")
def security_user_status(user_id: str):
    """Получить состояние безопасности для конкретного пользователя.

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
        description: Состояние пользователя
      500:
        description: Ошибка
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
    """Заблокировать пользователя.

    ---
    tags:
      - Admin
    parameters:
      - in: path
        name: user_id
        type: string
        required: true
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            reason:
              type: string
              description: Причина блокировки
    responses:
      200:
        description: Пользователь заблокирован
      500:
        description: Ошибка
    """
    try:
        payload = request.get_json(silent=True) or {}
        reason = payload.get("reason", "Manual block")

        security_monitor.block_user(user_id, reason)
        return jsonify({"status": "user_blocked", "user_id": user_id, "reason": reason})
    except Exception as e:
        logger.error(f"Security block user failed: {e}")
        return jsonify({"error": "security_block_user_failed", "message": str(e)}), 500
