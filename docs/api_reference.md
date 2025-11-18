# API Reference (v4.3.0)

Полный справочник API для RAG-системы edna Chat Center.

## 📚 Навигация

- [Обзор](#обзор)
- [Chat API](#chat-api)
- [Admin API](#admin-api)
- [Quality API](#quality-api)
- [Error Handling](#error-handling)
- [SDK Examples](#sdk-examples)

## Обзор

### Base URL
```
http://localhost:9000
```

### Swagger UI
```
http://localhost:9000/apidocs
```

### OpenAPI Specification
```
http://localhost:9000/apispec_1.json
```

### Версия
**v4.3.0** (Октябрь 2025)

### Аутентификация
В текущей версии аутентификация не требуется. В production рекомендуется добавить API ключи или JWT токены.

### Endpoints Summary

| Категория | Количество | Описание |
|-----------|------------|----------|
| **Chat** | 1 | Обработка пользовательских запросов |
| **Admin** | 14 | Администрирование системы |
| **Quality** | 5 | Оценка качества (RAGAS) |
| **Всего** | **20** | |

## Chat API

### POST /v1/chat/query

Обрабатывает запросы пользователей и возвращает ответы на основе документации.

#### Request

```http
POST /v1/chat/query
Content-Type: application/json
```

**Body:**
```json
{
  "channel": "telegram",
  "chat_id": "123456789",
  "message": "Как настроить маршрутизацию?"
}
```

**Parameters:**
- `channel` (string, required): Канал связи (`telegram`, `web`, `api`)
- `chat_id` (string, required): Уникальный идентификатор чата
- `message` (string, required): Текст запроса пользователя (max 10000 символов)

#### Response

**Success (200 OK):**
```json
{
  "answer": "Для настройки маршрутизации...",
  "answer_markdown": "🔧 **Настройка маршрутизации**\n\nДля настройки...",
  "sources": [
    {
      "title": "Настройка маршрутизации",
      "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/",
      "auto_merged": true,
      "merged_chunk_count": 3,
      "chunk_span": {"start": 2, "end": 4}
    }
  ],
  "meta": {
    "llm_provider": "yandex",
    "model": "yandexgpt/rc",
    "total_tokens": 450
  },
  "channel": "telegram",
  "chat_id": "123456789",
  "processing_time": 2.34,
  "request_id": "req_abc123",
  "interaction_id": "uuid-1234",
  "security_warnings": []
}
```

**Response Fields:**

- `answer` (string, **deprecated**): Устаревший ключ, используйте `answer_markdown`
- `answer_markdown` (string): Ответ в формате Markdown
- `sources` (array): Список источников информации
  - `title` (string): Заголовок источника
  - `url` (string): URL документации
  - `auto_merged` (boolean, optional): Чанк был автоматически объединен
  - `merged_chunk_count` (integer, optional): Количество объединенных чанков
  - `chunk_span` (object, optional): Диапазон объединенных чанков
- `meta` (object): Метаданные генерации (LLM, модель, токены)
- `channel` (string): Канал запроса
- `chat_id` (string): ID чата
- `processing_time` (number): Время обработки в секундах
- `request_id` (string): Уникальный ID запроса
- `interaction_id` (string): ID для системы качества RAGAS
- `security_warnings` (array): Предупреждения безопасности

**Error (400 Bad Request):**
```json
{
  "error": "validation_failed",
  "message": "Некорректные данные запроса",
  "details": {
    "message": ["Field is required"]
  }
}
```

**Error (500 Internal Server Error):**
```json
{
  "error": "internal_error",
  "message": "Internal server error"
}
```

## Admin API

### POST /v1/admin/reindex

Запускает переиндексацию документации.

#### Request

```http
POST /v1/admin/reindex
Content-Type: application/json
```

**Body (optional):**
```json
{
  "force_full": false
}
```

**Parameters:**
- `force_full` (boolean, optional): Принудительная полная переиндексация (default: false)

#### Response

**Success (200 OK):**
```json
{
  "status": "done",
  "force_full": false,
  "total_docs": 156,
  "processed_docs": 156,
  "failed_docs": 0,
  "duration": 245.32
}
```

**Error (500 Internal Server Error):**
```json
{
  "error": "reindex_failed",
  "message": "Error message"
}
```

---

### GET /v1/admin/health

Проверяет состояние системы и доступность всех компонентов.

#### Request

```http
GET /v1/admin/health
```

#### Response

**Success (200 OK):**
```json
{
  "status": "ok",
  "circuit_breakers": {
    "llm_service": {
      "state": "closed",
      "failure_count": 0
    },
    "embedding_service": {
      "state": "closed",
      "failure_count": 0
    },
    "qdrant_service": {
      "state": "closed",
      "failure_count": 0
    }
  },
  "cache": {
    "redis_available": true,
    "stats": {
      "hits": 1523,
      "misses": 456
    }
  }
}
```

---

### GET /v1/admin/metrics

Получение метрик Prometheus в JSON формате.

#### Request

```http
GET /v1/admin/metrics
```

#### Response

**Success (200 OK):**
```json
{
  "queries_total": 1523,
  "queries_by_channel": {
    "telegram": 1200,
    "web": 323
  },
  "queries_by_status": {
    "success": 1450,
    "error": 73
  },
  "avg_query_duration": 2.34,
  "avg_embedding_duration": 0.45,
  "avg_search_duration": 0.23,
  "avg_llm_duration": 1.56,
  "cache_hit_rate": 0.67,
  "errors_total": 73
}
```

---

### GET /v1/admin/metrics/raw

Сырые метрики Prometheus в текстовом формате для экспорта.

#### Request

```http
GET /v1/admin/metrics/raw
```

#### Response

**Content-Type**: `text/plain; version=0.0.4`

```
# HELP rag_queries_total Total number of queries
# TYPE rag_queries_total counter
rag_queries_total{channel="telegram",status="success"} 1200.0
rag_queries_total{channel="web",status="success"} 323.0

# HELP rag_query_duration_seconds Query processing duration
# TYPE rag_query_duration_seconds histogram
...
```

---

### POST /v1/admin/metrics/reset

Сброс всех метрик (только для тестирования).

⚠️ **Внимание**: Используйте только в тестовой среде!

#### Request

```http
POST /v1/admin/metrics/reset
```

#### Response

**Success (200 OK):**
```json
{
  "status": "metrics_reset",
  "message": "All metrics have been reset"
}
```

---

### GET /v1/admin/circuit-breakers

Состояние всех Circuit Breakers.

#### Request

```http
GET /v1/admin/circuit-breakers
```

#### Response

**Success (200 OK):**
```json
{
  "llm_service": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null,
    "threshold": 3,
    "timeout": 30
  },
  "embedding_service": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null,
    "threshold": 5,
    "timeout": 60
  },
  "qdrant_service": {...}
}
```

**States:**
- `closed` - нормальная работа
- `open` - сервис недоступен, запросы блокируются
- `half_open` - тестирование восстановления

---

### POST /v1/admin/circuit-breakers/reset

Сброс всех Circuit Breakers (переводит в состояние closed).

#### Request

```http
POST /v1/admin/circuit-breakers/reset
```

#### Response

**Success (200 OK):**
```json
{
  "status": "circuit_breakers_reset",
  "message": "All circuit breakers have been reset to closed state"
}
```

---

### GET /v1/admin/cache

Статистика кэша (Redis + in-memory).

#### Request

```http
GET /v1/admin/cache
```

#### Response

**Success (200 OK):**
```json
{
  "redis_available": true,
  "stats": {
    "hits": 1523,
    "misses": 456,
    "hit_rate": 0.77,
    "size": 1200,
    "memory_usage": "45.6 MB"
  }
}
```

---

### GET /v1/admin/rate-limiter

Глобальное состояние Rate Limiter.

#### Request

```http
GET /v1/admin/rate-limiter
```

#### Response

**Success (200 OK):**
```json
{
  "total_users": 245,
  "blocked_users": 3,
  "limits": {
    "requests_per_window": 10,
    "window_seconds": 300,
    "burst_limit": 3,
    "burst_window_seconds": 60
  },
  "active_users_last_hour": 156
}
```

---

### GET /v1/admin/rate-limiter/{user_id}

Состояние Rate Limiter для конкретного пользователя.

#### Request

```http
GET /v1/admin/rate-limiter/{user_id}
```

**Path Parameters:**
- `user_id` (string, required): ID пользователя

#### Response

**Success (200 OK):**
```json
{
  "user_id": "123456789",
  "requests_count": 5,
  "window_start": "2025-10-09T10:00:00Z",
  "is_limited": false,
  "remaining": 5,
  "reset_at": "2025-10-09T10:05:00Z"
}
```

---

### POST /v1/admin/rate-limiter/{user_id}/reset

Сброс лимитов для конкретного пользователя.

#### Request

```http
POST /v1/admin/rate-limiter/{user_id}/reset
```

**Path Parameters:**
- `user_id` (string, required): ID пользователя

#### Response

**Success (200 OK):**
```json
{
  "status": "rate_limit_reset",
  "user_id": "123456789",
  "message": "Rate limit has been reset for user"
}
```

---

### GET /v1/admin/security

Общая статистика безопасности.

#### Request

```http
GET /v1/admin/security
```

#### Response

**Success (200 OK):**
```json
{
  "total_users": 1523,
  "blocked_users": 12,
  "high_risk_users": 34,
  "medium_risk_users": 156,
  "low_risk_users": 1321,
  "security_events_24h": 145,
  "blocked_requests_24h": 23
}
```

---

### GET /v1/admin/security/user/{user_id}

Состояние безопасности для конкретного пользователя.

#### Request

```http
GET /v1/admin/security/user/{user_id}
```

**Path Parameters:**
- `user_id` (string, required): ID пользователя

#### Response

**Success (200 OK):**
```json
{
  "user_id": "123456789",
  "risk_score": 5,
  "is_blocked": false,
  "risk_level": "medium",
  "last_activity": "2025-10-09T10:00:00Z",
  "total_requests": 156,
  "failed_requests": 3,
  "suspicious_patterns": []
}
```

**Risk Levels:**
- `low` (0-3) - нормальная активность
- `medium` (4-6) - повышенное внимание
- `high` (7-10) - подозрительная активность

---

### POST /v1/admin/security/user/{user_id}/block

Блокировка пользователя.

#### Request

```http
POST /v1/admin/security/user/{user_id}/block
Content-Type: application/json
```

**Path Parameters:**
- `user_id` (string, required): ID пользователя

**Body (optional):**
```json
{
  "reason": "Suspicious activity detected"
}
```

#### Response

**Success (200 OK):**
```json
{
  "status": "user_blocked",
  "user_id": "123456789",
  "reason": "Suspicious activity detected",
  "blocked_at": "2025-10-09T10:00:00Z"
}
```

## Quality API

### GET /v1/admin/quality/stats

Статистика качества ответов за период.

#### Request

```http
GET /v1/admin/quality/stats?days=30
```

**Query Parameters:**
- `days` (integer, optional): Количество дней для анализа (default: 30)

#### Response

**Success (200 OK):**
```json
{
  "period_days": 30,
  "total_interactions": 1523,
  "avg_ragas_score": 0.87,
  "avg_faithfulness": 0.92,
  "avg_answer_relevancy": 0.88,
  "avg_context_precision": 0.87,
  "avg_combined_score": 0.85,
  "total_feedback": 245,
  "positive_feedback": 198,
  "negative_feedback": 47,
  "satisfaction_rate": 0.808
}
```

---

### GET /v1/admin/quality/interactions

Список взаимодействий с оценками качества.

#### Request

```http
GET /v1/admin/quality/interactions?limit=100&offset=0
```

**Query Parameters:**
- `limit` (integer, optional): Лимит записей (default: 100, max: 1000)
- `offset` (integer, optional): Смещение (default: 0)

#### Response

**Success (200 OK):**
```json
{
  "interactions": [
    {
      "interaction_id": "uuid-1234",
      "query": "Как настроить маршрутизацию?",
      "answer": "Для настройки маршрутизации...",
      "ragas_score": 0.89,
      "faithfulness": 0.92,
      "answer_relevancy": 0.88,
      "context_precision": 0.87,
      "feedback_score": 1,
      "feedback_text": "Полезный ответ",
      "channel": "telegram",
      "created_at": "2025-10-09T10:00:00Z"
    }
  ],
  "total": 1523,
  "limit": 100,
  "offset": 0
}
```

---

### GET /v1/admin/quality/trends

Тренды качества по дням.

#### Request

```http
GET /v1/admin/quality/trends?days=30
```

**Query Parameters:**
- `days` (integer, optional): Количество дней (default: 30)

#### Response

**Success (200 OK):**
```json
{
  "trends": [
    {
      "date": "2025-10-09",
      "avg_score": 0.87,
      "interactions_count": 45,
      "positive_feedback": 38,
      "negative_feedback": 7,
      "satisfaction_rate": 0.844
    },
    {
      "date": "2025-10-08",
      "avg_score": 0.85,
      "interactions_count": 52,
      "positive_feedback": 40,
      "negative_feedback": 12,
      "satisfaction_rate": 0.769
    }
  ]
}
```

---

### GET /v1/admin/quality/correlation

Корреляция между метриками качества и пользовательским фидбеком.

#### Request

```http
GET /v1/admin/quality/correlation
```

#### Response

**Success (200 OK):**
```json
{
  "correlations": {
    "ragas_feedback": 0.67,
    "faithfulness_feedback": 0.72,
    "relevancy_feedback": 0.65,
    "precision_feedback": 0.58
  },
  "sample_size": 245
}
```

**Интерпретация:**
- `0.7-1.0` - сильная корреляция
- `0.4-0.7` - средняя корреляция
- `0.0-0.4` - слабая корреляция

---

### POST /v1/admin/quality/feedback

Сохранение пользовательского фидбека.

#### Request

```http
POST /v1/admin/quality/feedback
Content-Type: application/json
```

**Body:**
```json
{
  "interaction_id": "uuid-1234",
  "feedback_score": 1,
  "feedback_text": "Полезный ответ, спасибо!"
}
```

**Parameters:**
- `interaction_id` (string, required): UUID взаимодействия
- `feedback_score` (integer, required): Оценка (1 = 👍, -1 = 👎)
- `feedback_text` (string, optional): Комментарий пользователя

#### Response

**Success (200 OK):**
```json
{
  "status": "success",
  "interaction_id": "uuid-1234",
  "feedback_saved": true,
  "timestamp": "2025-10-09T10:00:00Z"
}
```

**Error (404 Not Found):**
```json
{
  "error": "interaction_not_found",
  "message": "Interaction with provided ID not found"
}
```

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource already exists or operation in progress |
| 422 | Unprocessable Entity - Validation error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |
| 503 | Service Unavailable - Service temporarily unavailable |

### Error Response Format

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional error details"
  },
  "timestamp": "2025-10-09T10:00:00Z",
  "request_id": "req_123456789"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `validation_failed` | Invalid request parameters |
| `rate_limit_exceeded` | Too many requests |
| `security_validation_failed` | Request failed security checks |
| `llm_unavailable` | All LLM providers are unavailable |
| `embedding_error` | Embedding generation failed |
| `search_error` | Vector search failed |
| `rerank_error` | Reranking failed |
| `internal_error` | Internal server error |

## Rate Limiting

### Limits

- **Chat API**: 10 requests per 5 minutes per chat_id
- **Burst**: 3 requests per minute per chat_id
- **Admin API**: Unlimited (but monitored)
- **Quality API**: Unlimited (but monitored)

### Headers

Rate limit information is available through admin endpoints:
```bash
GET /v1/admin/rate-limiter/{user_id}
```

### Rate Limit Exceeded Response

**HTTP 429 Too Many Requests:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60,
  "user_id": "123456789"
}
```

## SDK Examples

### Python

```python
import requests

class ChatCenterAPI:
    """Клиент для работы с Chat Center API"""

    def __init__(self, base_url="http://localhost:9000"):
        self.base_url = base_url
        self.session = requests.Session()

    def ask(self, message: str, chat_id: str = "default", channel: str = "api"):
        """Отправить вопрос в RAG систему"""
        response = self.session.post(
            f"{self.base_url}/v1/chat/query",
            json={
                "message": message,
                "channel": channel,
                "chat_id": chat_id
            }
        )
        response.raise_for_status()
        return response.json()

    def health_check(self):
        """Проверить здоровье системы"""
        response = self.session.get(f"{self.base_url}/v1/admin/health")
        response.raise_for_status()
        return response.json()

    def get_quality_stats(self, days: int = 30):
        """Получить статистику качества"""
        response = self.session.get(
            f"{self.base_url}/v1/admin/quality/stats",
            params={"days": days}
        )
        response.raise_for_status()
        return response.json()

# Использование
api = ChatCenterAPI()

# Задать вопрос
result = api.ask("Как настроить маршрутизацию?")
print(result["answer_markdown"])

# Проверить здоровье
health = api.health_check()
print(f"Статус: {health['status']}")

# Получить статистику качества
stats = api.get_quality_stats(days=7)
print(f"Средний RAGAS score: {stats['avg_ragas_score']}")
```

### JavaScript

```javascript
class ChatCenterAPI {
  constructor(baseUrl = "http://localhost:9000") {
    this.baseUrl = baseUrl;
  }

  async ask(message, chatId = "default", channel = "api") {
    const response = await fetch(`${this.baseUrl}/v1/chat/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, channel, chat_id: chatId })
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  }

  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/v1/admin/health`);
    return await response.json();
  }

  async getQualityStats(days = 30) {
    const response = await fetch(
      `${this.baseUrl}/v1/admin/quality/stats?days=${days}`
    );
    return await response.json();
  }
}

// Использование
const api = new ChatCenterAPI();

// Задать вопрос
api.ask("Как настроить маршрутизацию?")
  .then(result => console.log(result.answer_markdown))
  .catch(error => console.error(error));

// Проверить здоровье
api.healthCheck()
  .then(health => console.log("Статус:", health.status))
  .catch(error => console.error(error));
```

### cURL

```bash
# Chat API
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "chat_id": "test123",
    "message": "Как настроить маршрутизацию?"
  }'

# Health check
curl http://localhost:9000/v1/admin/health

# Metrics
curl http://localhost:9000/v1/admin/metrics

# Quality stats
curl "http://localhost:9000/v1/admin/quality/stats?days=7"

# Send feedback
curl -X POST http://localhost:9000/v1/admin/quality/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_id": "uuid-1234",
    "feedback_score": 1,
    "feedback_text": "Полезный ответ"
  }'
```

## Testing

### Swagger UI Testing

1. Откройте http://localhost:9000/apidocs
2. Выберите endpoint
3. Нажмите "Try it out"
4. Заполните параметры
5. Нажмите "Execute"
6. Просмотрите результаты

### Integration Tests

```python
import pytest
import requests

BASE_URL = "http://localhost:9000"

def test_chat_api():
    response = requests.post(
        f"{BASE_URL}/v1/chat/query",
        json={
            "channel": "api",
            "chat_id": "test",
            "message": "test question"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer_markdown" in data
    assert "interaction_id" in data

def test_health():
    response = requests.get(f"{BASE_URL}/v1/admin/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

def test_quality_stats():
    response = requests.get(f"{BASE_URL}/v1/admin/quality/stats?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "avg_ragas_score" in data
```

## Changelog

### v4.3.0 (2025-10-09)
- ✅ Swagger UI включен и работает
- ✅ Полная документация 20 endpoints
- ✅ Quality API с RAGAS метриками
- ✅ Auto-merge feature для контекста
- ✅ interaction_id для отслеживания качества
- ✅ security_warnings в ответах
- ✅ Улучшенная валидация и безопасность

### v4.2.0 (2025-10-08)
- Критические исправления QdrantWriter
- Корректный гибридный поиск
- Надежность и стабильность

### v4.1.0
- Единая DAG архитектура индексации
- Circuit Breaker для всех сервисов

## Дополнительные ресурсы

- 📖 [API Documentation](api_documentation.md) - Детальная документация
- 🏗️ [Architecture](architecture.md) - Архитектура системы
- 💡 [Examples](examples.md) - Примеры использования
- 🎯 [RAGAS Quality System](ragas_quality_system.md) - Система качества
- 🚀 [Quickstart](quickstart.md) - Быстрый старт

---

**Последнее обновление**: Октябрь 2025
**Версия API**: v4.3.0
**Swagger UI**: http://localhost:9000/apidocs
**Endpoints**: 20 (Chat: 1, Admin: 14, Quality: 5)
