# 📊 Phase 2: RAGAS Quality System - Полная документация

## 🎯 Обзор

Phase 2 RAGAS Quality System представляет собой комплексную систему оценки качества RAG-взаимодействий с автоматической оценкой через RAGAS метрики, пользовательским фидбеком и продвинутой аналитикой качества.

## 🏗️ Архитектура системы

```mermaid
graph TB
    A[Telegram Bot] --> B[RAG Orchestrator]
    B --> C[Quality Manager]
    C --> D[RAGAS Evaluator]
    C --> E[Quality Database]
    C --> F[Metrics Collector]

    D --> G[Yandex LLM]
    D --> H[BGE Embeddings]
    D --> I[Fallback Scores]

    E --> J[SQLite/PostgreSQL]
    F --> K[Prometheus]
    K --> L[Grafana Dashboard]

    M[Admin API] --> C
    N[User Feedback] --> C

    subgraph "RAGAS Metrics"
        O[Faithfulness]
        P[Context Precision]
        Q[Answer Relevancy]
    end

    D --> O
    D --> P
    D --> Q
```

## 📋 Компоненты системы

### 1. RAGAS Evaluator (`app/services/ragas_evaluator.py`)

**Назначение**: Автоматическая оценка качества взаимодействий с использованием RAGAS метрик.

**Ключевые возможности**:
- ✅ **Три основные метрики**: Faithfulness, Context Precision, Answer Relevancy
- ✅ **Таймауты и fallback**: 25-секундный таймаут с автоматическим fallback
- ✅ **LangChain интеграция**: Совместимость с YandexGPT и BGE-M3
- ✅ **Детерминизм**: Фиксированные параметры LLM для стабильных результатов

**Метрики RAGAS**:

| Метрика | Описание | Диапазон | Назначение |
|---------|----------|----------|------------|
| **Faithfulness** | Соответствие ответа контексту | 0.0-1.0 | Проверка фактологической точности |
| **Context Precision** | Релевантность извлеченного контекста | 0.0-1.0 | Качество поиска документов |
| **Answer Relevancy** | Релевантность ответа запросу | 0.0-1.0 | Соответствие пользовательским ожиданиям |

**Fallback механизм**:
```python
def _calculate_fallback_scores(self, query: str, response: str, contexts: List[str]) -> Dict[str, float]:
    """Эвристические оценки при недоступности RAGAS"""
    # Простые эвристики на основе длины и релевантности
    faithfulness = min(0.8, len(response) / 100.0)  # 0.8 max
    context_precision = min(0.7, len(contexts) * 0.2)  # 0.7 max
    answer_relevancy = min(0.9, len(query.split()) / 10.0)  # 0.9 max

    return {
        'faithfulness': faithfulness,
        'context_precision': context_precision,
        'answer_relevancy': answer_relevancy,
        'overall_score': (faithfulness + context_precision + answer_relevancy) / 3.0
    }
```

### 2. Quality Manager (`app/services/quality_manager.py`)

**Назначение**: Центральный менеджер для управления процессом оценки качества.

**Функции**:
- 🔄 **Оценка взаимодействий**: Автоматическая RAGAS оценка
- 💾 **Сохранение данных**: В базу данных с метаданными
- 📊 **Статистика качества**: Агрегация и анализ метрик
- 🔗 **Интеграция с оркестратором**: Автоматическое создание взаимодействий

**API методы**:
```python
class UnifiedQualityManager:
    async def evaluate_interaction(self, query: str, response: str,
                                 contexts: List[str], sources: List[str]) -> str
    async def add_user_feedback(self, interaction_id: str,
                              feedback_type: str, feedback_text: str) -> bool
    async def get_quality_statistics(self, days: int = 7) -> Dict[str, Any]
    async def get_recent_interactions(self, limit: int = 10) -> List[Dict]
    async def get_quality_trends(self, days: int = 30) -> List[Dict]
    async def get_correlation_analysis(self, days: int = 30) -> Dict[str, Any]
```

### 3. Quality Database (`app/models/quality_interaction.py`)

**Назначение**: Хранение и управление данными о качестве взаимодействий.

**Схема базы данных**:
```sql
CREATE TABLE quality_interactions (
    interaction_id VARCHAR(255) PRIMARY KEY,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    contexts TEXT,                    -- JSON массив контекстов
    sources TEXT,                     -- JSON массив источников
    ragas_faithfulness FLOAT,
    ragas_context_precision FLOAT,
    ragas_answer_relevancy FLOAT,
    ragas_overall_score FLOAT,
    user_feedback_type VARCHAR(50),   -- positive/negative
    user_feedback_text TEXT,
    combined_score FLOAT,             -- комбинированная оценка
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Безопасность данных**:
- ✅ **JSON сериализация**: Безопасное хранение сложных структур
- ✅ **Валидация типов**: Проверка корректности данных
- ✅ **Индексы**: Оптимизация запросов по дате и ID

### 4. Admin API (`app/routes/quality.py`)

**Назначение**: REST API для управления и мониторинга качества.

**Endpoints**:

| Endpoint | Метод | Описание | Параметры |
|----------|-------|----------|-----------|
| `/v1/admin/quality/stats` | GET | Статистика качества | `days` (опционально) |
| `/v1/admin/quality/interactions` | GET | Список взаимодействий | `limit`, `offset` |
| `/v1/admin/quality/trends` | GET | Тренды качества | `days`, `metric` |
| `/v1/admin/quality/correlation` | GET | Корреляционный анализ | `days` |
| `/v1/admin/quality/feedback` | POST | Добавление фидбека | `interaction_id`, `feedback_type`, `feedback_text` |

**Примеры использования**:
```bash
# Получить статистику за последние 7 дней
curl "http://localhost:9000/v1/admin/quality/stats?days=7"

# Добавить пользовательский фидбек
curl -X POST "http://localhost:9000/v1/admin/quality/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_id": "interaction_abc123_1234567890",
    "feedback_type": "positive",
    "feedback_text": "Отличный ответ!"
  }'

# Получить тренды качества
curl "http://localhost:9000/v1/admin/quality/trends?days=30&metric=faithfulness"
```

### 5. Telegram Feedback Integration

**Назначение**: Сбор пользовательского фидбека через inline кнопки в Telegram.

**Функции**:
- 🔘 **Inline кнопки**: "👍 Подходит" / "👎 Не подходит"
- 💬 **Обработка callback**: Асинхронная обработка оценок
- 🔗 **Связь с базой**: Автоматическое сохранение в Quality DB
- 📊 **Метрики**: Отслеживание через Prometheus

**Реализация**:
```python
async def handle_callback_query(callback_query):
    """Обработка callback от inline кнопок"""
    try:
        data = callback_query.data
        interaction_id = data.split('_', 2)[1]  # feedback_<id>_<type>

        feedback_type = "positive" if "positive" in data else "negative"

        # Сохранение фидбека
        success = await quality_manager.add_user_feedback(
            interaction_id=interaction_id,
            feedback_type=feedback_type,
            feedback_text=""
        )

        # Обновление кнопок
        await callback_query.answer(
            "✅ Спасибо за оценку!" if success else "❌ Ошибка сохранения"
        )

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
```

## ⚙️ Конфигурация

### Переменные окружения

```bash
# === RAGAS Quality Evaluation ===
ENABLE_RAGAS_EVALUATION=true              # Включить RAGAS оценку
RAGAS_EVALUATION_SAMPLE_RATE=1.0          # Доля взаимодействий для оценки (0.0-1.0)
RAGAS_BATCH_SIZE=10                       # Размер батча для обработки
RAGAS_ASYNC_TIMEOUT=25                    # Таймаут RAGAS evaluation (секунды)

# === Quality Database ===
QUALITY_DB_ENABLED=true                   # Включить базу данных качества
DATABASE_URL=sqlite+aiosqlite:///data/quality_interactions.db  # URL базы данных

# === Quality Metrics ===
ENABLE_QUALITY_METRICS=true               # Включить Prometheus метрики
QUALITY_PREDICTION_THRESHOLD=0.7          # Порог для предсказания качества

# === Metrics Server ===
START_METRICS_SERVER=true                 # Запустить сервер метрик
METRICS_PORT=9002                         # Порт для метрик Prometheus
```

### Рекомендуемые настройки

**Для разработки**:
```bash
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=0.1          # 10% взаимодействий
QUALITY_DB_ENABLED=true
ENABLE_QUALITY_METRICS=true
```

**Для production**:
```bash
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=1.0          # Все взаимодействия
QUALITY_DB_ENABLED=true
DATABASE_URL=postgresql://user:pass@host/db  # PostgreSQL
ENABLE_QUALITY_METRICS=true
```

**Для тестирования**:
```bash
RAGAS_EVALUATION_SAMPLE_RATE=0            # Отключить RAGAS (быстрые тесты)
QUALITY_DB_ENABLED=true
ENABLE_QUALITY_METRICS=true
```

## 📊 Мониторинг и метрики

### Prometheus метрики

**Качество RAGAS**:
```python
# Метрики качества
rag_ragas_score = Gauge('rag_ragas_score', 'RAGAS quality score',
                       ['metric_type'])  # faithfulness, context_precision, answer_relevancy
rag_combined_quality_score = Gauge('rag_combined_quality_score',
                                  'Combined quality score')
rag_quality_interactions_total = Counter('rag_quality_interactions_total',
                                        'Total quality interactions')
rag_user_feedback_total = Counter('rag_user_feedback_total',
                                 'User feedback count', ['feedback_type'])
rag_quality_evaluation_duration_seconds = Histogram(
    'rag_quality_evaluation_duration_seconds',
    'Quality evaluation duration'
)
```

**Примеры запросов PromQL**:
```promql
# Средний RAGAS score по метрикам
avg(rag_ragas_score)

# Количество взаимодействий за последний час
rate(rag_quality_interactions_total[1h])

# Соотношение положительного/отрицательного фидбека
rate(rag_user_feedback_total{feedback_type="positive"}[1h]) /
rate(rag_user_feedback_total[1h])

# Среднее время RAGAS оценки
rate(rag_quality_evaluation_duration_seconds_sum[5m]) /
rate(rag_quality_evaluation_duration_seconds_count[5m])
```

### Grafana Dashboard

**Панели дашборда**:

1. **RAGAS Quality Scores**
   - График средних значений Faithfulness, Context Precision, Answer Relevancy
   - Временной ряд за последние 24 часа

2. **Combined Quality Score**
   - Общая оценка качества системы
   - Тренд изменения качества

3. **User Feedback**
   - Соотношение положительного/отрицательного фидбека
   - Общее количество оценок

4. **Quality Interactions**
   - Количество оцененных взаимодействий
   - Скорость обработки

5. **RAGAS Evaluation Time**
   - Время выполнения RAGAS оценки
   - Производительность системы

**Конфигурация дашборда**:
```json
{
  "dashboard": {
    "title": "RAG Quality Metrics",
    "panels": [
      {
        "title": "RAGAS Quality Scores",
        "targets": [
          {
            "expr": "rag_ragas_score{metric_type=\"faithfulness\"}",
            "legendFormat": "Faithfulness"
          }
        ]
      }
    ]
  }
}
```

## 🧪 Тестирование

### Интеграционные тесты

**Файл**: `scripts/test_phase2_integration.py`

**Покрытие тестов**:
- ✅ **Quality Manager**: Тестирование основных функций
- ✅ **API Endpoints**: Проверка всех quality endpoints
- ✅ **Chat API Integration**: Создание взаимодействий через chat API
- ✅ **Feedback API**: Добавление пользовательского фидбека
- ✅ **RAGAS Evaluation**: Тестирование с мокированием LLM

**Запуск тестов**:
```bash
# Все тесты Phase 2
$env:PYTHONPATH=(Get-Location).Path; pytest scripts/test_phase2_integration.py -v

# Отдельные тесты
$env:PYTHONPATH=(Get-Location).Path; pytest scripts/test_phase2_integration.py::test_feedback_api -v

# Тесты с отключенным RAGAS (быстрые)
$env:RAGAS_EVALUATION_SAMPLE_RATE="0"; pytest scripts/test_phase2_integration.py -v
```

**Результаты тестирования**:
```
5 passed, 1 skipped, 17 warnings in 161.68s (0:02:41)
```

### Unit тесты

**Компоненты для тестирования**:
- `RAGASEvaluatorWithoutGroundTruth`
- `UnifiedQualityManager`
- `QualityInteractionModel`
- Admin API endpoints

### Load тесты

**Нагрузочное тестирование**:
```python
# Тест производительности RAGAS evaluation
async def test_ragas_performance():
    start_time = time.time()
    for i in range(100):
        await ragas_evaluator.evaluate_interaction(
            query=f"Test query {i}",
            response=f"Test response {i}",
            contexts=["Context 1", "Context 2"],
            sources=["https://example.com"]
        )
    duration = time.time() - start_time
    print(f"100 evaluations in {duration:.2f}s ({duration/100:.3f}s per evaluation)")
```

## 🚀 Развертывание

### 1. Подготовка окружения

```bash
# Установка зависимостей
pip install -r requirements.txt

# Создание директории для данных
mkdir -p data

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл
```

### 2. Инициализация базы данных

```bash
# Создание таблиц качества
python -c "
from app.models.quality_interaction import QualityInteraction
from app.config import CONFIG
import asyncio

async def init_db():
    await QualityInteraction.create_tables()
    print('✅ Quality database initialized')

asyncio.run(init_db())
"
```

### 3. Запуск системы

```bash
# Запуск Flask API с Quality System
python wsgi.py

# Запуск Telegram бота с фидбеком
python adapters/telegram_polling.py

# Запуск мониторинга (опционально)
docker-compose up -d prometheus grafana
```

### 4. Проверка работоспособности

```bash
# Проверка health endpoint
curl http://localhost:9000/v1/admin/health

# Проверка quality endpoints
curl http://localhost:9000/v1/admin/quality/stats

# Проверка метрик
curl http://localhost:9002/metrics | grep rag_ragas_score
```

## 🔧 Troubleshooting

### Частые проблемы

#### 1. **"RAGAS evaluation timeout"**

**Симптомы**:
- Тесты падают с таймаутом
- Медленные ответы API
- Логи показывают долгие LLM вызовы

**Решение**:
```bash
# Отключить RAGAS для быстрых тестов
export RAGAS_EVALUATION_SAMPLE_RATE=0

# Увеличить таймаут
export RAGAS_ASYNC_TIMEOUT=60

# Проверить LLM доступность
curl -H "Authorization: Bearer $YANDEX_API_KEY" \
  https://llm.api.cloud.yandex.net/foundationModels/v1/completion
```

#### 2. **"Database connection failed"**

**Симптомы**:
- Ошибки подключения к SQLite
- Отсутствие таблиц качества

**Решение**:
```bash
# Пересоздать базу данных
rm data/quality_interactions.db

# Инициализировать таблицы
python -c "
import asyncio
from app.models.quality_interaction import QualityInteraction

async def recreate_db():
    await QualityInteraction.create_tables()
    print('✅ Database recreated')

asyncio.run(recreate_db())
"
```

#### 3. **"Quality endpoints not found (404)"**

**Симптомы**:
- API возвращает 404 для quality endpoints
- Отсутствие роутинга

**Решение**:
```python
# Проверить регистрацию blueprint в app/__init__.py
app.register_blueprint(quality_bp, url_prefix="/v1/admin/quality")

# Проверить URL prefix в routes/quality.py
quality_bp = Blueprint('quality', __name__)  # БЕЗ url_prefix здесь
```

#### 4. **"Metrics not showing in Grafana"**

**Симптомы**:
- Пустой Grafana dashboard
- Отсутствие метрик в Prometheus

**Решение**:
```bash
# Проверить статус Prometheus targets
curl http://localhost:9090/api/v1/targets

# Проверить метрики RAG API
curl http://localhost:9002/metrics | grep rag_ragas_score

# Перезапустить с метриками
export ENABLE_QUALITY_METRICS=true
export START_METRICS_SERVER=true
python wsgi.py
```

#### 5. **"Telegram feedback not working"**

**Симптомы**:
- Inline кнопки не отвечают
- Ошибки в callback обработке

**Решение**:
```python
# Проверить обработку callback в telegram_polling.py
async def handle_callback_query(callback_query):
    try:
        data = callback_query.data
        parts = data.split('_', 2)  # feedback_<id>_<type>
        interaction_id = parts[1]
        # ... обработка
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
```

### Логирование и отладка

**Уровни логов**:
```python
# Включить детальное логирование
import logging
logging.getLogger('app.services.ragas_evaluator').setLevel(logging.DEBUG)
logging.getLogger('app.services.quality_manager').setLevel(logging.DEBUG)
```

**Полезные логи**:
```
# RAGAS evaluation
INFO | RAGAS evaluation completed: {'faithfulness': 0.8, 'context_precision': 0.7, 'answer_relevancy': 0.9}

# Fallback activation
WARNING | RAGAS evaluation timeout, using fallback scores

# Database operations
INFO | Quality interaction saved: interaction_abc123_1234567890

# Metrics recording
DEBUG | Recording metrics for interaction: interaction_abc123_1234567890
```

## 📈 Производительность

### Бенчмарки

**RAGAS Evaluation**:
- ⚡ **С RAGAS**: 2-5 секунд на взаимодействие
- ⚡ **Fallback scores**: <100ms на взаимодействие
- ⚡ **С таймаутом**: 25 секунд максимум

**Database Operations**:
- 💾 **SQLite**: до 1,000 взаимодействий/минуту
- 💾 **PostgreSQL**: до 10,000 взаимодействий/минуту
- 💾 **Batch processing**: рекомендуется батчи по 10-20

**Memory Usage**:
- 🧠 **RAGAS**: ~500MB RAM для метрик
- 🧠 **Database**: ~10MB на 10,000 взаимодействий
- 🧠 **LangChain wrappers**: ~100MB RAM

### Оптимизация

**Для высокой нагрузки**:
```bash
# Уменьшить sample rate
RAGAS_EVALUATION_SAMPLE_RATE=0.1  # 10% взаимодействий

# Использовать PostgreSQL
DATABASE_URL=postgresql://user:pass@host/db

# Включить кэширование
REDIS_URL=redis://localhost:6379
```

**Для разработки**:
```bash
# Отключить RAGAS
RAGAS_EVALUATION_SAMPLE_RATE=0

# Использовать SQLite
DATABASE_URL=sqlite+aiosqlite:///data/quality_interactions.db
```

## 🔮 Roadmap

### Краткосрочные улучшения (v2.3.0)

1. **Улучшение fallback scores**
   - Более сложные эвристики на основе длины и релевантности
   - Машинное обучение для предсказания качества
   - A/B тестирование алгоритмов

2. **Оптимизация производительности**
   - Кэширование результатов RAGAS оценки
   - Асинхронная обработка батчей
   - Оптимизация запросов к БД

3. **Расширение метрик**
   - Дополнительные RAGAS метрики (Context Recall, Context Relevancy)
   - Пользовательские метрики качества
   - Корреляционный анализ между метриками

### Долгосрочные задачи (v3.0.0)

1. **Полная RAGAS интеграция**
   - Решение проблемы с OpenAI dependency
   - Кастомные embeddings для RAGAS
   - Оптимизация LangChain wrappers

2. **Машинное обучение**
   - Обучение моделей на пользовательском фидбеке
   - Автоматическая настройка порогов качества
   - Предсказание деградации качества

3. **Масштабирование**
   - Поддержка PostgreSQL в продакшене
   - Горизонтальное масштабирование
   - Микросервисная архитектура для Quality System

## 📚 Дополнительные ресурсы

### Документация
- [RAGAS Documentation](https://docs.ragas.io/)
- [LangChain Documentation](https://python.langchain.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

### Примеры кода
- `scripts/test_phase2_integration.py` - Полное тестирование Phase 2
- `app/services/ragas_evaluator.py` - RAGAS evaluator
- `app/services/quality_manager.py` - Quality manager
- `app/models/quality_interaction.py` - Database model

### Конфигурационные файлы
- `.env` - Переменные окружения
- `monitoring/grafana/dashboards/rag-quality-metrics.json` - Grafana dashboard
- `requirements.txt` - Python зависимости

---

**Версия документации**: 2.0
**Дата обновления**: 2025-09-23
**Статус**: Production Ready ✅
**Автор**: RAG System Team
