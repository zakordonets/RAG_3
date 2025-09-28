# 📚 Phase 2: RAGAS Quality System - Примеры использования

## 🚀 Быстрый старт

### 1. Базовая настройка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл

# Инициализация базы данных качества
python -c "
import asyncio
from app.models.quality_interaction import QualityInteraction

async def init_db():
    await QualityInteraction.create_tables()
    print('✅ Quality database initialized')

asyncio.run(init_db())
"
```

### 2. Запуск системы

```bash
# Запуск Flask API с Quality System
python wsgi.py

# В другом терминале - Telegram бот с фидбеком
python adapters/telegram_polling.py
```

### 3. Проверка работоспособности

```bash
# Проверка health endpoint
curl http://localhost:9000/v1/admin/health

# Проверка quality endpoints
curl http://localhost:9000/v1/admin/quality/stats
```

## 📊 API Примеры

### Chat API с автоматической оценкой качества

```bash
# Отправка запроса через Chat API
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Как настроить маршрутизацию в edna Chat Center?",
    "channel": "api",
    "chat_id": "user123"
  }'

# Ответ включает interaction_id для последующего фидбека
{
  "response": "Маршрутизация в edna Chat Center настраивается через...",
  "interaction_id": "interaction_abc123_1234567890",
  "sources": ["https://docs.edna.ru/routing"],
  "quality_score": 0.85
}
```

### Quality Analytics API

```bash
# Получение статистики качества за последние 7 дней
curl "http://localhost:9000/v1/admin/quality/stats?days=7"

# Ответ
{
  "total_interactions": 150,
  "avg_ragas_score": 0.82,
  "avg_faithfulness": 0.85,
  "avg_context_precision": 0.78,
  "avg_answer_relevancy": 0.83,
  "satisfaction_rate": 0.89,
  "positive_feedback": 45,
  "negative_feedback": 6
}

# Получение списка последних взаимодействий
curl "http://localhost:9000/v1/admin/quality/interactions?limit=5"

# Ответ
{
  "interactions": [
    {
      "interaction_id": "interaction_abc123_1234567890",
      "query": "Как настроить маршрутизацию?",
      "response": "Маршрутизация настраивается через...",
      "ragas_faithfulness": 0.85,
      "ragas_context_precision": 0.78,
      "ragas_answer_relevancy": 0.83,
      "user_feedback_type": "positive",
      "created_at": "2025-09-23T10:30:00Z"
    }
  ]
}

# Получение трендов качества
curl "http://localhost:9000/v1/admin/quality/trends?days=30&metric=faithfulness"

# Ответ
{
  "trends": [
    {
      "date": "2025-09-23",
      "avg_faithfulness": 0.85,
      "avg_context_precision": 0.78,
      "avg_answer_relevancy": 0.83,
      "interaction_count": 25
    }
  ]
}

# Корреляционный анализ
curl "http://localhost:9000/v1/admin/quality/correlation?days=30"

# Ответ
{
  "correlations": {
    "faithfulness_vs_satisfaction": 0.72,
    "context_precision_vs_satisfaction": 0.68,
    "answer_relevancy_vs_satisfaction": 0.81
  },
  "insights": [
    "Answer relevancy наиболее коррелирует с пользовательской удовлетворенностью",
    "Faithfulness показывает стабильно высокие значения",
    "Context precision имеет потенциал для улучшения"
  ]
}
```

### User Feedback API

```bash
# Добавление положительного фидбека
curl -X POST http://localhost:9000/v1/admin/quality/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_id": "interaction_abc123_1234567890",
    "feedback_type": "positive",
    "feedback_text": "Отличный ответ! Очень помогло."
  }'

# Ответ
{
  "success": true,
  "message": "Feedback added successfully",
  "interaction_id": "interaction_abc123_1234567890"
}

# Добавление отрицательного фидбека
curl -X POST http://localhost:9000/v1/admin/quality/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_id": "interaction_def456_1234567891",
    "feedback_type": "negative",
    "feedback_text": "Ответ не полный, не хватает деталей."
  }'
```

## 🤖 Telegram Bot примеры

### Inline кнопки для фидбека

```python
# Пример сообщения с inline кнопками
message = """
🤖 **Ответ найден:**

Маршрутизация в edna Chat Center настраивается через веб-интерфейс администратора. В разделе "Настройки" → "Маршрутизация" вы можете:

• Настроить правила маршрутизации по ключевым словам
• Установить приоритеты для разных типов запросов
• Настроить fallback маршруты

📚 **Источник:** [Документация по маршрутизации](https://docs.edna.ru/routing)

---
**Помог ли этот ответ?**
"""

# Создание inline клавиатуры
keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("👍 Подходит",
                           callback_data=f"feedback_{interaction_id}_positive"),
        InlineKeyboardButton("👎 Не подходит",
                           callback_data=f"feedback_{interaction_id}_negative")
    ]
])

# Отправка сообщения
await bot.send_message(
    chat_id=chat_id,
    text=message,
    reply_markup=keyboard,
    parse_mode=ParseMode.MARKDOWN_V2
)
```

### Обработка callback от кнопок

```python
# Обработка нажатия на inline кнопки
@bot.callback_query_handler(func=lambda call: call.data.startswith('feedback_'))
async def handle_feedback_callback(callback_query):
    try:
        # Парсинг callback данных
        data = callback_query.data
        parts = data.split('_', 2)  # feedback_<id>_<type>

        if len(parts) != 3:
            await callback_query.answer("❌ Ошибка обработки фидбека")
            return

        interaction_id = parts[1]
        feedback_type = "positive" if parts[2] == "positive" else "negative"

        # Сохранение фидбека
        success = await quality_manager.add_user_feedback(
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            feedback_text=""
        )

        if success:
            # Обновление кнопок
            new_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "✅ Спасибо за оценку!",
                    callback_data="feedback_received"
                )]
            ])

            await callback_query.edit_message_reply_markup(
                reply_markup=new_keyboard
            )
            await callback_query.answer("✅ Оценка сохранена!")
        else:
            await callback_query.answer("❌ Ошибка сохранения оценки")

    except Exception as e:
        logger.error(f"Error handling feedback callback: {e}")
        await callback_query.answer("❌ Произошла ошибка")
```

## 🧪 Тестирование примеры

### Интеграционные тесты

```python
# scripts/test_phase2_integration.py
import pytest
import asyncio
from app.services.quality_manager import quality_manager

@pytest.mark.asyncio
async def test_quality_flow():
    """Тест полного flow оценки качества"""

    # 1. Создание взаимодействия
    interaction_id = await quality_manager.evaluate_interaction(
        query="Как настроить маршрутизацию?",
        response="Маршрутизация настраивается через веб-интерфейс...",
        contexts=["Контекст 1", "Контекст 2"],
        sources=["https://docs.edna.ru/routing"]
    )

    assert interaction_id is not None
    print(f"✅ Interaction created: {interaction_id}")

    # 2. Добавление пользовательского фидбека
    feedback_success = await quality_manager.add_user_feedback(
        interaction_id=interaction_id,
        feedback_type="positive",
        feedback_text="Отличный ответ!"
    )

    assert feedback_success is True
    print("✅ User feedback added")

    # 3. Получение статистики
    stats = await quality_manager.get_quality_statistics(days=1)

    assert stats['total_interactions'] > 0
    assert stats['avg_ragas_score'] > 0
    print(f"✅ Statistics retrieved: {stats}")

# Запуск теста
if __name__ == "__main__":
    asyncio.run(test_quality_flow())
```

### Unit тесты компонентов

```python
# tests/test_ragas_evaluator.py
import pytest
from app.services.ragas_evaluator import RAGASEvaluatorWithoutGroundTruth

@pytest.mark.asyncio
async def test_ragas_evaluation():
    """Тест RAGAS оценки"""

    evaluator = RAGASEvaluatorWithoutGroundTruth()

    # Тест с реальными данными
    scores = await evaluator.evaluate_interaction(
        query="Как настроить маршрутизацию?",
        response="Маршрутизация настраивается через веб-интерфейс администратора...",
        contexts=[
            "Маршрутизация позволяет направлять входящие сообщения к соответствующим агентам",
            "Настройка маршрутизации доступна в разделе Настройки → Маршрутизация"
        ],
        sources=["https://docs.edna.ru/routing"]
    )

    # Проверка структуры ответа
    assert 'faithfulness' in scores
    assert 'context_precision' in scores
    assert 'answer_relevancy' in scores
    assert 'overall_score' in scores

    # Проверка диапазонов значений
    for metric, score in scores.items():
        assert 0.0 <= score <= 1.0, f"{metric} score out of range: {score}"

    print(f"✅ RAGAS scores: {scores}")

@pytest.mark.asyncio
async def test_fallback_scores():
    """Тест fallback оценок при недоступности RAGAS"""

    # Отключить RAGAS для теста fallback
    import os
    os.environ["RAGAS_EVALUATION_SAMPLE_RATE"] = "0"

    evaluator = RAGASEvaluatorWithoutGroundTruth()

    scores = await evaluator.evaluate_interaction(
        query="Тестовый вопрос",
        response="Тестовый ответ",
        contexts=["Контекст"],
        sources=["https://example.com"]
    )

    # Проверка fallback логики
    assert scores['faithfulness'] <= 0.8
    assert scores['context_precision'] <= 0.7
    assert scores['answer_relevancy'] <= 0.9

    print(f"✅ Fallback scores: {scores}")
```

### API тесты

```python
# tests/test_quality_api.py
import requests
import pytest

def test_quality_stats_api():
    """Тест API статистики качества"""

    response = requests.get("http://localhost:9000/v1/admin/quality/stats?days=7")

    assert response.status_code == 200

    data = response.json()
    assert 'total_interactions' in data
    assert 'avg_ragas_score' in data
    assert 'satisfaction_rate' in data

    print(f"✅ Stats API: {data}")

def test_quality_interactions_api():
    """Тест API списка взаимодействий"""

    response = requests.get("http://localhost:9000/v1/admin/quality/interactions?limit=5")

    assert response.status_code == 200

    data = response.json()
    assert 'interactions' in data
    assert isinstance(data['interactions'], list)

    if data['interactions']:
        interaction = data['interactions'][0]
        assert 'interaction_id' in interaction
        assert 'query' in interaction
        assert 'response' in interaction

    print(f"✅ Interactions API: {len(data['interactions'])} interactions")

def test_feedback_api():
    """Тест API добавления фидбека"""

    # Сначала создаем взаимодействие через Chat API
    chat_response = requests.post(
        "http://localhost:9000/v1/chat/query",
        json={
            "message": "Тестовый вопрос для фидбека",
            "channel": "api",
            "chat_id": "test_user"
        }
    )

    assert chat_response.status_code == 200
    chat_data = chat_response.json()
    interaction_id = chat_data.get("interaction_id")

    assert interaction_id is not None

    # Добавляем фидбек
    feedback_response = requests.post(
        "http://localhost:9000/v1/admin/quality/feedback",
        json={
            "interaction_id": interaction_id,
            "feedback_type": "positive",
            "feedback_text": "Отличный ответ!"
        }
    )

    assert feedback_response.status_code == 200

    feedback_data = feedback_response.json()
    assert feedback_data['success'] is True

    print(f"✅ Feedback API: {feedback_data}")
```

## 📊 Мониторинг примеры

### Prometheus запросы

```bash
# Средний RAGAS score по метрикам
curl "http://localhost:9090/api/v1/query?query=avg(rag_ragas_score)"

# Количество взаимодействий за последний час
curl "http://localhost:9090/api/v1/query?query=rate(rag_quality_interactions_total[1h])"

# Соотношение положительного/отрицательного фидбека
curl "http://localhost:9090/api/v1/query?query=rate(rag_user_feedback_total{feedback_type=\"positive\"}[1h]) / rate(rag_user_feedback_total[1h])"

# Среднее время RAGAS оценки
curl "http://localhost:9090/api/v1/query?query=rate(rag_quality_evaluation_duration_seconds_sum[5m]) / rate(rag_quality_evaluation_duration_seconds_count[5m])"

# Топ-5 пользователей по количеству взаимодействий
curl "http://localhost:9090/api/v1/query?query=topk(5, sum by (user_id) (rag_quality_interactions_total))"
```

### Grafana Dashboard конфигурация

```json
{
  "dashboard": {
    "title": "RAG Quality Metrics - Phase 2",
    "panels": [
      {
        "title": "RAGAS Quality Scores",
        "type": "graph",
        "targets": [
          {
            "expr": "rag_ragas_score{metric_type=\"faithfulness\"}",
            "legendFormat": "Faithfulness"
          },
          {
            "expr": "rag_ragas_score{metric_type=\"context_precision\"}",
            "legendFormat": "Context Precision"
          },
          {
            "expr": "rag_ragas_score{metric_type=\"answer_relevancy\"}",
            "legendFormat": "Answer Relevancy"
          }
        ]
      },
      {
        "title": "User Satisfaction Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "rate(rag_user_feedback_total{feedback_type=\"positive\"}[1h]) / rate(rag_user_feedback_total[1h]) * 100",
            "legendFormat": "Satisfaction %"
          }
        ]
      },
      {
        "title": "Quality Interactions per Hour",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(rag_quality_interactions_total[1h])",
            "legendFormat": "Interactions/hour"
          }
        ]
      }
    ]
  }
}
```

## 🔧 Конфигурация примеры

### Различные сценарии конфигурации

```bash
# === Для разработки ===
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=0.1          # 10% взаимодействий
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite+aiosqlite:///data/quality_interactions.db
ENABLE_QUALITY_METRICS=true
START_METRICS_SERVER=true

# === Для production ===
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=1.0          # Все взаимодействия
QUALITY_DB_ENABLED=true
DATABASE_URL=postgresql://user:pass@host:5432/quality_db
ENABLE_QUALITY_METRICS=true
START_METRICS_SERVER=true

# === Для тестирования ===
RAGAS_EVALUATION_SAMPLE_RATE=0            # Отключить RAGAS
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite+aiosqlite:///data/quality_interactions_test.db
ENABLE_QUALITY_METRICS=true
START_METRICS_SERVER=false

# === Для демонстрации ===
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=0.5          # 50% взаимодействий
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite+aiosqlite:///data/quality_interactions.db
ENABLE_QUALITY_METRICS=true
START_METRICS_SERVER=true
```

### Docker Compose конфигурация

```yaml
# docker-compose.quality.yml
version: '3.8'

services:
  rag-api:
    build: .
    ports:
      - "9000:9000"
      - "9002:9002"  # Metrics port
    environment:
      - ENABLE_RAGAS_EVALUATION=true
      - QUALITY_DB_ENABLED=true
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/quality_db
      - ENABLE_QUALITY_METRICS=true
      - START_METRICS_SERVER=true
    depends_on:
      - postgres
      - redis
    volumes:
      - ./data:/app/data

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=quality_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana
    ports:
      - "8080:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning

volumes:
  postgres_data:
  grafana_data:
```

## 🚀 Production развертывание

### Kubernetes манифесты

```yaml
# k8s/quality-system.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-quality-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rag-quality-system
  template:
    metadata:
      labels:
        app: rag-quality-system
    spec:
      containers:
      - name: rag-api
        image: rag-system:latest
        ports:
        - containerPort: 9000
        - containerPort: 9002
        env:
        - name: ENABLE_RAGAS_EVALUATION
          value: "true"
        - name: QUALITY_DB_ENABLED
          value: "true"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: quality-db-secret
              key: database-url
        - name: ENABLE_QUALITY_METRICS
          value: "true"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /v1/admin/health
            port: 9000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /v1/admin/health
            port: 9000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: rag-quality-service
spec:
  selector:
    app: rag-quality-system
  ports:
  - name: api
    port: 9000
    targetPort: 9000
  - name: metrics
    port: 9002
    targetPort: 9002
  type: ClusterIP
```

---

**Версия документации**: 2.0
**Дата обновления**: 2025-09-23
**Статус**: Production Ready ✅
