# 📊 RAGAS Quality System - Documentation Index

## 📚 Документация

### Основные документы
- **[RAGAS Quality System](ragas_quality_system.md)** - Полная техническая документация
- **[Quick Start Guide](ragas_quickstart.md)** - Быстрый запуск и настройка

### Краткое описание

RAGAS Quality System - это система автоматической оценки качества ответов RAG (Retrieval-Augmented Generation) системы с использованием метрик RAGAS и пользовательского фидбека.

## 🎯 Основные возможности

- **Автоматическая оценка качества** с помощью RAGAS метрик
- **Умные fallback scores** при недоступности OpenAI
- **Пользовательский фидбек** через кнопки 👍/👎
- **База данных качества** для хранения взаимодействий
- **Prometheus метрики** для мониторинга
- **Корреляционный анализ** между автоматическими и пользовательскими оценками

## ⚠️ Критические ограничения

### 1. OpenAI Dependency
- **Проблема**: RAGAS требует OpenAI API ключ для полного функционала
- **Решение**: Автоматический fallback на умные эвристики
- **Статус**: ✅ Работает без OpenAI

### 2. Версии зависимостей
- **RAGAS**: `0.1.21` (не обновлять до 0.2.x)
- **LangChain**: `0.2.16` (не обновлять до 0.3.x)
- **Datasets**: `2.19.0`

### 3. Производительность
- **RAGAS evaluation**: 2-5 секунд на взаимодействие
- **Fallback scores**: <100ms на взаимодействие
- **Рекомендация**: Использовать `RAGAS_EVALUATION_SAMPLE_RATE=0.1`

## 🚀 Быстрый старт

```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Настройка конфигурации
cp env.example .env
# Отредактируйте .env файл

# 3. Инициализация базы данных
python scripts/init_quality_db.py

# 4. Тестирование
python scripts/test_simple_ragas.py
```

## 📊 Что вы получите

### Автоматические метрики
- **Faithfulness**: Соответствие ответа контексту (0.0-1.0)
- **Context Precision**: Релевантность извлеченного контекста (0.0-1.0)
- **Answer Relevancy**: Релевантность ответа запросу (0.0-1.0)
- **Overall Score**: Общая оценка качества (0.0-1.0)

### Пользовательские оценки
- **Positive feedback**: 👍 кнопки
- **Negative feedback**: 👎 кнопки
- **Satisfaction rate**: Процент удовлетворенности

### Мониторинг
- **Prometheus метрики**: `ragas_score`, `user_satisfaction_rate`
- **Grafana dashboard**: Визуализация качества
- **Database storage**: Полная история взаимодействий

## 🔧 Конфигурация

### Основные параметры
```bash
# Включить RAGAS оценку
ENABLE_RAGAS_EVALUATION=true

# Доля взаимодействий для оценки (10%)
RAGAS_EVALUATION_SAMPLE_RATE=0.1

# База данных качества
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite:///data/quality_interactions.db

# Метрики Prometheus
ENABLE_QUALITY_METRICS=true
```

## 📈 Результаты тестирования

```
✅ RAGAS Evaluation Results:
   Faithfulness: 0.700
   Context Precision: 0.600
   Answer Relevancy: 0.800
   Overall Score: 0.700

🧪 Testing different scenarios:
   No contexts - Overall: 0.500
   Short response - Overall: 0.500
   Long response - Overall: 0.700
```

## 🎯 Готовность к продакшену

### ✅ Что работает
- Автоматическая оценка качества
- Умные fallback scores
- База данных взаимодействий
- Пользовательский фидбек
- Prometheus метрики
- Полная документация

### ⚠️ Ограничения
- Требует точные версии зависимостей
- RAGAS evaluation медленный (2-5 сек)
- Fallback scores вместо полного RAGAS

### 🚀 Рекомендации
- Использовать fallback scores для продакшена
- Настроить мониторинг через Grafana
- Регулярно анализировать качество ответов
- Собирать пользовательский фидбек

---

**Система готова к использованию в продакшене!** 🎉
