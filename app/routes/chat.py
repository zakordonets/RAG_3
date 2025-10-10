from __future__ import annotations

from flask import Blueprint, request, jsonify
from loguru import logger
from app.services.infrastructure.orchestrator import handle_query
from app.utils import validate_query_data
from app.infrastructure import validate_request, security_monitor

bp = Blueprint("chat", __name__)


@bp.post("/query")
def chat_query():
    """
    Обработка запросов чата с валидацией и санитизацией.

    Выполняет полный цикл обработки запроса пользователя:
    - Валидация входных данных
    - Проверка безопасности и санитизация
    - Гибридный поиск по базе знаний (dense + sparse)
    - Генерация ответа через LLM с использованием найденного контекста
    - Оценка качества через RAGAS метрики

    .. versionadded:: 4.0.0
    .. versionchanged:: 4.3.0
       Добавлены поля interaction_id, security_warnings, auto_merged для источников

    ---
    tags:
      - Chat
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            message:
              type: string
              description: Текст запроса пользователя (максимум 10000 символов)
              minLength: 1
              maxLength: 10000
              example: "Как настроить маршрутизацию обращений в edna Chat Center?"
            channel:
              type: string
              enum: [telegram, web, api]
              default: telegram
              description: Канал, через который поступил запрос (влияет на rate limiting)
              example: "telegram"
            chat_id:
              type: string
              description: Уникальный идентификатор чата/пользователя для rate limiting и аналитики
              example: "123456789"
          required: [message, channel, chat_id]
          example:
            message: "Как настроить маршрутизацию?"
            channel: "telegram"
            chat_id: "123456789"
    responses:
      200:
        description: Успешный ответ с результатами обработки запроса
        schema:
          type: object
          properties:
            answer:
              type: string
              deprecated: true
              description: |
                (УСТАРЕЛО) Ответ в plain text формате.
                Используйте answer_markdown для получения форматированного ответа.
            answer_markdown:
              type: string
              description: |
                Ответ системы в формате Markdown с форматированием.
                Может содержать заголовки (###), списки (-), нумерацию (1.), код (```).
              example: |
                ### Настройка маршрутизации

                Для настройки маршрутизации обращений в edna Chat Center:

                1. Откройте раздел **Настройки** → **Маршрутизация**
                2. Создайте новое правило маршрутизации
                3. Укажите условия и назначьте группу агентов
            sources:
              type: array
              description: Список источников информации из базы знаний, использованных для генерации ответа
              items:
                type: object
                properties:
                  title:
                    type: string
                    description: Заголовок документа-источника
                    example: "Настройка маршрутизации"
                  url:
                    type: string
                    description: Ссылка на полный документ в документации
                    example: "https://docs-chatcenter.edna.ru/docs/admin/routing/"
                  auto_merged:
                    type: boolean
                    description: |
                      Флаг автоматического объединения соседних чанков (Auto-Merge feature).
                      True если контекст был расширен за счет объединения чанков.
                    example: true
                  merged_chunk_count:
                    type: integer
                    description: Количество чанков, объединенных в один контекст
                    example: 3
                  chunk_span:
                    type: object
                    description: Диапазон объединенных чанков в документе
                    properties:
                      start:
                        type: integer
                        description: Индекс начального чанка
                      end:
                        type: integer
                        description: Индекс конечного чанка
                    example:
                      start: 2
                      end: 4
            meta:
              type: object
              description: Метаданные о генерации ответа (LLM провайдер, модель, токены)
              properties:
                llm_provider:
                  type: string
                  description: Использованный LLM провайдер
                  example: "yandex"
                model:
                  type: string
                  description: Название модели LLM
                  example: "yandexgpt/rc"
                total_tokens:
                  type: integer
                  description: Общее количество использованных токенов
                  example: 450
            channel:
              type: string
              description: Канал запроса (копия из запроса)
              example: "telegram"
            chat_id:
              type: string
              description: ID чата (копия из запроса)
              example: "123456789"
            processing_time:
              type: number
              format: float
              description: Время обработки запроса в секундах
              example: 2.34
            request_id:
              type: string
              description: Уникальный идентификатор запроса для трейсинга
              example: "req_abc123xyz"
            interaction_id:
              type: string
              format: uuid
              description: |
                UUID взаимодействия для системы оценки качества RAGAS.
                Используйте этот ID для отправки пользовательского фидбека через /v1/admin/quality/feedback
              example: "550e8400-e29b-41d4-a716-446655440000"
            security_warnings:
              type: array
              description: |
                Список предупреждений безопасности (если обнаружены подозрительные паттерны).
                Пустой массив если запрос безопасен.
              items:
                type: string
              example: []
        examples:
          application/json:
            answer_markdown: |
              ### Настройка маршрутизации

              Для настройки маршрутизации обращений:

              1. Откройте **Настройки** → **Маршрутизация**
              2. Создайте новое правило
              3. Настройте условия и назначьте группу
            sources:
              - title: "Настройка маршрутизации"
                url: "https://docs-chatcenter.edna.ru/docs/admin/routing/"
                auto_merged: true
                merged_chunk_count: 3
                chunk_span:
                  start: 2
                  end: 4
            meta:
              llm_provider: "yandex"
              model: "yandexgpt/rc"
              total_tokens: 450
            channel: "telegram"
            chat_id: "123456789"
            processing_time: 2.34
            request_id: "req_abc123"
            interaction_id: "550e8400-e29b-41d4-a716-446655440000"
            security_warnings: []
      400:
        description: Ошибка валидации входных данных или проверки безопасности
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [validation_failed, security_validation_failed]
              description: Код ошибки
            message:
              type: string
              description: Человекочитаемое описание ошибки
            details:
              type: object
              description: Детальная информация об ошибках валидации
          required: [error, message]
        examples:
          validation_error:
            error: "validation_failed"
            message: "Некорректные данные запроса"
            details:
              message: ["Field is required"]
          security_error:
            error: "security_validation_failed"
            message: "Запрос не прошел проверку безопасности"
            details:
              warnings: ["Suspicious pattern detected"]
      429:
        description: Превышен лимит запросов (rate limit)
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [rate_limit_exceeded]
            message:
              type: string
            retry_after:
              type: integer
              description: Количество секунд до следующей попытки
        examples:
          rate_limit:
            error: "rate_limit_exceeded"
            message: "Слишком много запросов. Попробуйте позже."
            retry_after: 60
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            error:
              type: string
              enum: [internal_error, llm_unavailable, embedding_error, search_error]
            message:
              type: string
          required: [error, message]
        examples:
          internal:
            error: "internal_error"
            message: "Внутренняя ошибка сервера. Попробуйте позже."
    """
    try:
        # Получение и валидация данных
        payload = request.get_json(silent=True) or {}
        validated_data, errors = validate_query_data(payload)

        if errors:
            logger.warning(f"Validation errors: {errors}")
            return jsonify({
                "error": "validation_failed",
                "message": "Некорректные данные запроса",
                "details": errors
            }), 400

        # Дополнительная проверка безопасности
        user_id = validated_data.get("chat_id", "unknown")
        security_result = validate_request(
            user_id=user_id,
            message=validated_data["message"],
            channel=validated_data["channel"],
            chat_id=validated_data["chat_id"]
        )

        if not security_result["is_valid"]:
            logger.warning(f"Security validation failed for user {user_id}: {security_result['errors']}")
            return jsonify({
                "error": "security_validation_failed",
                "message": "Запрос не прошел проверку безопасности",
                "details": security_result["errors"]
            }), 400

        # Используем санитизированное сообщение
        sanitized_message = security_result["sanitized_message"]

        # Обработка запроса
        result = handle_query(
            channel=validated_data["channel"],
            chat_id=validated_data["chat_id"],
            message=sanitized_message
        )

        # Добавляем метаданные запроса
        result["request_id"] = request.headers.get("X-Request-ID", "unknown")
        result["security_warnings"] = security_result.get("warnings", [])

        return jsonify(result)

    except Exception as e:
        logger.error(f"Unexpected error in chat_query: {e}", exc_info=True)
        return jsonify({
            "error": "internal_error",
            "message": "Внутренняя ошибка сервера. Попробуйте позже."
        }), 500
