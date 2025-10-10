# Grafana Quality Dashboard

Визуализация метрик качества RAG-системы в реальном времени.

**Версия**: 1.0
**Дата обновления**: 9 октября 2024

---

## 📖 Содержание

- [Обзор](#обзор)
- [Доступ](#доступ-к-dashboard)
- [Панели](#панели-dashboard)
- [Настройка](#настройка-dashboard)
- [Интерпретация](#интерпретация-данных)
- [Алерты](#алерты-и-уведомления)
- [Troubleshooting](#устранение-неполадок)
- [Технические детали](#технические-детали)

---

## Обзор

Grafana Quality Dashboard предоставляет комплексную визуализацию метрик качества:

- ✅ **RAGAS метрики** - автоматическая оценка качества (faithfulness, precision, relevancy)
- ✅ **Пользовательский фидбек** - оценки 👍/👎 от пользователей
- ✅ **Комбинированный score** - общая оценка качества
- ✅ **Performance** - время оценки, throughput
- ✅ **Real-time** - обновление каждые 30 секунд

### Когда использовать

- Мониторинг качества ответов в production
- Анализ эффективности системы
- Выявление проблем с качеством
- A/B тестирование изменений
- Отчеты для стейкхолдеров

---

## Доступ к Dashboard

### Быстрый доступ

```
URL:      http://localhost:8080
Login:    admin
Password: admin123
Dashboard: RAG Quality Metrics
```

### Навигация

1. Откройте Grafana: http://localhost:8080
2. Войдите (admin / admin123)
3. Меню → Dashboards → Browse
4. Выберите **RAG Quality Metrics Dashboard**

**Требования**: RAG API и мониторинг должны быть запущены.

---

## Панели Dashboard

### Временные графики (Time Series)

#### 1. RAGAS Quality Scores
**Назначение**: Отслеживание автоматических метрик качества

| Параметр | Значение |
|----------|----------|
| **Тип** | Time Series (3 линии) |
| **Метрики** | faithfulness, context_precision, answer_relevancy |
| **PromQL** | `ragas_score{metric_type=~"faithfulness\|context_precision\|answer_relevancy"}` |
| **Диапазон** | 0.0 - 1.0 |

**Интерпретация**:
- Значения > 0.8 - отличное качество
- Значения 0.6-0.8 - хорошее качество
- Значения < 0.6 - требует внимания

#### 2. Combined Quality Score
**Назначение**: Общая оценка качества системы

| Параметр | Значение |
|----------|----------|
| **Тип** | Time Series |
| **Формула** | RAGAS + User Feedback |
| **PromQL** | `rag_combined_quality_score` |
| **Threshold** | Warning < 0.6, Critical < 0.5 |

#### 3. Quality Interactions Rate
**Назначение**: Частота оценок качества

| Параметр | Значение |
|----------|----------|
| **Тип** | Time Series (по каналам) |
| **PromQL** | `rate(rag_quality_interactions_total[5m])` |
| **Group By** | channel (telegram, api, web) |

#### 4. Evaluation Duration
**Назначение**: Производительность оценки качества

| Параметр | Значение |
|----------|----------|
| **Тип** | Time Series |
| **Метрика** | `quality_evaluation_duration_seconds` |
| **Unit** | seconds |
| **Threshold** | > 5s требует оптимизации |

### Статистика (Stats)

#### 5. Current Quality Score
**Большая цифра**: Текущая оценка качества (0-1)

```promql
rag_combined_quality_score{period="current"}
```

#### 6. Total RAGAS Evaluations
**Счетчик**: Всего RAGAS оценок

```promql
sum(rag_quality_interactions_total{interaction_type="ragas_evaluation"})
```

#### 7. Total User Feedback
**Счетчик**: Всего оценок от пользователей

```promql
sum(rag_quality_interactions_total{interaction_type="user_feedback"})
```

#### 8. User Satisfaction Rate
**Процент**: Доля положительных оценок

```promql
user_satisfaction_rate * 100
```

#### 9. Avg Evaluation Time
**Время**: Среднее время оценки

```promql
avg(quality_evaluation_duration_seconds)
```

### Визуализация (Charts)

#### 10. User Feedback Distribution
**Тип**: Pie Chart

**Сегменты**:
- 👍 Positive (зеленый)
- 👎 Negative (красный)
- ⚪ No Feedback (серый)

```promql
sum by (feedback_type) (rag_quality_interactions_total{interaction_type="user_feedback"})
```

---

## Настройка Dashboard

### Параметры отображения

**Временной диапазон**:
- По умолчанию: Последний час
- Быстрый выбор: 5m, 15m, 1h, 6h, 12h, 24h, 7d, 30d
- Кастомный период: от-до

**Обновление**:
- Частота: 30 секунд (auto-refresh)
- Можно отключить или изменить интервал

**Timezone**:
- По умолчанию: Browser time
- Опции: UTC, Local

### Переменные (Variables)

Dashboard поддерживает динамические фильтры:

```
$channel = telegram | api | web | all
$interaction_type = ragas_evaluation | user_feedback | all
$time_range = 1h | 6h | 24h | 7d
```

**Использование**: Dropdown в верхней части дашборда

### Кастомизация

**Изменение панелей**:
1. Edit (иконка карандаша на панели)
2. Измените PromQL query
3. Настройте визуализацию
4. Save

**Добавление панелей**:
1. Dashboard settings (⚙️) → Add panel
2. Выберите тип (Time Series, Stat, Gauge, etc.)
3. Настройте query и visualization
4. Save

---

## Интерпретация данных

### RAGAS Метрики

| Метрика | Что измеряет | Диапазон | Хорошее значение |
|---------|--------------|----------|------------------|
| **Faithfulness** | Соответствие ответа контексту | 0.0 - 1.0 | > 0.7 |
| **Context Precision** | Релевантность найденного контекста | 0.0 - 1.0 | > 0.6 |
| **Answer Relevancy** | Релевантность ответа запросу | 0.0 - 1.0 | > 0.8 |

**Примеры**:
- **Faithfulness 0.9**: Ответ на 90% основан на контексте (хорошо)
- **Context Precision 0.5**: Половина контекста нерелевантна (требует улучшения)
- **Answer Relevancy 0.95**: Ответ отлично отвечает на вопрос

### User Feedback

| Тип | Значение | Интерпретация |
|-----|----------|---------------|
| 👍 **Positive** | User нажал кнопку "полезно" | Ответ помог решить задачу |
| 👎 **Negative** | User нажал кнопку "не помогло" | Ответ не удовлетворил запрос |
| ⚪ **No Feedback** | User не оценил | Нейтральный результат |

**User Satisfaction Rate** = Positive / (Positive + Negative)

### Combined Quality Score

Комбинированная метрика: автоматическая оценка + пользовательский фидбек

| Диапазон | Оценка | Действия |
|----------|--------|----------|
| **> 0.8** | 🟢 Отличное качество | Поддерживать уровень |
| **0.6 - 0.8** | 🟡 Хорошее качество | Мониторить тренды |
| **< 0.6** | 🔴 Требует улучшения | Анализ проблем, оптимизация |

---

## Алерты и уведомления

### Критические алерты

**1. Low Quality Score**
```promql
rag_combined_quality_score < 0.6 for 15m
```
**Severity**: Critical
**Действие**: Проверить последние изменения, анализ логов

**2. High Evaluation Time**
```promql
avg(quality_evaluation_duration_seconds) > 10 for 10m
```
**Severity**: Warning
**Действие**: Проверить нагрузку, оптимизировать RAGAS

**3. Low User Satisfaction**
```promql
user_satisfaction_rate < 0.5 for 30m
```
**Severity**: Warning
**Действие**: Анализ негативных отзывов, улучшение промптов

### Настройка алертов

**Через Grafana UI**:
1. Alerting → Alert rules → New alert rule
2. Query: вставьте PromQL выше
3. Condition: например, `< 0.6`
4. Notifications: Slack/Email/Webhook
5. Save

**Пример Slack webhook**:
```
https://hooks.slack.com/services/YOUR/WEBHOOK/URL
Message: Quality score dropped to {{ $value }}
```

---

## Устранение неполадок

### 1. "No data points" в дашборде

**Симптомы**: Панели пустые или показывают "No data"

**Диагностика**:
```bash
# Проверьте RAG API
curl http://localhost:9000/metrics | grep ragas

# Проверьте Prometheus
curl http://localhost:9090/api/v1/query?query=ragas_score

# Проверьте targets
open http://localhost:9090/targets
```

**Решение**:
1. Убедитесь, что RAG API запущен: `python wsgi.py`
2. Проверьте переменные окружения:
   ```bash
   ENABLE_RAGAS_EVALUATION=true
   QUALITY_DB_ENABLED=true
   ```
3. Сделайте несколько запросов к системе для генерации данных
4. Подождите 30-60 секунд для обновления

### 2. "Metrics not updating"

**Симптомы**: Данные устаревшие, не обновляются

**Причины**:
- RAG API не обрабатывает запросы
- Prometheus не собирает метрики
- Auto-refresh отключен

**Решение**:
```bash
# Проверьте логи API
tail -f logs/app.log | grep -i quality

# Проверьте Prometheus scraping
docker logs rag-prometheus --tail 50

# В Grafana: проверьте auto-refresh (правый верхний угол)
```

### 3. "Dashboard not loading"

**Симптомы**: Grafana не открывается или дашборд недоступен

**Решение**:
```bash
# Проверьте статус Grafana
docker ps | grep grafana

# Перезапустите
docker restart rag-grafana

# Проверьте логи
docker logs rag-grafana

# Проверьте порт
curl http://localhost:8080/api/health
```

### 4. "Authentication failed"

**Симптомы**: Не могу войти в Grafana

**Решение**:
- **Login**: admin
- **Password**: admin123 (не просто admin!)
- Если забыли пароль: сбросьте через docker-compose

### 5. "Query timeout"

**Симптомы**: Панели показывают timeout ошибки

**Решение**:
```bash
# Уменьшите временной диапазон (с 30d до 1h)
# Или оптимизируйте queries (добавьте rate/avg)
```

---

## Технические детали

### Архитектура

```
RAG API (:9000/metrics)
    ↓ экспортирует метрики
Prometheus (:9090)
    ↓ сохраняет с retention 200h
Grafana (:8080)
    ↓ визуализирует через PromQL
Quality Dashboard
```

### Источники данных

| Компонент | URL | Назначение |
|-----------|-----|------------|
| **RAG API** | http://localhost:9000 | Экспорт метрик quality |
| **Prometheus** | http://localhost:9090 | Хранение time-series |
| **Quality DB** | data/quality_interactions.db | SQLite с историей |
| **Grafana** | http://localhost:8080 | Visualization |

### Метрики Quality

| Метрика | Тип | Labels | Описание |
|---------|-----|--------|----------|
| `ragas_score` | Gauge | metric_type | RAGAS метрики (0-1) |
| `user_satisfaction_rate` | Gauge | - | User feedback rate |
| `rag_quality_interactions_total` | Counter | interaction_type, channel | Счетчик оценок |
| `quality_evaluation_duration_seconds` | Histogram | evaluation_type | Время оценки |
| `rag_combined_quality_score` | Gauge | period | Общая оценка |

### PromQL Примеры

**Средний RAGAS score за час**:
```promql
avg_over_time(ragas_score{metric_type="overall"}[1h])
```

**User satisfaction trend**:
```promql
rate(rag_quality_interactions_total{interaction_type="user_feedback", feedback_type="positive"}[5m])
/
rate(rag_quality_interactions_total{interaction_type="user_feedback"}[5m])
```

**Quality по каналам**:
```promql
avg(rag_combined_quality_score) by (channel)
```

### Производительность

| Параметр | Значение | Настройка |
|----------|----------|-----------|
| **Обновление панелей** | 30 сек | Dashboard settings |
| **Prometheus scraping** | 5 сек | prometheus.yml |
| **Data retention** | 200 часов | Prometheus config |
| **Max throughput** | 1000 interactions/hour | Quality system |

### Storage

**Prometheus**:
- Формат: Time-series database (TSDB)
- Размер: ~10MB на день метрик
- Сжатие: Автоматическое

**Quality DB**:
- Формат: SQLite
- Размер: ~1MB на 1000 interactions
- Retention: Настраивается

---

## 📚 Связанная документация

- [RAGAS Quality System](ragas_quality_system.md) - Полная документация системы качества
- [Monitoring Setup](monitoring_setup.md) - Настройка мониторинга
- [Monitoring Quick Start](monitoring_quickstart.md) - Быстрый запуск
- [Architecture](architecture.md) - Архитектура RAG системы

### Внешние ресурсы

- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [RAGAS Framework](https://docs.ragas.io/)

---

**Версия документа**: 1.0
**Последнее обновление**: 9 октября 2024
**Статус**: Production Ready
