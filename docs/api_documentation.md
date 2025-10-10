# API Документация

## 📚 Обзор

RAG-система предоставляет автоматически генерируемую OpenAPI/Swagger документацию для всех API endpoints. Документация доступна в интерактивном формате через Swagger UI и в виде JSON спецификации.

**Версия API:** v4.3.0

## 🔗 Доступ к документации

### Swagger UI (Интерактивная документация) ✅

```
http://localhost:9000/apidocs
```

**Возможности Swagger UI:**
- 📖 Интерактивное изучение всех endpoints
- 🧪 Тестирование API прямо в браузере
- 📝 Автоматически сгенерированные схемы запросов/ответов
- 🔍 Поиск по endpoints и операциям
- 💡 Примеры запросов и ответов

### OpenAPI 2.0 Спецификация (JSON)

```
http://localhost:9000/apispec_1.json
```

**Использование:**
- Импорт в Postman для создания коллекции
- Генерация клиентских SDK
- Интеграция с другими инструментами API

## 🏗️ Структура API

### Базовый URL
```
http://localhost:9000
```

### Теги (Tags)

API endpoints сгруппированы по функциональности:

#### 📱 Chat (1 endpoint)
Основные функции чата и обработки запросов пользователей

#### ⚙️ Admin (14 endpoints)
Административные функции: здоровье системы, переиндексация, метрики, Circuit Breakers, кэш, rate limiting, безопасность

#### 🎯 Quality (5 endpoints)
Система оценки качества с RAGAS метриками и пользовательским фидбеком

**Всего: 20 endpoints**

## 📝 Основные Endpoints

### POST /v1/chat/query

**Описание**: Обработка запросов чата с валидацией и санитизацией

**Тело запроса**:
```json
{
  "message": "Текст запроса",
  "channel": "telegram|web|api",
  "chat_id": "ID чата"
}
```

**Ответ (200)**:
```json
{
  "answer": "Ответ системы (deprecated - используйте answer_markdown)",
  "answer_markdown": "Ответ в формате Markdown",
  "sources": [
    {
      "title": "Название источника",
      "url": "https://example.com",
      "auto_merged": true,
      "merged_chunk_count": 3,
      "chunk_span": {
        "start": 2,
        "end": 4
      }
    }
  ],
  "channel": "telegram",
  "chat_id": "123456789",
  "processing_time": 1.23,
  "request_id": "req_123",
  "interaction_id": "uuid",
  "security_warnings": []
}
```

**Новые поля v4.3.0:**
- `answer_markdown` - ответ в Markdown (рекомендуется использовать вместо `answer`)
- `interaction_id` - UUID для системы качества RAGAS
- `security_warnings` - массив предупреждений безопасности
- `auto_merged`, `merged_chunk_count`, `chunk_span` - метаданные Auto-Merge feature

**Примечание**: С версии 4.3.0 источники могут содержать дополнительные поля `auto_merged`, `merged_chunk_count`, и `chunk_span`, которые указывают на автоматическое объединение соседних чанков документа. См. [AUTO_MERGE.md](./AUTO_MERGE.md) для подробностей.

**Ошибки**:
- `400` - Ошибка валидации или безопасности
- `500` - Внутренняя ошибка сервера

### Admin Endpoints

#### POST /v1/admin/reindex

**Описание**: Запуск переиндексации документации

**Тело запроса** (опционально):
```json
{
  "force_full": false
}
```

**Ответ**:
```json
{
  "status": "done",
  "force_full": false,
  "total_docs": 156,
  "processed_docs": 156,
  "failed_docs": 0
}
```

#### GET /v1/admin/health

**Описание**: Проверка состояния системы

**Ответ**:
```json
{
  "status": "ok",
  "circuit_breakers": {
    "llm_service": {"state": "closed", "failure_count": 0},
    "embedding_service": {"state": "closed", "failure_count": 0},
    "qdrant_service": {"state": "closed", "failure_count": 0},
    "sparse_service": {"state": "closed", "failure_count": 0}
  },
  "cache": {
    "redis_available": true,
    "stats": {...}
  }
}
```

#### GET /v1/admin/metrics

**Описание**: Получение метрик Prometheus в JSON формате

**Ответ**:
```json
{
  "queries_total": 1523,
  "queries_by_channel": {
    "telegram": 1200,
    "web": 323
  },
  "avg_query_duration": 2.34,
  "cache_hit_rate": 0.45,
  "errors_total": 12
}
```

#### GET /v1/admin/metrics/raw

**Описание**: Сырые метрики Prometheus в текстовом формате для экспорта

**Content-Type**: `text/plain`

#### POST /v1/admin/metrics/reset

**Описание**: Сброс всех метрик (только для тестирования)

⚠️ **Внимание**: Используйте только в тестовой среде!

#### GET /v1/admin/circuit-breakers

**Описание**: Состояние всех Circuit Breakers

**Ответ**:
```json
{
  "llm_service": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null
  },
  "embedding_service": {...},
  "qdrant_service": {...},
  "sparse_service": {...}
}
```

#### POST /v1/admin/circuit-breakers/reset

**Описание**: Сброс всех Circuit Breakers (переводит в состояние closed)

#### GET /v1/admin/cache

**Описание**: Статистика кэша (Redis + in-memory)

**Ответ**:
```json
{
  "redis_available": true,
  "stats": {
    "hits": 1523,
    "misses": 456,
    "hit_rate": 0.77,
    "size": 1200
  }
}
```

#### Rate Limiting Endpoints

##### GET /v1/admin/rate-limiter

**Описание**: Глобальное состояние Rate Limiter

**Ответ**:
```json
{
  "total_users": 245,
  "blocked_users": 3,
  "limits": {
    "requests_per_window": 10,
    "window_seconds": 300,
    "burst_limit": 3,
    "burst_window_seconds": 60
  }
}
```

##### GET /v1/admin/rate-limiter/{user_id}

**Описание**: Состояние Rate Limiter для конкретного пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

**Ответ**:
```json
{
  "user_id": "123456789",
  "requests_count": 5,
  "window_start": "2025-10-09T10:00:00Z",
  "is_limited": false,
  "remaining": 5
}
```

##### POST /v1/admin/rate-limiter/{user_id}/reset

**Описание**: Сброс лимитов для конкретного пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

#### Security Endpoints

##### GET /v1/admin/security

**Описание**: Общая статистика безопасности

**Ответ**:
```json
{
  "total_users": 1523,
  "blocked_users": 12,
  "high_risk_users": 34,
  "security_events_24h": 145
}
```

##### GET /v1/admin/security/user/{user_id}

**Описание**: Состояние безопасности для конкретного пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

**Ответ**:
```json
{
  "user_id": "123456789",
  "risk_score": 5,
  "is_blocked": false,
  "risk_level": "medium",
  "last_activity": "2025-10-09T10:00:00Z",
  "total_requests": 156
}
```

##### POST /v1/admin/security/user/{user_id}/block

**Описание**: Блокировка пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

**Тело запроса** (опционально):
```json
{
  "reason": "Причина блокировки"
}
```

### Quality API Endpoints (v4.3.0+)

Система оценки качества с RAGAS метриками.

#### GET /v1/admin/quality/stats

**Описание**: Статистика качества ответов за период

**Parameters**:
- `days` (integer, optional): Количество дней для анализа (default: 30)

**Ответ**:
```json
{
  "period_days": 30,
  "total_interactions": 1523,
  "avg_ragas_score": 0.87,
  "avg_combined_score": 0.85,
  "total_feedback": 245,
  "positive_feedback": 198,
  "negative_feedback": 47,
  "satisfaction_rate": 0.808
}
```

#### GET /v1/admin/quality/interactions

**Описание**: Список взаимодействий с оценками качества

**Parameters**:
- `limit` (integer, optional): Лимит записей (default: 100)
- `offset` (integer, optional): Смещение (default: 0)

**Ответ**:
```json
{
  "interactions": [
    {
      "interaction_id": "uuid",
      "query": "Как настроить маршрутизацию?",
      "answer": "Для настройки...",
      "ragas_score": 0.89,
      "faithfulness": 0.92,
      "answer_relevancy": 0.88,
      "context_precision": 0.87,
      "feedback_score": 1,
      "created_at": "2025-10-09T10:00:00Z"
    }
  ],
  "total": 1523,
  "limit": 100,
  "offset": 0
}
```

#### GET /v1/admin/quality/trends

**Описание**: Тренды качества по дням

**Parameters**:
- `days` (integer, optional): Количество дней (default: 30)

**Ответ**:
```json
{
  "trends": [
    {
      "date": "2025-10-09",
      "avg_score": 0.87,
      "interactions_count": 45,
      "positive_feedback": 38,
      "negative_feedback": 7
    }
  ]
}
```

#### GET /v1/admin/quality/correlation

**Описание**: Корреляция между метриками качества

**Ответ**:
```json
{
  "correlations": {
    "ragas_feedback": 0.67,
    "faithfulness_feedback": 0.72,
    "relevancy_feedback": 0.65
  }
}
```

#### POST /v1/admin/quality/feedback

**Описание**: Сохранение пользовательского фидбека

**Тело запроса**:
```json
{
  "interaction_id": "uuid",
  "feedback_score": 1,
  "feedback_text": "Опциональный комментарий"
}
```

**feedback_score values**:
- `1` - положительный отзыв (👍)
- `-1` - отрицательный отзыв (👎)

**Ответ**:
```json
{
  "status": "success",
  "interaction_id": "uuid",
  "feedback_saved": true
}
```

## 🛠️ Технические детали

### OpenAPI 2.0 (Swagger)

- **Версия**: OpenAPI 2.0 (Swagger 2.0)
- **Генератор**: Flasgger 0.9.7.1
- **Формат**: JSON
- **Кодировка**: UTF-8

### Конфигурация

```python
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "edna Chat Center RAG API",
        "description": "API для RAG-системы технической поддержки",
        "version": "4.3.0"
    },
    "host": "localhost:9000",
    "basePath": "/",
    "schemes": ["http", "https"],
    "tags": [
        {"name": "Chat", "description": "Основные операции чата"},
        {"name": "Admin", "description": "Административные функции"},
        {"name": "Quality", "description": "Система оценки качества (RAGAS)"}
    ]
}
```

### Аннотации в коде

Документация генерируется автоматически из docstring функций с YAML аннотациями:

```python
@bp.post("/query")
def chat_query():
    """
    Обработка запросов чата с валидацией и санитизацией.

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
              description: Текст запроса
            channel:
              type: string
              enum: [telegram, web, api]
              default: telegram
            chat_id:
              type: string
              description: Идентификатор чата/пользователя
          required: [message]
    responses:
      200:
        description: Успешный ответ
      400:
        description: Ошибка валидации или безопасности
      500:
        description: Внутренняя ошибка сервера
    """
```

## 🧪 Тестирование API

### Через Swagger UI

1. Откройте http://localhost:9000/apidocs
2. Выберите endpoint
3. Нажмите "Try it out"
4. Заполните параметры
5. Нажмите "Execute"
6. Просмотрите результаты

### Через curl

```bash
# Тест основного API
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"message": "Как настроить интеграцию?", "channel": "api", "chat_id": "test"}'

# Тест health check
curl http://localhost:9000/v1/admin/health

# Получение метрик
curl http://localhost:9000/v1/admin/metrics

# Quality stats
curl http://localhost:9000/v1/admin/quality/stats?days=7
```

### Через Python

```python
import requests

# Тест основного API
response = requests.post(
    "http://localhost:9000/v1/chat/query",
    json={
        "message": "Как настроить интеграцию?",
        "channel": "api",
        "chat_id": "test"
    }
)
print(response.json())

# Тест health check
response = requests.get("http://localhost:9000/v1/admin/health")
print(response.json())

# Quality stats
response = requests.get("http://localhost:9000/v1/admin/quality/stats?days=7")
print(response.json())
```

### Через Postman

1. Импортируйте OpenAPI спецификацию:
   - File → Import → Link
   - Вставьте: `http://localhost:9000/apispec_1.json`
2. Postman автоматически создаст коллекцию со всеми endpoints
3. Настройте переменные окружения (base_url, etc.)
4. Тестируйте endpoints

## 📊 Мониторинг API

### Метрики Prometheus

Доступны через `/v1/admin/metrics/raw`:

- **rag_queries_total** - количество запросов по каналам и статусам
- **rag_query_duration_seconds** - длительность обработки запросов
- **rag_embedding_duration_seconds** - время создания эмбеддингов
- **rag_search_duration_seconds** - время поиска
- **rag_llm_duration_seconds** - время генерации LLM
- **rag_cache_hits_total** - попадания в кэш
- **rag_errors_total** - количество ошибок по типам
- **rag_quality_score** - оценки качества ответов

### Логирование

- Все API запросы логируются с контекстом
- Ошибки записываются с полным стеком вызовов
- Время обработки каждого этапа
- Security события

### Health Checks

- **GET /v1/admin/health** - общее состояние системы
- **GET /v1/admin/circuit-breakers** - состояние Circuit Breakers
- **GET /v1/admin/cache** - состояние кэша

## 🔒 Безопасность API

### Валидация

- Все входные данные валидируются через Marshmallow схемы
- Проверка типов, форматов и ограничений
- Санитизация HTML и опасных паттернов
- Максимальная длина сообщений: 10000 символов

### Rate Limiting

- Ограничение частоты запросов от пользователей
- 10 запросов в 5 минут (основной лимит)
- 3 запроса в минуту (burst protection)
- Управление через admin API

### Мониторинг безопасности

- Отслеживание подозрительной активности
- Автоматическая блокировка пользователей
- Оценка риска для каждого запроса
- Security warnings в ответах

## 🚀 Развертывание

### Локальная разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск сервера
python wsgi.py

# Доступ к документации
open http://localhost:9000/apidocs
```

### Production

```bash
# Запуск через Gunicorn
gunicorn -w 4 -b 0.0.0.0:9000 wsgi:app

# Доступ к документации
curl http://your-domain.com/apidocs
```

### Docker

```bash
# Запуск через Docker Compose
docker-compose up -d

# Проверка
curl http://localhost:9000/apidocs
```

## 📝 Обновление документации

Документация обновляется автоматически при изменении кода. Для добавления новых endpoints:

1. Добавьте endpoint в соответствующий blueprint
2. Добавьте YAML аннотации в docstring функции
3. Перезапустите сервер
4. Документация обновится автоматически

### Пример добавления нового endpoint

```python
@bp.get("/new-endpoint")
def new_endpoint():
    """
    Описание нового endpoint.

    ---
    tags:
      - Admin
    parameters:
      - in: query
        name: param1
        type: string
        required: false
        description: Описание параметра
    responses:
      200:
        description: Успешный ответ
        schema:
          type: object
          properties:
            status:
              type: string
    """
    return jsonify({"status": "ok"})
```

## 🎯 Лучшие практики

### Использование API

1. **Всегда проверяйте health** перед массовыми операциями
2. **Используйте rate limiting** для предотвращения блокировки
3. **Обрабатывайте ошибки** gracefully (400, 500)
4. **Используйте interaction_id** для отслеживания качества
5. **Отправляйте фидбек** для улучшения системы

### Безопасность

1. **Валидируйте данные** на клиенте перед отправкой
2. **Не отправляйте** sensitive data в запросах
3. **Используйте HTTPS** в production
4. **Мониторьте** security warnings в ответах
5. **Следите** за rate limiting статусом

### Производительность

1. **Кэшируйте** часто запрашиваемые данные
2. **Используйте батчинг** для множественных запросов
3. **Мониторьте** метрики производительности
4. **Оптимизируйте** запросы на основе метрик
5. **Используйте** async/await где возможно

## 🎓 Заключение

Автоматическая генерация OpenAPI документации через Flasgger обеспечивает:

- ✅ **Актуальность** - документация всегда соответствует коду
- ✅ **Интерактивность** - тестирование через Swagger UI
- ✅ **Стандартизацию** - OpenAPI 2.0 совместимость
- ✅ **Удобство** - автоматическое обновление при изменениях
- ✅ **Полноту** - все 20 endpoints с детальными схемами
- ✅ **Качество** - RAGAS система с метриками и фидбеком

API документация готова к использованию разработчиками и интеграторами! 🚀

---

**Последнее обновление**: Октябрь 2025
**Версия API**: v4.3.0
**Swagger UI**: ✅ Доступен
**Endpoints**: 20 (Chat: 1, Admin: 14, Quality: 5)
