# 📊 RAGAS Quality System

## О системе

Система автоматической оценки качества ответов RAG (Retrieval-Augmented Generation) с использованием метрик RAGAS и пользовательского фидбека.

**Версия**: 1.1
**Дата обновления**: 9 октября 2024

---

## 📚 Документация

### Для быстрого старта
👉 **[Quick Start Guide](ragas_quickstart.md)** - Запуск за 5 минут

**Содержание:**
- Минимальная настройка
- Первый запуск
- Базовое тестирование
- Troubleshooting

### Для разработчиков
👉 **[RAGAS Quality System](ragas_quality_system.md)** - Полная техническая документация

**Содержание:**
- Архитектура системы
- API и интеграция
- Конфигурация
- Мониторинг и метрики
- Troubleshooting
- Roadmap

---

## ⚡ Возможности

| Функция | Описание | Статус |
|---------|----------|--------|
| **Автоматическая оценка** | RAGAS метрики (faithfulness, precision, relevancy) | ✅ Работает |
| **Fallback scores** | Умные эвристики при недоступности OpenAI | ✅ Production ready |
| **База данных** | SQLite/PostgreSQL для хранения истории | ✅ Работает |
| **Пользовательский фидбек** | Кнопки 👍/👎 в Telegram | ✅ Интегрировано |
| **Prometheus метрики** | Мониторинг качества в реальном времени | ✅ Настроено |
| **Grafana дашборд** | Визуализация статистики | ✅ Готов |

---

## ⚠️ Важно знать

### Критические требования

**Версии зависимостей** (не обновлять!):
- RAGAS: `0.1.21`
- LangChain: `0.2.16`
- Datasets: `2.19.0`

**OpenAI зависимость:**
- RAGAS требует OpenAI для некоторых метрик
- Система работает **без OpenAI** через fallback
- Производительность: fallback <100ms vs RAGAS 2-5 сек

### Рекомендуемая конфигурация

```bash
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=0.1  # Оценивать 10% запросов
QUALITY_DB_ENABLED=true
ENABLE_QUALITY_METRICS=true
```

---

## 🚀 Начало работы

### 1-минутная проверка

```bash
# Установка
pip install -r requirements.txt

# Инициализация
python scripts/init_quality_db.py

# Тест
python scripts/test_simple_ragas.py
```

### Результат теста

```
✅ RAGAS Evaluation Results:
   Faithfulness: 0.700
   Context Precision: 0.600
   Answer Relevancy: 0.800
   Overall Score: 0.700
```

👉 **Полная инструкция**: [ragas_quickstart.md](ragas_quickstart.md)

---

## 📊 Метрики качества

### Автоматические (RAGAS)
- **Faithfulness** - Соответствие ответа контексту
- **Context Precision** - Релевантность извлеченного контекста
- **Answer Relevancy** - Релевантность ответа запросу

### Пользовательские
- **Positive/Negative feedback** - Оценки через 👍/👎
- **Satisfaction rate** - Процент удовлетворенности
- **Correlation analysis** - Связь между метриками

---

## 🔗 Связанные ресурсы

- [Architecture Overview](architecture.md) - Общая архитектура RAG системы
- [Monitoring Setup](monitoring_setup.md) - Настройка Grafana/Prometheus
- [API Reference](api_reference.md) - REST API документация

---

## 💬 Поддержка

**Вопросы?** См. секцию Troubleshooting в [полной документации](ragas_quality_system.md) или создайте issue.
