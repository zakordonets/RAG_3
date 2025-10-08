# API Документация

## 📚 Обзор

RAG-система предоставляет автоматически генерируемую OpenAPI/Swagger документацию для всех API endpoints. Документация доступна в интерактивном формате через Swagger UI и в виде JSON спецификации.

## 🔗 Доступ к документации

### Swagger UI (Интерактивная документация)
```
http://localhost:9000/apidocs
```

### OpenAPI 2.0 Спецификация (JSON)
```
http://localhost:9000/apispec_1.json
```

## 🏗️ Структура документации

### Теги (Tags)
API endpoints сгруппированы по функциональности:

- **Chat** - Основные функции чата
- **Admin** - Административные функции

### Схемы запросов и ответов

#### POST /v1/chat/query
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
  "answer": "Ответ системы",
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
  "security_warnings": []
}
```

**Примечание**: С версии 4.3.0 источники могут содержать дополнительные поля `auto_merged`, `merged_chunk_count`, и `chunk_span`, которые указывают на автоматическое объединение соседних чанков документа. См. [AUTO_MERGE.md](./AUTO_MERGE.md) для подробностей.

**Ошибки**:
- `400` - Ошибка валидации или безопасности
- `500` - Внутренняя ошибка сервера

#### Admin Endpoints

##### POST /v1/admin/reindex
**Описание**: Запуск переиндексации документации

**Тело запроса** (опционально):
```json
{
  "force_full": false
}
```

##### GET /v1/admin/health
**Описание**: Проверка состояния системы

**Ответ**:
```json
{
  "status": "ok",
  "circuit_breakers": {...},
  "cache": {...}
}
```

##### GET /v1/admin/metrics
**Описание**: Получение метрик Prometheus в JSON формате

##### GET /v1/admin/metrics/raw
**Описание**: Сырые метрики Prometheus в текстовом формате

##### POST /v1/admin/metrics/reset
**Описание**: Сброс всех метрик (только для тестирования)

##### GET /v1/admin/circuit-breakers
**Описание**: Состояние Circuit Breakers

##### POST /v1/admin/circuit-breakers/reset
**Описание**: Сброс всех Circuit Breakers

##### GET /v1/admin/cache
**Описание**: Статистика кэша

##### Rate Limiting Endpoints

###### GET /v1/admin/rate-limiter
**Описание**: Состояние Rate Limiter

###### GET /v1/admin/rate-limiter/{user_id}
**Описание**: Состояние Rate Limiter для конкретного пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

###### POST /v1/admin/rate-limiter/{user_id}/reset
**Описание**: Сброс лимитов для конкретного пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

##### Security Endpoints

###### GET /v1/admin/security
**Описание**: Статистика безопасности

###### GET /v1/admin/security/user/{user_id}
**Описание**: Состояние безопасности для конкретного пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

**Ответ**:
```json
{
  "user_id": "123456789",
  "risk_score": 5,
  "is_blocked": false,
  "risk_level": "medium"
}
```

###### POST /v1/admin/security/user/{user_id}/block
**Описание**: Блокировка пользователя

**Параметры пути**:
- `user_id` (string, required) - ID пользователя

**Тело запроса** (опционально):
```json
{
  "reason": "Причина блокировки"
}
```

## 🛠️ Технические детали

### OpenAPI 2.0 (Swagger)
- **Версия**: OpenAPI 2.0 (Swagger 2.0)
- **Генератор**: Flasgger
- **Формат**: JSON
- **Кодировка**: UTF-8

### Конфигурация
```python
Swagger(app, template={
    "swagger": "2.0",
    "info": {
        "title": "edna Chat Center RAG API",
        "version": "1.0.0",
        "description": "Автоматически сгенерированная документация OpenAPI для Core API"
    },
    "basePath": "/",
    "schemes": ["http"],
    "securityDefinitions": {},
})
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
        schema:
          type: object
          properties:
            answer:
              type: string
            sources:
              type: array
              items:
                type: object
                properties:
                  title:
                    type: string
                  url:
                    type: string
            # ... другие поля
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
```

## 📊 Мониторинг API

### Метрики
- **rag_queries_total** - количество запросов по каналам и статусам
- **rag_query_duration_seconds** - длительность обработки запросов
- **rag_errors_total** - количество ошибок по типам

### Логирование
- Все API запросы логируются с контекстом
- Ошибки записываются с полным стеком вызовов
- Время обработки каждого этапа

### Health Checks
- **GET /v1/admin/health** - общее состояние системы
- **GET /v1/admin/circuit-breakers** - состояние Circuit Breakers
- **GET /v1/admin/cache** - состояние кэша

## 🔒 Безопасность API

### Валидация
- Все входные данные валидируются через Marshmallow схемы
- Проверка типов, форматов и ограничений
- Санитизация HTML и опасных паттернов

### Rate Limiting
- Ограничение частоты запросов от пользователей
- Burst protection для предотвращения спама
- Управление через admin API

### Мониторинг безопасности
- Отслеживание подозрительной активности
- Автоматическая блокировка пользователей
- Оценка риска для каждого запроса

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
    responses:
      200:
        description: Успешный ответ
    """
    return jsonify({"status": "ok"})
```

## 🎯 Заключение

Автоматическая генерация OpenAPI документации обеспечивает:

- ✅ **Актуальность** - документация всегда соответствует коду
- ✅ **Интерактивность** - тестирование через Swagger UI
- ✅ **Стандартизацию** - OpenAPI 2.0 совместимость
- ✅ **Удобство** - автоматическое обновление при изменениях
- ✅ **Полноту** - все endpoints с детальными схемами

API документация готова к использованию разработчиками и интеграторами! 🚀
