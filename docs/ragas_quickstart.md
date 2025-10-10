# 🚀 RAGAS Quality System - Quick Start

Запуск системы оценки качества за 5 минут.

**Версия**: 1.1
**Дата обновления**: 9 октября 2024

---

## ⚡ Быстрый старт

### Шаг 1: Установка зависимостей

```bash
pip install -r requirements.txt
```

**Что будет установлено:**
- `ragas==0.1.21` - Основная библиотека
- `langchain==0.2.16` - LLM интеграция
- `datasets==2.19.0` - Обработка данных
- `sqlalchemy==2.0.23` - База данных

### Шаг 2: Настройка конфигурации

```bash
cp env.example .env
```

**Минимальная конфигурация** (добавьте в `.env`):

```bash
# RAGAS Evaluation
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=0.1
RAGAS_BATCH_SIZE=10
RAGAS_ASYNC_TIMEOUT=30

# Quality Database
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite:///data/quality_interactions.db

# Metrics
ENABLE_QUALITY_METRICS=true
QUALITY_PREDICTION_THRESHOLD=0.7
```

### Шаг 3: Инициализация базы данных

```bash
python scripts/init_quality_db.py
```

**Вывод:**
```
✅ Database initialized successfully
📊 Created table: quality_interactions
```

### Шаг 4: Проверка работоспособности

```bash
# Простой тест
python scripts/test_simple_ragas.py

# Полное тестирование
pytest tests/test_ragas_quality.py -v
```

**Ожидаемый результат:**
```
✅ RAGAS Evaluation Results:
   Faithfulness: 0.700
   Context Precision: 0.600
   Answer Relevancy: 0.800
   Overall Score: 0.700

✅ All tests passed!
```

---

## 🎯 Использование в коде

### Базовая интеграция

```python
from app.services.quality_manager import quality_manager

# Инициализация (один раз при старте)
await quality_manager.initialize()

# Оценка взаимодействия
interaction_id = await quality_manager.evaluate_interaction(
    query="Как настроить маршрутизацию?",
    response="Маршрутизация настраивается через API...",
    contexts=["Контекст 1", "Контекст 2"],
    sources=["https://docs.example.com/routing"]
)
```

### Добавление пользовательского фидбека

```python
# Положительная оценка
await quality_manager.add_user_feedback(
    interaction_id=interaction_id,
    feedback_type="positive",
    feedback_text="Отличный ответ!"
)

# Отрицательная оценка
await quality_manager.add_user_feedback(
    interaction_id=interaction_id,
    feedback_type="negative",
    feedback_text="Не хватает деталей"
)
```

### Получение статистики

```python
# Статистика за последние 7 дней
stats = await quality_manager.get_quality_statistics(days=7)

print(f"Взаимодействий: {stats['total_interactions']}")
print(f"Средний RAGAS score: {stats['avg_ragas_score']:.3f}")
print(f"Удовлетворенность: {stats['satisfaction_rate']:.1f}%")
```

---

## ⚠️ Важные ограничения

### 1. OpenAI зависимость

**Проблема**: RAGAS использует OpenAI embeddings внутри некоторых метрик.

**Что происходит:**
```python
# При отсутствии OpenAI API ключа
1 validation error for OpenAIEmbeddings
Did not find openai_api_key
```

**Решение**: Система **автоматически** переключается на fallback scores:
- ✅ Работает без OpenAI
- ✅ Производительность: <100ms (vs 2-5 сек с RAGAS)
- ⚠️ Упрощенная оценка на эвристиках

### 2. Версии зависимостей

**Критично важно** не обновлять:

| Пакет | Версия | Почему |
|-------|--------|---------|
| `ragas` | 0.1.21 | API изменился в 0.2.x |
| `langchain` | 0.2.16 | Несовместимость с 0.3.x |
| `datasets` | 2.19.0 | Формат данных |

### 3. Производительность

**Рекомендации:**
- `RAGAS_EVALUATION_SAMPLE_RATE=0.1` - оценивать 10% запросов
- Использовать fallback для production
- Настроить асинхронную обработку

---

## 🔧 Troubleshooting

### "OpenAI API key not found"

**Это нормально!** Система использует fallback scores.

**Если нужен полный RAGAS:**
```bash
# Добавьте в .env
OPENAI_API_KEY=your_key_here
```

### "LangChain import errors"

```bash
# Переустановите с точными версиями
pip uninstall langchain langchain-community langchain-core
pip install langchain==0.2.16 langchain-community==0.2.16 langchain-core==0.2.38
```

### "Database connection failed"

```bash
# Пересоздайте базу
rm data/quality_interactions.db
python scripts/init_quality_db.py
```

### "RAGAS evaluation timeout"

```bash
# Увеличьте таймаут в .env
RAGAS_ASYNC_TIMEOUT=60

# Или уменьшите sample rate
RAGAS_EVALUATION_SAMPLE_RATE=0.05
```

---

## 📊 Мониторинг

### Prometheus метрики

Доступны на `http://localhost:9000/metrics`:

```
# RAGAS scores
ragas_score{metric_type="faithfulness"} 0.7
ragas_score{metric_type="context_precision"} 0.6
ragas_score{metric_type="answer_relevancy"} 0.8

# User satisfaction
user_satisfaction_rate 0.75
```

### Grafana Dashboard

```bash
# Запуск мониторинга
.\start_monitoring.ps1  # Windows
./start_monitoring.sh   # Linux/Mac

# Открыть Grafana
open http://localhost:3000
```

**Credentials:** admin / admin123

### Логи

```bash
# Просмотр логов качества
grep "RAGAS\|Quality" logs/app.log

# Только ошибки
grep "ERROR.*RAGAS" logs/app.log
```

---

## 📈 Метрики качества

### Автоматические (RAGAS)

| Метрика | Описание | Диапазон |
|---------|----------|----------|
| **Faithfulness** | Соответствие ответа контексту | 0.0 - 1.0 |
| **Context Precision** | Релевантность контекста | 0.0 - 1.0 |
| **Answer Relevancy** | Релевантность ответа | 0.0 - 1.0 |
| **Overall Score** | Общая оценка | 0.0 - 1.0 |

### Пользовательские

- 👍 **Positive feedback** - положительная оценка
- 👎 **Negative feedback** - отрицательная оценка
- 📊 **Satisfaction rate** - процент удовлетворенности

---

## 🎯 Следующие шаги

1. ✅ Система запущена
2. 📖 Изучите [полную документацию](ragas_quality_system.md)
3. 🔧 Настройте [мониторинг](monitoring_setup.md)
4. 📊 Анализируйте качество ответов
5. 🚀 Оптимизируйте конфигурацию

---

## 🔗 Связанные документы

- [RAGAS Quality System](ragas_quality_system.md) - Полная техническая документация
- [Architecture](architecture.md) - Архитектура RAG системы
- [Monitoring Setup](monitoring_setup.md) - Настройка мониторинга

---

**Вопросы?** Создайте issue или см. [Troubleshooting](ragas_quality_system.md#troubleshooting) в полной документации.
