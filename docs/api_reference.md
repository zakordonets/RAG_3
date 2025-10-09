# API Reference

## Base URL
```
http://localhost:9000
```

## Authentication
В текущей версии аутентификация не требуется. В production рекомендуется добавить API ключи или JWT токены.

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
- `channel` (string, required): Канал связи (telegram, web, etc.)
- `chat_id` (string, required): Уникальный идентификатор чата
- `message` (string, required): Текст запроса пользователя

#### Response

**Success (200 OK):**
```json
{
  "answer": "🔧 *Настройка маршрутизации*\n\nДля настройки маршрутизации в edna Chat Center...",
  "sources": [
    {
      "title": "Настройка маршрутизации",
      "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/"
    },
    {
      "title": "Создание сегментов",
      "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/admin-createsegment"
    }
  ],
  "channel": "telegram",
  "chat_id": "123456789"
}
```

**Error (400 Bad Request):**
```json
{
  "error": "Missing required field: message",
  "code": "VALIDATION_ERROR"
}
```

**Error (500 Internal Server Error):**
```json
{
  "error": "Internal server error",
  "code": "INTERNAL_ERROR"
}
```

#### Response Fields

- `answer` (string): Сгенерированный ответ (устаревший ключ, будет удалён)
- `answer_markdown` (string): Ответ ядра в Markdown
- `sources` (array): Список источников информации
  - `title` (string): Заголовок источника
  - `url` (string): URL документации
- `meta` (object): Метаданные генерации (LLM, режим, параметры)
- `channel` (string): Канал, с которого пришел запрос
- `chat_id` (string): ID чата

## Admin API

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
  "timestamp": "2025-01-16T18:30:00Z",
  "components": {
    "qdrant": {
      "status": "healthy",
      "response_time_ms": 45
    },
    "llm_providers": {
      "yandex": "healthy",
      "gpt5": "unavailable",
      "deepseek": "healthy"
    },
    "embeddings": {
      "dense": "healthy",
      "sparse": "healthy"
    }
  }
}
```

**Error (503 Service Unavailable):**
```json
{
  "status": "error",
  "timestamp": "2025-01-16T18:30:00Z",
  "error": "Qdrant connection failed",
  "components": {
    "qdrant": {
      "status": "unhealthy",
      "error": "Connection timeout"
    }
  }
}
```

### POST /v1/admin/reindex

Запускает полную переиндексацию документации.

#### Request

```http
POST /v1/admin/reindex
Content-Type: application/json
```

**Body (optional):**
```json
{
  "incremental": true,
  "force": false
}
```

**Parameters:**
- `incremental` (boolean, optional): Инкрементальное обновление (по умолчанию: true)
- `force` (boolean, optional): Принудительная переиндексация (по умолчанию: false)

#### Response

**Success (200 OK):**
```json
{
  "status": "started",
  "job_id": "reindex_20250116_183000",
  "message": "Reindexing started",
  "estimated_duration_minutes": 15
}
```

**Success (202 Accepted):**
```json
{
  "status": "in_progress",
  "job_id": "reindex_20250116_183000",
  "progress": {
    "pages_processed": 150,
    "total_pages": 284,
    "percentage": 52.8
  }
}
```

**Error (409 Conflict):**
```json
{
  "error": "Reindexing already in progress",
  "job_id": "reindex_20250116_182000"
}
```

## Error Codes

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
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  },
  "timestamp": "2025-01-16T18:30:00Z",
  "request_id": "req_123456789"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Invalid request parameters |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `LLM_UNAVAILABLE` | All LLM providers are unavailable |
| `EMBEDDING_ERROR` | Embedding generation failed |
| `SEARCH_ERROR` | Vector search failed |
| `RERANK_ERROR` | Reranking failed |
| `FORMATTING_ERROR` | Response formatting failed |

## Rate Limiting

### Limits
- **Chat API**: 10 requests per minute per chat_id
- **Admin API**: 5 requests per minute per IP
- **Reindex**: 1 request per hour per IP

### Headers
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1642276800
```

### Rate Limit Exceeded Response
```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
```

## Webhooks (Planned)

### POST /v1/webhooks/telegram

Webhook endpoint для Telegram Bot API (альтернатива long polling).

#### Request

```http
POST /v1/webhooks/telegram
Content-Type: application/json
X-Telegram-Bot-Api-Secret-Token: your_secret_token
```

**Body:**
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 123456789,
      "is_bot": false,
      "first_name": "User"
    },
    "chat": {
      "id": 123456789,
      "first_name": "User",
      "type": "private"
    },
    "date": 1642276800,
    "text": "Hello"
  }
}
```

## SDK Examples

### Python

```python
import requests

# Chat API
def ask_question(message, chat_id="default"):
    response = requests.post(
        "http://localhost:9000/v1/chat/query",
        json={
            "channel": "web",
            "chat_id": chat_id,
            "message": message
        }
    )
    return response.json()

# Usage
result = ask_question("Как настроить маршрутизацию?")
print(result["answer"])
```

### JavaScript

```javascript
// Chat API
async function askQuestion(message, chatId = "default") {
  const response = await fetch("http://localhost:9000/v1/chat/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      channel: "web",
      chat_id: chatId,
      message: message
    })
  });
  return await response.json();
}

// Usage
askQuestion("Как настроить маршрутизацию?")
  .then(result => console.log(result.answer));
```

### cURL

```bash
# Chat API
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web",
    "chat_id": "123456789",
    "message": "Как настроить маршрутизацию?"
  }'

# Health check
curl http://localhost:9000/v1/admin/health

# Reindex
curl -X POST http://localhost:9000/v1/admin/reindex \
  -H "Content-Type: application/json" \
  -d '{"incremental": true}'
```

## Testing

### Unit Tests

```python
import pytest
from app.services.orchestrator import handle_query

def test_handle_query():
    result = handle_query("telegram", "123", "test message")
    assert "answer" in result
    assert "sources" in result
    assert result["channel"] == "telegram"
    assert result["chat_id"] == "123"
```

### Integration Tests

```python
import requests

def test_chat_api():
    response = requests.post(
        "http://localhost:9000/v1/chat/query",
        json={
            "channel": "test",
            "chat_id": "test123",
            "message": "test question"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
```

### Load Testing

```bash
# Using Apache Bench
ab -n 100 -c 10 -p request.json -T application/json http://localhost:9000/v1/chat/query

# Using wrk
wrk -t12 -c400 -d30s -s post.lua http://localhost:9000/v1/chat/query
```

## Changelog

### v1.0.0 (2025-01-16)
- Initial release
- Chat API with Telegram support
- Admin API for health checks and reindexing
- Hybrid search with dense and sparse embeddings
- LLM routing with fallback support
- HTML-адаптер для Telegram с санитайзером

### Planned Features
- Web interface
- Webhook support
- Rate limiting
- Authentication
- Analytics API
- Batch processing
