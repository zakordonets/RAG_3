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
    Получить общую статистику качества ответов за период.

    Агрегированные метрики качества из системы RAGAS:
    - Средние оценки RAGAS (faithfulness, relevancy, precision)
    - Комбинированные оценки (RAGAS + пользовательский фидбек)
    - Статистика пользовательского фидбека (👍 / 👎)
    - Процент удовлетворенности пользователей

    Используется для мониторинга качества ответов системы и выявления проблем.

    .. versionadded:: 4.3.0

    ---
    tags:
      - Quality
    parameters:
      - in: query
        name: days
        type: integer
        default: 30
        description: |
          Количество дней для анализа статистики.
          Допустимые значения: 1-365.
        minimum: 1
        maximum: 365
        example: 30
    produces:
      - application/json
    responses:
      200:
        description: Статистика качества за указанный период
        schema:
          type: object
          properties:
            period_days:
              type: integer
              description: Период анализа в днях
            total_interactions:
              type: integer
              description: Общее количество взаимодействий (запросов) за период
            avg_ragas_score:
              type: number
              format: float
              description: Средняя оценка RAGAS (0.0-1.0, где 1.0 - отлично)
            avg_faithfulness:
              type: number
              format: float
              description: Средняя оценка faithfulness - соответствие ответа контексту
            avg_answer_relevancy:
              type: number
              format: float
              description: Средняя оценка answer relevancy - релевантность ответа запросу
            avg_context_precision:
              type: number
              format: float
              description: Средняя оценка context precision - точность выбора контекста
            avg_combined_score:
              type: number
              format: float
              description: Комбинированная оценка (RAGAS + пользовательский фидбек)
            total_feedback:
              type: integer
              description: Общее количество полученного пользовательского фидбека
            positive_feedback:
              type: integer
              description: Количество положительных оценок (👍)
            negative_feedback:
              type: integer
              description: Количество отрицательных оценок (👎)
            satisfaction_rate:
              type: number
              format: float
              description: |
                Процент удовлетворенности (0.0-1.0).
                Рассчитывается как positive / (positive + negative)
        examples:
          application/json:
            period_days: 30
            total_interactions: 1523
            avg_ragas_score: 0.87
            avg_faithfulness: 0.92
            avg_answer_relevancy: 0.88
            avg_context_precision: 0.87
            avg_combined_score: 0.85
            total_feedback: 245
            positive_feedback: 198
            negative_feedback: 47
            satisfaction_rate: 0.808
      400:
        description: Ошибка валидации или качество БД отключена
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [quality_db_disabled, invalid_days]
            message:
              type: string
        examples:
          application/json:
            error: "quality_db_disabled"
            message: "Quality database is disabled"
      500:
        description: Внутренняя ошибка получения статистики
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "internal_error"
            message: "Failed to get quality statistics"
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
    Получить список последних взаимодействий с оценками качества.

    Возвращает детальную информацию о каждом взаимодействии:
    - Запрос и ответ системы
    - RAGAS метрики (faithfulness, relevancy, precision)
    - Пользовательский фидбек (если есть)
    - Комбинированная оценка качества

    Используется для:
    - Анализа качества отдельных ответов
    - Поиска проблемных взаимодействий
    - Корреляции RAGAS и пользовательского фидбека

    .. versionadded:: 4.3.0

    ---
    tags:
      - Quality
    parameters:
      - in: query
        name: limit
        type: integer
        default: 50
        description: |
          Максимальное количество записей для возврата.
          Допустимые значения: 1-1000.
        minimum: 1
        maximum: 1000
        example: 50
      - in: query
        name: offset
        type: integer
        default: 0
        description: Смещение для пагинации (количество записей для пропуска)
        minimum: 0
        example: 0
    produces:
      - application/json
    responses:
      200:
        description: Список взаимодействий с метриками качества
        schema:
          type: object
          properties:
            interactions:
              type: array
              description: Список взаимодействий
              items:
                type: object
                properties:
                  interaction_id:
                    type: string
                    format: uuid
                    description: Уникальный идентификатор взаимодействия
                  query:
                    type: string
                    description: Запрос пользователя
                  response:
                    type: string
                    description: Ответ системы
                  ragas_overall_score:
                    type: number
                    format: float
                    description: Общая оценка RAGAS (0.0-1.0)
                  faithfulness:
                    type: number
                    format: float
                    description: Оценка faithfulness (соответствие контексту)
                  answer_relevancy:
                    type: number
                    format: float
                    description: Оценка relevancy (релевантность ответа)
                  context_precision:
                    type: number
                    format: float
                    description: Оценка precision (точность контекста)
                  user_feedback_type:
                    type: string
                    enum: [positive, negative, null]
                    description: |
                      Тип пользовательского фидбека.
                      null если фидбек не предоставлен.
                  feedback_text:
                    type: string
                    description: Текстовый комментарий пользователя (опционально)
                  combined_score:
                    type: number
                    format: float
                    description: Комбинированная оценка (RAGAS + фидбек)
                  created_at:
                    type: string
                    format: date-time
                    description: Время взаимодействия
                  channel:
                    type: string
                    enum: [telegram, web, api]
                    description: Канал, через который поступил запрос
            total:
              type: integer
              description: Общее количество возвращенных записей
            limit:
              type: integer
              description: Примененный лимит
            offset:
              type: integer
              description: Примененное смещение
        examples:
          application/json:
            interactions:
              - interaction_id: "550e8400-e29b-41d4-a716-446655440000"
                query: "Как настроить маршрутизацию?"
                response: "Для настройки маршрутизации..."
                ragas_overall_score: 0.89
                faithfulness: 0.92
                answer_relevancy: 0.88
                context_precision: 0.87
                user_feedback_type: "positive"
                feedback_text: "Полезный ответ"
                combined_score: 0.91
                created_at: "2025-10-09T10:00:00Z"
                channel: "telegram"
            total: 1
            limit: 50
            offset: 0
      400:
        description: Ошибка валидации или качество БД отключена
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "quality_db_disabled"
            message: "Quality database is disabled"
      500:
        description: Внутренняя ошибка
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "internal_error"
            message: "Failed to get quality interactions"
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
    Получить тренды качества по дням за период.

    Временной ряд метрик качества для анализа динамики:
    - Изменение средних оценок RAGAS по дням
    - Количество взаимодействий по дням
    - Тренды пользовательского фидбека
    - Процент удовлетворенности по дням

    Используется для:
    - Мониторинга изменений качества после обновлений
    - Выявления проблемных периодов
    - Построения графиков в Grafana/дашбордах

    .. versionadded:: 4.3.0

    ---
    tags:
      - Quality
    parameters:
      - in: query
        name: days
        type: integer
        default: 30
        description: |
          Количество дней для анализа трендов.
          Допустимые значения: 1-365.
        minimum: 1
        maximum: 365
        example: 30
    produces:
      - application/json
    responses:
      200:
        description: Тренды качества по дням
        schema:
          type: object
          properties:
            trends:
              type: array
              description: Массив данных по дням (от старых к новым)
              items:
                type: object
                properties:
                  date:
                    type: string
                    format: date
                    description: Дата (ISO 8601 формат)
                  avg_ragas_score:
                    type: number
                    format: float
                    description: Средняя оценка RAGAS за день
                  avg_combined_score:
                    type: number
                    format: float
                    description: Комбинированная оценка за день
                  total_interactions:
                    type: integer
                    description: Количество взаимодействий за день
                  positive_feedback:
                    type: integer
                    description: Количество положительных оценок за день
                  negative_feedback:
                    type: integer
                    description: Количество отрицательных оценок за день
                  satisfaction_rate:
                    type: number
                    format: float
                    description: Процент удовлетворенности за день
            period_days:
              type: integer
              description: Период анализа в днях
        examples:
          application/json:
            trends:
              - date: "2025-10-09"
                avg_ragas_score: 0.87
                avg_combined_score: 0.85
                total_interactions: 45
                positive_feedback: 38
                negative_feedback: 7
                satisfaction_rate: 0.844
              - date: "2025-10-08"
                avg_ragas_score: 0.85
                avg_combined_score: 0.83
                total_interactions: 52
                positive_feedback: 40
                negative_feedback: 12
                satisfaction_rate: 0.769
            period_days: 30
      400:
        description: Ошибка валидации или качество БД отключена
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "quality_db_disabled"
            message: "Quality database is disabled"
      500:
        description: Внутренняя ошибка
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "internal_error"
            message: "Failed to get quality trends"
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
    Получить анализ корреляции между RAGAS метриками и пользовательским фидбеком.

    Статистический анализ взаимосвязи между:
    - Автоматическими оценками RAGAS (ML-based)
    - Реальным пользовательским фидбеком (человеческая оценка)

    Коэффициент корреляции показывает, насколько RAGAS метрики соответствуют
    реальному восприятию качества пользователями.

    Интерпретация коэффициента корреляции:
    - 0.7-1.0: сильная корреляция (RAGAS хорошо предсказывает фидбек)
    - 0.4-0.7: средняя корреляция
    - 0.0-0.4: слабая корреляция (требуется доработка RAGAS)

    .. versionadded:: 4.3.0

    ---
    tags:
      - Quality
    produces:
      - application/json
    responses:
      200:
        description: Анализ корреляции метрик
        schema:
          type: object
          properties:
            correlations:
              type: object
              description: Коэффициенты корреляции для разных метрик
              properties:
                ragas_feedback:
                  type: number
                  format: float
                  description: Корреляция общей RAGAS оценки с фидбеком (-1.0 до 1.0)
                faithfulness_feedback:
                  type: number
                  format: float
                  description: Корреляция faithfulness с фидбеком
                relevancy_feedback:
                  type: number
                  format: float
                  description: Корреляция answer relevancy с фидбеком
                precision_feedback:
                  type: number
                  format: float
                  description: Корреляция context precision с фидбеком
            sample_size:
              type: integer
              description: Количество взаимодействий с фидбеком для анализа
            interpretation:
              type: object
              description: Интерпретация результатов
              properties:
                overall_quality:
                  type: string
                  enum: [strong, moderate, weak]
                  description: Общая оценка корреляции
                recommendations:
                  type: array
                  description: Рекомендации по улучшению
                  items:
                    type: string
        examples:
          application/json:
            correlations:
              ragas_feedback: 0.67
              faithfulness_feedback: 0.72
              relevancy_feedback: 0.65
              precision_feedback: 0.58
            sample_size: 245
            interpretation:
              overall_quality: "moderate"
              recommendations:
                - "Улучшить context precision метрику"
                - "Собрать больше фидбека для точности анализа"
      400:
        description: Ошибка валидации или качество БД отключена
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "quality_db_disabled"
            message: "Quality database is disabled"
      500:
        description: Внутренняя ошибка
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
        examples:
          application/json:
            error: "internal_error"
            message: "Failed to get correlation analysis"
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
    Добавить пользовательский feedback к взаимодействию.

    Сохранение оценки пользователя о качестве ответа:
    - Положительная оценка (👍) - ответ полезный и правильный
    - Отрицательная оценка (👎) - ответ неполный, неточный или бесполезный
    - Опциональный текстовый комментарий

    Фидбек используется для:
    - Корреляционного анализа с RAGAS метриками
    - Выявления проблемных ответов
    - Улучшения промптов и настройки системы
    - Обучения и тюнинга моделей

    .. versionadded:: 4.3.0

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
              format: uuid
              description: |
                UUID взаимодействия из поля interaction_id в ответе /v1/chat/query.
                Должен существовать в базе данных качества.
              example: "550e8400-e29b-41d4-a716-446655440000"
            feedback_type:
              type: string
              enum: [positive, negative]
              description: |
                Тип фидбека:
                - positive: положительная оценка (👍)
                - negative: отрицательная оценка (👎)
              example: "positive"
            feedback_text:
              type: string
              description: |
                Опциональный текстовый комментарий пользователя.
                Полезен для понимания причин негативных оценок.
              maxLength: 1000
              example: "Полезный ответ, спасибо!"
          required:
            - interaction_id
            - feedback_type
          example:
            interaction_id: "550e8400-e29b-41d4-a716-446655440000"
            feedback_type: "positive"
            feedback_text: "Полезный ответ"
    produces:
      - application/json
    responses:
      200:
        description: Feedback успешно сохранен
        schema:
          type: object
          properties:
            message:
              type: string
              description: Сообщение об успехе
            interaction_id:
              type: string
              format: uuid
              description: ID взаимодействия
            feedback_type:
              type: string
              enum: [positive, negative]
              description: Сохраненный тип фидбека
            saved_at:
              type: string
              format: date-time
              description: Время сохранения фидбека
        examples:
          application/json:
            message: "Feedback added successfully"
            interaction_id: "550e8400-e29b-41d4-a716-446655440000"
            feedback_type: "positive"
            saved_at: "2025-10-09T10:00:00Z"
      400:
        description: Ошибка валидации данных
        schema:
          type: object
          properties:
            error:
              type: string
              enum:
                - no_data
                - missing_fields
                - invalid_feedback_type
                - quality_db_disabled
              description: Код ошибки
            message:
              type: string
              description: Описание ошибки
          required: [error, message]
        examples:
          missing_fields:
            error: "missing_fields"
            message: "interaction_id and feedback_type are required"
          invalid_type:
            error: "invalid_feedback_type"
            message: "feedback_type must be 'positive' or 'negative'"
          db_disabled:
            error: "quality_db_disabled"
            message: "Quality database is disabled"
      404:
        description: Взаимодействие с указанным ID не найдено
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [interaction_not_found]
            message:
              type: string
          required: [error, message]
        examples:
          application/json:
            error: "interaction_not_found"
            message: "Interaction with provided ID not found"
      500:
        description: Внутренняя ошибка сохранения фидбека
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [internal_error, failed_to_add_feedback]
            message:
              type: string
          required: [error, message]
        examples:
          application/json:
            error: "failed_to_add_feedback"
            message: "Failed to add feedback"
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
