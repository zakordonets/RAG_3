# 📊 RAGAS Quality System Documentation

## Обзор

Система оценки качества RAG (Retrieval-Augmented Generation) на основе RAGAS (Retrieval-Augmented Generation Assessment) для автоматической оценки качества ответов чат-бота.

## 🏗️ Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram Bot  │───▶│  RAG Orchestrator │───▶│  Quality Manager │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   RAGAS Evaluator │    │ Quality Database │
                       └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Fallback Scores │    │  Metrics System │
                       └──────────────────┘    └─────────────────┘
```

## 📋 Компоненты

### 1. RAGAS Evaluator (`app/services/ragas_evaluator.py`)

**Назначение**: Оценка качества взаимодействий с использованием RAGAS метрик.

**Метрики**:
- **Faithfulness**: Насколько ответ соответствует предоставленному контексту
- **Context Precision**: Насколько релевантен извлеченный контекст
- **Answer Relevancy**: Насколько релевантен ответ пользовательскому запросу

**Реализация**:
```python
class RAGASEvaluatorWithoutGroundTruth:
    def __init__(self):
        self.llm_wrapper = YandexGPTLangChainWrapper()
        self.embeddings_wrapper = BGELangChainWrapper()

        self.faithfulness = Faithfulness(llm=self.llm_wrapper)
        self.context_precision = ContextPrecision(llm=self.llm_wrapper)
        self.answer_relevancy = AnswerRelevancy(llm=self.llm_wrapper)
```

### 2. Quality Manager (`app/services/quality_manager.py`)

**Назначение**: Управление процессом оценки качества и интеграция с системой.

**Функции**:
- Оценка взаимодействий
- Сохранение результатов в базу данных
- Обработка пользовательского фидбека
- Генерация статистики качества

### 3. Quality Database (`app/models/quality_interaction.py`)

**Назначение**: Хранение данных о качестве взаимодействий.

**Схема**:
```sql
CREATE TABLE quality_interactions (
    interaction_id VARCHAR(255) PRIMARY KEY,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    contexts TEXT,
    sources TEXT,
    ragas_faithfulness FLOAT,
    ragas_context_precision FLOAT,
    ragas_answer_relevancy FLOAT,
    ragas_overall_score FLOAT,
    user_feedback_type VARCHAR(50),
    user_feedback_text TEXT,
    combined_score FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## ⚙️ Конфигурация

### Переменные окружения

```bash
# RAGAS Quality Evaluation
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=0.1
RAGAS_BATCH_SIZE=10
RAGAS_ASYNC_TIMEOUT=30
RAGAS_LLM_MODEL=yandexgpt

# Quality Database
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite:///data/quality_interactions.db

# Quality Metrics
ENABLE_QUALITY_METRICS=true
QUALITY_PREDICTION_THRESHOLD=0.7
```

### Параметры конфигурации

| Параметр | Описание | По умолчанию | Влияние |
|----------|----------|--------------|---------|
| `ENABLE_RAGAS_EVALUATION` | Включить оценку RAGAS | `false` | Основной переключатель системы |
| `RAGAS_EVALUATION_SAMPLE_RATE` | Доля взаимодействий для оценки | `0.1` | Производительность vs точность |
| `RAGAS_BATCH_SIZE` | Размер батча для обработки | `10` | Память и скорость |
| `RAGAS_ASYNC_TIMEOUT` | Таймаут асинхронных операций | `30` | Надежность |
| `QUALITY_DB_ENABLED` | Включить базу данных качества | `false` | Хранение данных |
| `DATABASE_URL` | URL базы данных | SQLite | Масштабируемость |
| `ENABLE_QUALITY_METRICS` | Включить метрики Prometheus | `false` | Мониторинг |

## 🚀 Использование

### Инициализация

```python
from app.services.quality_manager import quality_manager

# Инициализация
await quality_manager.initialize()

# Оценка взаимодействия
interaction_id = await quality_manager.evaluate_interaction(
    query="Как настроить маршрутизацию?",
    response="Маршрутизация настраивается через API...",
    contexts=["Контекст 1", "Контекст 2"],
    sources=["https://docs.example.com"]
)

# Добавление пользовательского фидбека
await quality_manager.add_user_feedback(
    interaction_id=interaction_id,
    feedback_type="positive",
    feedback_text="Отличный ответ!"
)
```

### Получение статистики

```python
# Статистика качества
stats = await quality_manager.get_quality_statistics(days=7)
print(f"Общее количество взаимодействий: {stats['total_interactions']}")
print(f"Средний RAGAS score: {stats['avg_ragas_score']:.3f}")
print(f"Процент удовлетворенности: {stats['satisfaction_rate']:.1f}%")
```

## 🔧 Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

**Ключевые зависимости**:
- `ragas==0.1.21` - Основная библиотека RAGAS
- `datasets==2.19.0` - Обработка данных
- `langchain==0.2.16` - Интеграция с LLM
- `sqlalchemy==2.0.23` - База данных
- `alembic==1.13.1` - Миграции

### 2. Инициализация базы данных

```bash
python scripts/init_quality_db.py
```

### 3. Тестирование системы

```bash
python scripts/test_ragas_integration.py
python scripts/test_simple_ragas.py
```

## ⚠️ Ограничения и требования

### Критические ограничения

#### 1. **RAGAS OpenAI Dependency**
**Проблема**: RAGAS метрики (`ContextPrecision`, `AnswerRelevancy`) **внутренне используют OpenAI embeddings** по умолчанию.

**Ошибка**:
```
1 validation error for OpenAIEmbeddings
Did not find openai_api_key
```

**Решение**: Система автоматически переключается на **fallback scores** при ошибке.

#### 2. **LangChain Compatibility**
**Проблема**: Требуется точная совместимость версий LangChain с RAGAS.

**Поддерживаемые версии**:
- `langchain==0.2.16`
- `langchain-community==0.2.16`
- `langchain-core==0.2.38`
- `ragas==0.1.21`

**Несовместимые версии**:
- `langchain>=0.3.0` - вызывает ошибки импорта
- `ragas>=0.2.0` - изменился API

#### 3. **Dataset Format Requirements**
**Проблема**: RAGAS требует точный формат Dataset.

**Требования**:
```python
dataset = Dataset.from_dict({
    'question': [query],           # string
    'answer': [response],          # string
    'contexts': [contexts],        # List[string]
    'ground_truth': [""]           # string (не List[string]!)
})
```

### Производительность

#### 1. **Время выполнения**
- **RAGAS evaluation**: 2-5 секунд на взаимодействие
- **Fallback scores**: <100ms на взаимодействие
- **Database operations**: <50ms на операцию

#### 2. **Память**
- **RAGAS**: ~500MB RAM для метрик
- **Database**: ~10MB на 10,000 взаимодействий
- **LangChain wrappers**: ~100MB RAM

#### 3. **Масштабируемость**
- **SQLite**: до 1,000 взаимодействий/минуту
- **PostgreSQL**: до 10,000 взаимодействий/минуту
- **Batch processing**: рекомендуется батчи по 10-20

### Надежность

#### 1. **Fallback Mechanism**
Система автоматически переключается на fallback scores при:
- Ошибках RAGAS evaluation
- Отсутствии OpenAI API ключа
- Проблемах с LangChain wrappers
- Ошибках Dataset форматирования

#### 2. **Error Handling**
```python
try:
    # RAGAS evaluation
    scores = await ragas_evaluator.evaluate_interaction(...)
except Exception as e:
    logger.error(f"RAGAS evaluation failed: {e}")
    # Automatic fallback
    scores = self._calculate_fallback_scores(...)
```

#### 3. **Database Resilience**
- Автоматическое создание таблиц
- Graceful degradation при ошибках БД
- Транзакционная безопасность

## 📊 Мониторинг и метрики

### Prometheus метрики

```python
# RAGAS scores
ragas_score_gauge = Gauge('ragas_score', 'RAGAS quality score', ['metric_type'])
user_satisfaction_rate = Gauge('user_satisfaction_rate', 'User satisfaction rate')
quality_evaluation_duration = Histogram('quality_evaluation_duration_seconds', 'Quality evaluation duration')

# Recording metrics
metrics_collector.record_ragas_score(
    faithfulness=0.8,
    context_precision=0.7,
    answer_relevancy=0.9,
    overall_score=0.8
)
```

### Grafana Dashboard

**Доступные метрики**:
- RAGAS scores по типам метрик
- User satisfaction rate
- Quality evaluation duration
- Database interaction count
- Error rates

**URL**: `http://localhost:8080` (Grafana)

## 🛠️ Troubleshooting

### Частые проблемы

#### 1. **"OpenAI API key not found"**
**Причина**: RAGAS пытается использовать OpenAI embeddings.

**Решение**:
- Убедитесь, что `ENABLE_RAGAS_EVALUATION=false` для отключения RAGAS
- Или используйте fallback scores (автоматически)

#### 2. **"LangChain import errors"**
**Причина**: Несовместимые версии LangChain.

**Решение**:
```bash
pip uninstall langchain langchain-community langchain-core
pip install langchain==0.2.16 langchain-community==0.2.16 langchain-core==0.2.38
```

#### 3. **"Database connection failed"**
**Причина**: Проблемы с базой данных.

**Решение**:
```bash
# Пересоздать базу данных
rm data/quality_interactions.db
python scripts/init_quality_db.py
```

#### 4. **"RAGAS evaluation timeout"**
**Причина**: Медленные LLM вызовы.

**Решение**:
- Увеличить `RAGAS_ASYNC_TIMEOUT`
- Уменьшить `RAGAS_EVALUATION_SAMPLE_RATE`
- Использовать fallback scores

### Логирование

**Уровни логов**:
- `INFO`: Нормальная работа системы
- `WARNING`: Проблемы, не критичные для работы
- `ERROR`: Критические ошибки, fallback активирован
- `DEBUG`: Детальная информация для отладки

**Пример логов**:
```
2025-09-21 22:07:39.993 | INFO | RAGAS evaluation completed: {'faithfulness': 0.7, 'context_precision': 0.6, 'answer_relevancy': 0.8, 'overall_score': 0.7}
2025-09-21 22:07:39.993 | ERROR | RAGAS evaluation failed: OpenAI API key not found
2025-09-21 22:07:39.993 | INFO | Using fallback scores: {'faithfulness': 0.7, 'context_precision': 0.6, 'answer_relevancy': 0.8, 'overall_score': 0.7}
```

## 🔮 Roadmap и улучшения

### Краткосрочные задачи

1. **Улучшение fallback scores**
   - Более сложные эвристики
   - Машинное обучение для предсказания качества
   - A/B тестирование алгоритмов

2. **Оптимизация производительности**
   - Кэширование результатов оценки
   - Асинхронная обработка батчей
   - Оптимизация запросов к БД

3. **Расширение метрик**
   - Дополнительные RAGAS метрики
   - Пользовательские метрики качества
   - Корреляционный анализ

### Долгосрочные задачи

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
   - Микросервисная архитектура

## 📚 Дополнительные ресурсы

### Документация
- [RAGAS Documentation](https://docs.ragas.io/)
- [LangChain Documentation](https://python.langchain.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

### Примеры использования
- `scripts/test_ragas_integration.py` - Полное тестирование
- `scripts/test_simple_ragas.py` - Простое тестирование
- `scripts/init_quality_db.py` - Инициализация БД

### Конфигурационные файлы
- `env.example` - Пример конфигурации
- `app/config.py` - Основная конфигурация
- `monitoring/prometheus.yml` - Настройки мониторинга

---

**Версия документации**: 1.0
**Дата обновления**: 2025-09-21
**Автор**: RAG System Team
