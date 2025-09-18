# Изменения в API

## Обзор

Данный документ описывает изменения в API RAG-системы после критических исправлений.

## 🔄 Изменения в существующих endpoints

### POST /v1/chat/query

**Изменения**:
- Добавлена валидация входных данных с Marshmallow
- Улучшена обработка ошибок с детальными сообщениями
- Добавлена санитизация HTML и защита от XSS
- Интегрированы метрики Prometheus

**Новый формат ответа**:
```json
{
  "answer": "Ответ пользователю",
  "sources": [
    {
      "title": "Заголовок документа",
      "url": "https://docs-chatcenter.edna.ru/..."
    }
  ],
  "channel": "telegram",
  "chat_id": "123456789",
  "processing_time": 2.5,
  "request_id": "req_12345"
}
```

**Обработка ошибок**:
```json
{
  "error": "validation_failed",
  "message": "Некорректные данные запроса",
  "details": ["Message is required"],
  "sources": [],
  "channel": "telegram",
  "chat_id": "123456789"
}
```

## 🆕 Новые endpoints

### Мониторинг

#### GET /v1/admin/health
**Описание**: Расширенная проверка состояния системы
**Ответ**:
```json
{
  "status": "ok",
  "circuit_breakers": {
    "llm": {"state": "closed", "failure_count": 0},
    "embedding": {"state": "closed", "failure_count": 0},
    "qdrant": {"state": "closed", "failure_count": 0},
    "sparse": {"state": "closed", "failure_count": 0}
  },
  "cache": {
    "type": "redis",
    "used_memory": "2.5MB",
    "connected_clients": 1
  }
}
```

#### GET /v1/admin/metrics
**Описание**: Метрики Prometheus в JSON формате
**Ответ**:
```json
{
  "status": "ok",
  "metrics_count": 15,
  "metrics": {
    "rag_queries_total": {
      "type": "counter",
      "help": "Total queries processed",
      "samples": 150
    },
    "rag_query_duration_seconds": {
      "type": "histogram",
      "help": "Query processing duration in seconds",
      "samples": 45
    }
  }
}
```

#### GET /v1/admin/metrics/raw
**Описание**: Сырые метрики Prometheus для мониторинга
**Content-Type**: `text/plain; version=0.0.4; charset=utf-8`
**Ответ**: Текстовый формат Prometheus

#### GET /v1/admin/circuit-breakers
**Описание**: Состояние Circuit Breakers
**Ответ**:
```json
{
  "llm": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null,
    "threshold": 3,
    "timeout": 30
  },
  "embedding": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null,
    "threshold": 5,
    "timeout": 60
  }
}
```

#### GET /v1/admin/cache
**Описание**: Статистика кэша
**Ответ**:
```json
{
  "type": "redis",
  "used_memory": "2.5MB",
  "connected_clients": 1,
  "keyspace_hits": 1250,
  "keyspace_misses": 150
}
```

### Управление

#### POST /v1/admin/circuit-breakers/reset
**Описание**: Сброс всех Circuit Breakers
**Ответ**:
```json
{
  "status": "circuit_breakers_reset"
}
```

#### POST /v1/admin/metrics/reset
**Описание**: Сброс всех метрик (только для тестирования)
**Ответ**:
```json
{
  "status": "metrics_reset"
}
```

## 📊 Новые метрики Prometheus

### Основные метрики
- `rag_queries_total{channel, status, error_type}` - количество запросов
- `rag_query_duration_seconds{stage}` - длительность этапов
- `rag_embedding_duration_seconds{type}` - время эмбеддингов
- `rag_search_duration_seconds{type}` - время поиска
- `rag_llm_duration_seconds{provider}` - время LLM
- `rag_cache_hits_total{type}` - попадания в кэш
- `rag_cache_misses_total{type}` - промахи кэша
- `rag_errors_total{error_type, component}` - ошибки

### Состояние системы
- `rag_circuit_breaker_state{service}` - состояние Circuit Breakers
- `rag_active_connections` - активные соединения
- `rag_search_results_count{type}` - количество результатов поиска
- `rag_llm_tokens_total{provider, type}` - использование токенов

## 🔒 Улучшения безопасности

### Валидация входных данных
- Максимальная длина сообщения: 2000 символов
- Разрешенные каналы: telegram, web, api
- HTML экранирование и санитизация
- Защита от XSS и инъекций

### Обработка ошибок
- Детальные сообщения об ошибках
- Логирование всех ошибок с контекстом
- Graceful degradation при сбоях
- Автоматическое восстановление

## 📈 Мониторинг

### HTTP сервер метрик
- Порт: 8000
- Endpoint: `http://localhost:8000/metrics`
- Совместимость с Prometheus, Grafana

### Логирование
- Структурированные логи с контекстом
- Время выполнения каждого этапа
- Детальная информация об ошибках
- Статистика производительности

## 🚀 Миграция

### Обратная совместимость
- Все существующие endpoints сохранены
- Формат ответов расширен, но обратно совместим
- Новые поля опциональны

### Рекомендации
1. Обновите клиенты для использования новых полей ответа
2. Настройте мониторинг через новые endpoints
3. Используйте Circuit Breaker endpoints для диагностики
4. Настройте алерты на основе новых метрик

## 📝 Примеры использования

### Проверка состояния системы
```bash
curl http://localhost:9000/v1/admin/health
```

### Получение метрик
```bash
curl http://localhost:9000/v1/admin/metrics
```

### Сброс Circuit Breakers
```bash
curl -X POST http://localhost:9000/v1/admin/circuit-breakers/reset
```

### Мониторинг через Prometheus
```bash
curl http://localhost:8000/metrics
```

### Управление Rate Limiting
```bash
# Проверка состояния Rate Limiter
curl http://localhost:9000/v1/admin/rate-limiter

# Проверка пользователя
curl http://localhost:9000/v1/admin/rate-limiter/123456789

# Сброс лимитов пользователя
curl -X POST http://localhost:9000/v1/admin/rate-limiter/123456789/reset
```

### Управление безопасностью
```bash
# Статистика безопасности
curl http://localhost:9000/v1/admin/security

# Состояние пользователя
curl http://localhost:9000/v1/admin/security/user/123456789

# Блокировка пользователя
curl -X POST http://localhost:9000/v1/admin/security/user/123456789/block \
  -H "Content-Type: application/json" \
  -d '{"reason": "Suspicious activity"}'
```

## 🆕 Дополнительные API endpoints (завершены)

### Rate Limiting
- `GET /v1/admin/rate-limiter` - Состояние Rate Limiter
- `GET /v1/admin/rate-limiter/<user_id>` - Состояние пользователя
- `POST /v1/admin/rate-limiter/<user_id>/reset` - Сброс лимитов

### Безопасность
- `GET /v1/admin/security` - Статистика безопасности
- `GET /v1/admin/security/user/<user_id>` - Состояние пользователя
- `POST /v1/admin/security/user/<user_id>/block` - Блокировка пользователя

### Новые возможности
- **Семантическое chunking** - улучшенное разбиение текста
- **Rate Limiting** - защита от злоупотреблений
- **Улучшенный Telegram адаптер** - красивое форматирование
- **Система безопасности** - мониторинг и блокировка
