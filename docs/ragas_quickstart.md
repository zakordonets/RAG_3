# 🚀 RAGAS Quality System - Quick Start

## Быстрый запуск

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации

Скопируйте `env.example` в `.env` и настройте:

```bash
cp env.example .env
```

**Минимальная конфигурация для RAGAS**:
```bash
# RAGAS Quality Evaluation
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=0.1
RAGAS_BATCH_SIZE=10
RAGAS_ASYNC_TIMEOUT=30

# Quality Database
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite:///data/quality_interactions.db

# Quality Metrics
ENABLE_QUALITY_METRICS=true
QUALITY_PREDICTION_THRESHOLD=0.7
```

### 3. Инициализация базы данных

```bash
python scripts/init_quality_db.py
```

### 4. Тестирование системы

```bash
python scripts/test_simple_ragas.py
```

### 5. Запуск полного тестирования

```bash
pytest tests/test_ragas_quality.py -v
```

## ⚠️ Важные ограничения

### OpenAI Dependency
- **Проблема**: RAGAS требует OpenAI API ключ для некоторых метрик
- **Решение**: Система автоматически использует fallback scores
- **Статус**: Работает без OpenAI, но с упрощенной оценкой

### Версии зависимостей
- **RAGAS**: `0.1.21` (не обновлять до 0.2.x)
- **LangChain**: `0.2.16` (не обновлять до 0.3.x)
- **Datasets**: `2.19.0`

### Производительность
- **RAGAS evaluation**: 2-5 секунд на взаимодействие
- **Fallback scores**: <100ms на взаимодействие
- **Рекомендуется**: `RAGAS_EVALUATION_SAMPLE_RATE=0.1` (10% взаимодействий)

## 📊 Что вы получите

### Автоматическая оценка качества
- **Faithfulness**: Соответствие ответа контексту
- **Context Precision**: Релевантность извлеченного контекста
- **Answer Relevancy**: Релевантность ответа запросу

### Пользовательский фидбек
- Кнопки 👍/👎 в Telegram
- Сохранение оценок в базе данных
- Корреляционный анализ

### Мониторинг
- Prometheus метрики
- Grafana dashboard
- Статистика качества

## 🔧 Troubleshooting

### "OpenAI API key not found"
**Это нормально!** Система автоматически переключится на fallback scores.

### "LangChain import errors"
```bash
pip uninstall langchain langchain-community langchain-core
pip install langchain==0.2.16 langchain-community==0.2.16 langchain-core==0.2.38
```

### "Database connection failed"
```bash
rm data/quality_interactions.db
python scripts/init_quality_db.py
```

## 📈 Мониторинг

### Prometheus метрики
- `ragas_score` - RAGAS оценки по типам метрик
- `user_satisfaction_rate` - Процент удовлетворенности
- `quality_evaluation_duration` - Время оценки качества

### Grafana Dashboard
URL: `http://localhost:8080`

### Логи
```bash
# Просмотр логов качества
grep "RAGAS\|Quality" logs/app.log
```

## 🎯 Следующие шаги

1. **Интеграция с Telegram ботом**
2. **Настройка Grafana dashboard**
3. **Анализ качества ответов**
4. **Оптимизация системы**

---

**Полная документация**: [docs/ragas_quality_system.md](ragas_quality_system.md)
