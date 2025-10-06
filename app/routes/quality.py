"""
API endpoints для системы оценки качества RAGAS
"""
from __future__ import annotations

from flask import Blueprint, request, jsonify
from loguru import logger
import asyncio
from app.services.quality.quality_manager import quality_manager
from app.config import CONFIG

bp = Blueprint("quality", __name__)


@bp.get("/stats")
def get_quality_stats():
    """
    Получить общую статистику качества за период

    ---
    tags:
      - Quality
    parameters:
      - in: query
        name: days
        type: integer
        default: 30
        description: Количество дней для анализа
    responses:
      200:
        description: Статистика качества
        schema:
          type: object
          properties:
            period_days:
              type: integer
            total_interactions:
              type: integer
            avg_ragas_score:
              type: number
            avg_combined_score:
              type: number
            total_feedback:
              type: integer
            positive_feedback:
              type: integer
            negative_feedback:
              type: integer
            satisfaction_rate:
              type: number
    """
    try:
        days = request.args.get('days', 30, type=int)

        if not CONFIG.quality_db_enabled:
            return jsonify({
                "error": "quality_db_disabled",
                "message": "Quality database is disabled"
            }), 400

        stats = asyncio.run(quality_manager.get_quality_statistics(days=days))

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting quality stats: {e}")
        return jsonify({
            "error": "internal_error",
            "message": "Failed to get quality statistics"
        }), 500


@bp.get("/interactions")
def get_quality_interactions():
    """
    Получить последние quality interactions

    ---
    tags:
      - Quality
    parameters:
      - in: query
        name: limit
        type: integer
        default: 50
        description: Максимальное количество записей
    responses:
      200:
        description: Список interactions
        schema:
          type: object
          properties:
            interactions:
              type: array
              items:
                type: object
                properties:
                  interaction_id:
                    type: string
                  query:
                    type: string
                  response:
                    type: string
                  ragas_overall_score:
                    type: number
                  user_feedback_type:
                    type: string
                  combined_score:
                    type: number
                  created_at:
                    type: string
    """
    try:
        limit = request.args.get('limit', 50, type=int)

        if not CONFIG.quality_db_enabled:
            return jsonify({
                "error": "quality_db_disabled",
                "message": "Quality database is disabled"
            }), 400

        interactions = asyncio.run(quality_manager.get_recent_interactions(limit=limit))

        return jsonify({
            "interactions": interactions,
            "total": len(interactions)
        })

    except Exception as e:
        logger.error(f"Error getting quality interactions: {e}")
        return jsonify({
            "error": "internal_error",
            "message": "Failed to get quality interactions"
        }), 500


@bp.get("/trends")
def get_quality_trends():
    """
    Получить тренды качества за период

    ---
    tags:
      - Quality
    parameters:
      - in: query
        name: days
        type: integer
        default: 30
        description: Количество дней для анализа
    responses:
      200:
        description: Тренды качества
        schema:
          type: object
          properties:
            trends:
              type: array
              items:
                type: object
                properties:
                  date:
                    type: string
                  avg_ragas_score:
                    type: number
                  avg_combined_score:
                    type: number
                  total_interactions:
                    type: integer
                  satisfaction_rate:
                    type: number
    """
    try:
        days = request.args.get('days', 30, type=int)

        if not CONFIG.quality_db_enabled:
            return jsonify({
                "error": "quality_db_disabled",
                "message": "Quality database is disabled"
            }), 400

        trends = asyncio.run(quality_manager.get_quality_trends(days=days))

        return jsonify({
            "trends": trends,
            "period_days": days
        })

    except Exception as e:
        logger.error(f"Error getting quality trends: {e}")
        return jsonify({
            "error": "internal_error",
            "message": "Failed to get quality trends"
        }), 500


@bp.get("/correlation")
def get_correlation_analysis():
    """
    Получить анализ корреляции между RAGAS и пользовательским фидбеком

    ---
    tags:
      - Quality
    responses:
      200:
        description: Анализ корреляции
        schema:
          type: object
          properties:
            correlation_coefficient:
              type: number
            total_comparisons:
              type: integer
            accuracy_breakdown:
              type: object
              properties:
                positive_predictions:
                  type: integer
                negative_predictions:
                  type: integer
                correct_predictions:
                  type: integer
    """
    try:
        if not CONFIG.quality_db_enabled:
            return jsonify({
                "error": "quality_db_disabled",
                "message": "Quality database is disabled"
            }), 400

        correlation = asyncio.run(quality_manager.get_correlation_analysis())

        return jsonify(correlation)

    except Exception as e:
        logger.error(f"Error getting correlation analysis: {e}")
        return jsonify({
            "error": "internal_error",
            "message": "Failed to get correlation analysis"
        }), 500


@bp.post("/feedback")
def add_feedback():
    """
    Добавить пользовательский feedback к interaction

    ---
    tags:
      - Quality
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            interaction_id:
              type: string
            feedback_type:
              type: string
              enum: [positive, negative]
            feedback_text:
              type: string
          required: [interaction_id, feedback_type]
    responses:
      200:
        description: Feedback добавлен
      400:
        description: Ошибка валидации
      500:
        description: Внутренняя ошибка
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "no_data",
                "message": "No data provided"
            }), 400

        interaction_id = data.get("interaction_id")
        feedback_type = data.get("feedback_type")
        feedback_text = data.get("feedback_text", "")

        if not interaction_id or not feedback_type:
            return jsonify({
                "error": "missing_fields",
                "message": "interaction_id and feedback_type are required"
            }), 400

        if feedback_type not in ["positive", "negative"]:
            return jsonify({
                "error": "invalid_feedback_type",
                "message": "feedback_type must be 'positive' or 'negative'"
            }), 400

        if not CONFIG.quality_db_enabled:
            return jsonify({
                "error": "quality_db_disabled",
                "message": "Quality database is disabled"
            }), 400

        success = asyncio.run(quality_manager.add_user_feedback(
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            feedback_text=feedback_text
        ))

        if success:
            return jsonify({
                "message": "Feedback added successfully",
                "interaction_id": interaction_id
            })
        else:
            return jsonify({
                "error": "failed_to_add_feedback",
                "message": "Failed to add feedback"
            }), 500

    except Exception as e:
        logger.error(f"Error adding feedback: {e}")
        return jsonify({
            "error": "internal_error",
            "message": "Failed to add feedback"
        }), 500
