# 📊 RAGAS Quality System - Technical Documentation

Полная техническая документация системы оценки качества RAG.

**Версия**: 1.1
**Дата обновления**: 9 октября 2024

---

## 📖 Содержание

- [Обзор](#обзор)
- [Архитектура](#архитектура)
- [Компоненты](#компоненты)
- [Конфигурация](#конфигурация)
- [Использование](#использование)
- [Ограничения](#ограничения)
- [Мониторинг](#мониторинг)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Обзор

RAGAS Quality System - система автоматической оценки качества ответов RAG (Retrieval-Augmented Generation) с использованием метрик RAGAS и пользовательского фидбека.

### Основные возможности

- ✅ Автоматическая оценка через RAGAS метрики
- ✅ Fallback механизм при недоступности OpenAI
- ✅ База данных для хранения истории взаимодействий
- ✅ Пользовательский фидбек (👍/👎)
- ✅ Prometheus метрики для мониторинга
- ✅ Корреляционный анализ оценок

### Быстрый старт

👉 См. [Quick Start Guide](ragas_quickstart.md) для пошаговой инструкции.

---

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

### Зависимости

**Критические версии** (не обновлять!):

```txt
ragas==0.1.21              # Основная библиотека RAGAS
datasets==2.19.0           # Обработка данных
langchain==0.2.16          # LLM интеграция
langchain-community==0.2.16
langchain-core==0.2.38
sqlalchemy==2.0.23         # База данных
alembic==1.13.1           # Миграции
```

### Установка

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Инициализировать базу данных
python scripts/init_quality_db.py

# 3. Проверить работоспособность
pytest tests/test_ragas_quality.py -v
```

👉 **Детали установки**: [ragas_quickstart.md](ragas_quickstart.md)

---

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

**Время выполнения:**

| Операция | Время | Рекомендации |
|----------|-------|--------------|
| RAGAS evaluation | 2-5 сек | Используйте sample rate 10% |
| Fallback scores | <100ms | Подходит для production |
| Database operations | <50ms | Оптимизировано |

**Потребление ресурсов:**
- RAM: ~500MB (RAGAS метрики)
- Disk: ~10MB на 10,000 взаимодействий
- CPU: Зависит от LLM вызовов

**Масштабируемость:**
- SQLite: до 1,000 взаимодействий/минуту
- PostgreSQL: до 10,000 взаимодействий/минуту
- Batch processing: батчи по 10-20 записей

### Надежность

**Fallback Mechanism:**

Система автоматически переключается на fallback при:
- ❌ Ошибках RAGAS evaluation
- ❌ Отсутствии OpenAI API ключа
- ❌ Проблемах с LangChain wrappers
- ❌ Ошибках форматирования Dataset

**Обработка ошибок:**

```python
try:
    scores = await ragas_evaluator.evaluate_interaction(...)
except Exception as e:
    logger.error(f"RAGAS failed: {e}")
    # Автоматический fallback
    scores = self._calculate_fallback_scores(...)
```

---

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

### Частые проблемы и решения

#### 1. "OpenAI API key not found"

**Причина**: RAGAS пытается использовать OpenAI embeddings по умолчанию.

**Решение**:
- ✅ Система автоматически использует fallback scores
- Или установите `ENABLE_RAGAS_EVALUATION=false` в `.env`
- Или добавьте `OPENAI_API_KEY=your_key` для полного RAGAS

#### 2. "LangChain import errors"

**Симптомы**:
```
ImportError: cannot import name 'X' from 'langchain.Y'
```

**Решение**:
```bash
pip uninstall langchain langchain-community langchain-core
pip install langchain==0.2.16 langchain-community==0.2.16 langchain-core==0.2.38
```

#### 3. "Database connection failed"

**Причина**: Проблемы с файлом или схемой БД.

**Решение**:
```bash
# Пересоздать базу данных
rm data/quality_interactions.db
python scripts/init_quality_db.py
```

#### 4. "RAGAS evaluation timeout"

**Причина**: Медленные LLM вызовы или сетевые проблемы.

**Решение**:
```bash
# В .env увеличьте таймаут
RAGAS_ASYNC_TIMEOUT=60

# Или уменьшите частоту оценки
RAGAS_EVALUATION_SAMPLE_RATE=0.05
```

#### 5. "Dataset format errors"

**Причина**: Неправильный формат данных для RAGAS.

**Проверка**:
```python
# ground_truth должен быть строкой, не списком!
dataset = Dataset.from_dict({
    'question': ["query"],
    'answer': ["response"],
    'contexts': [["context1", "context2"]],  # List[List[str]]
    'ground_truth': [""]  # str, НЕ List[str]!
})
```

### Диагностика

**Логи качества:**
```bash
# Просмотр логов RAGAS
grep "RAGAS\|Quality" logs/app.log | tail -50

# Только ошибки
grep "ERROR.*RAGAS" logs/error.log

# Статистика fallback
grep "fallback scores" logs/app.log | wc -l
```

**Проверка метрик:**
```bash
# Prometheus метрики
curl http://localhost:9000/metrics | grep ragas

# Проверка БД
sqlite3 data/quality_interactions.db "SELECT COUNT(*) FROM quality_interactions;"
```

### Уровни логирования

| Уровень | Использование | Пример |
|---------|---------------|--------|
| `DEBUG` | Детальная отладка | Параметры RAGAS вызовов |
| `INFO` | Нормальная работа | Успешная оценка качества |
| `WARNING` | Проблемы, не критичные | Fallback активирован |
| `ERROR` | Критические ошибки | RAGAS evaluation failed |

---

## 🔮 Roadmap

### Версия 1.2 (Q4 2024)

**Оптимизация производительности:**
- [ ] Кэширование результатов RAGAS оценки
- [ ] Асинхронная батч-обработка
- [ ] Оптимизация запросов к БД

**Улучшение fallback:**
- [ ] ML-модель для предсказания качества
- [ ] Более сложные эвристики
- [ ] A/B тестирование алгоритмов

### Версия 1.3 (Q1 2025)

**Расширение метрик:**
- [ ] Дополнительные RAGAS метрики
- [ ] Пользовательские метрики качества
- [ ] Корреляционный анализ

**Интеграция:**
- [ ] Поддержка PostgreSQL в production
- [ ] Экспорт данных для аналитики
- [ ] REST API для оценки качества

### Долгосрочные цели

**Полная RAGAS интеграция:**
- Решение OpenAI dependency
- Кастомные embeddings для RAGAS
- Оптимизация LangChain wrappers

**Машинное обучение:**
- Обучение на пользовательском фидбеке
- Автоматическая настройка порогов
- Предсказание деградации качества

**Масштабирование:**
- Микросервисная архитектура
- Горизонтальное масштабирование
- Multi-tenant поддержка

---

## 📚 Дополнительные ресурсы

### Внешняя документация
- [RAGAS Documentation](https://docs.ragas.io/) - Официальная документация RAGAS
- [LangChain Documentation](https://python.langchain.com/) - Документация LangChain
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/) - Работа с БД

### Примеры и тесты
- `tests/test_ragas_quality.py` - Полное тестирование системы
- `scripts/test_simple_ragas.py` - Простое тестирование RAGAS
- `scripts/init_quality_db.py` - Инициализация БД

### Связанная документация
- [Quick Start Guide](ragas_quickstart.md) - Быстрый старт
- [Architecture Overview](architecture.md) - Общая архитектура
- [Monitoring Setup](monitoring_setup.md) - Настройка мониторинга
- [API Reference](api_reference.md) - REST API документация

### Конфигурационные файлы
- `env.example` - Пример конфигурации окружения
- `app/config/app_config.py` - Основная конфигурация приложения
- `monitoring/prometheus.yml` - Настройки Prometheus

---

## 💬 Поддержка

**Вопросы или проблемы?**
- 📖 Изучите [Quick Start Guide](ragas_quickstart.md)
- 🔍 Проверьте [Troubleshooting](#troubleshooting)
- 🐛 Создайте issue в репозитории

---

**Версия документации**: 1.1
**Последнее обновление**: 9 октября 2024
