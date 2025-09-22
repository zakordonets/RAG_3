# Grafana Quality Dashboard

## Обзор

Grafana Quality Dashboard предоставляет визуализацию метрик качества RAGAS системы в реальном времени. Dashboard отображает ключевые показатели качества ответов, пользовательский фидбек и производительность системы оценки качества.

## Доступ к Dashboard

- **URL**: http://localhost:8080
- **Login**: admin
- **Password**: admin
- **Dashboard**: RAG Quality Metrics Dashboard

## Панели Dashboard

### 1. RAGAS Quality Scores
- **Тип**: Time Series
- **Описание**: Отображает оценки RAGAS метрик (faithfulness, context_precision, answer_relevancy) во времени
- **Метрика**: `rag_ragas_score`
- **Цветовая схема**: Различные цвета для каждой метрики

### 2. User Feedback Distribution
- **Тип**: Pie Chart
- **Описание**: Показывает распределение пользовательского фидбека (positive/negative)
- **Метрика**: `rag_quality_interactions_total{interaction_type="user_feedback"}`
- **Обновление**: В реальном времени

### 3. Combined Quality Score Over Time
- **Тип**: Time Series
- **Описание**: Комбинированная оценка качества (RAGAS + пользовательский фидбек)
- **Метрика**: `rag_combined_quality_score`
- **Единицы**: Проценты (0-1)

### 4. Quality Interactions Rate
- **Тип**: Time Series
- **Описание**: Скорость создания quality interactions по каналам
- **Метрика**: `rate(rag_quality_interactions_total[5m])`
- **Группировка**: По каналам (telegram, api, web)

### 5. Quality Evaluation Duration
- **Тип**: Time Series
- **Описание**: Время выполнения оценки качества
- **Метрика**: `rag_quality_evaluation_duration_seconds`
- **Единицы**: Секунды

### 6. Total RAGAS Evaluations (Stat)
- **Тип**: Stat
- **Описание**: Общее количество RAGAS оценок
- **Метрика**: `sum(rag_quality_interactions_total{interaction_type="ragas_evaluation"})`

### 7. Total User Feedback (Stat)
- **Тип**: Stat
- **Описание**: Общее количество пользовательского фидбека
- **Метрика**: `sum(rag_quality_interactions_total{interaction_type="user_feedback"})`

### 8. Current Quality Score (Stat)
- **Тип**: Stat
- **Описание**: Текущая комбинированная оценка качества
- **Метрика**: `rag_combined_quality_score{period="current"}`
- **Единицы**: Проценты

### 9. Avg RAGAS Evaluation Time (Stat)
- **Тип**: Stat
- **Описание**: Среднее время RAGAS оценки
- **Метрика**: `rag_quality_evaluation_duration_seconds{evaluation_type="ragas"}`
- **Единицы**: Секунды

## Настройка Dashboard

### Временной диапазон
- **По умолчанию**: Последний час
- **Доступные опции**: 5 минут, 15 минут, 1 час, 6 часов, 12 часов, 24 часа, 7 дней, 30 дней

### Обновление данных
- **Частота**: 30 секунд
- **Автообновление**: Включено

### Фильтры
- **Каналы**: telegram, api, web
- **Типы interactions**: ragas_evaluation, user_feedback
- **Качество**: positive, negative, unknown

## Интерпретация данных

### RAGAS Scores
- **Faithfulness**: Насколько ответ соответствует предоставленному контексту (0-1)
- **Context Precision**: Релевантность найденного контекста (0-1)
- **Answer Relevancy**: Релевантность ответа пользовательскому запросу (0-1)

### User Feedback
- **Positive**: 👍 Пользователь доволен ответом
- **Negative**: 👎 Пользователь недоволен ответом

### Combined Quality Score
- **Высокий (>0.8)**: Отличное качество
- **Средний (0.6-0.8)**: Хорошее качество
- **Низкий (<0.6)**: Требует улучшения

## Алерты и уведомления

### Рекомендуемые алерты
1. **Low Quality Score**: `rag_combined_quality_score < 0.6`
2. **High Evaluation Time**: `rag_quality_evaluation_duration_seconds > 30`
3. **Low User Satisfaction**: `rag_user_satisfaction_rate < 0.5`

### Настройка алертов
1. Перейдите в раздел "Alerting" в Grafana
2. Создайте новый alert rule
3. Настройте условия и уведомления

## Устранение неполадок

### Нет данных в dashboard
1. Проверьте, что API сервер запущен
2. Убедитесь, что переменные окружения установлены:
   - `ENABLE_RAGAS_EVALUATION=true`
   - `QUALITY_DB_ENABLED=true`
3. Проверьте Prometheus targets: http://localhost:9090/targets

### Метрики не обновляются
1. Проверьте логи API сервера
2. Убедитесь, что есть активность (запросы к системе)
3. Проверьте подключение к базе данных качества

### Dashboard не загружается
1. Проверьте, что Grafana запущен: http://localhost:8080
2. Убедитесь, что Prometheus datasource настроен
3. Проверьте логи Grafana: `docker logs rag-grafana`

## Технические детали

### Источники данных
- **Prometheus**: http://localhost:9090
- **API Metrics**: http://localhost:9002/metrics
- **Quality Database**: SQLite (data/quality_interactions.db)

### Метрики
- **rag_ragas_score**: Оценки RAGAS метрик
- **rag_quality_interactions_total**: Счетчики interactions
- **rag_combined_quality_score**: Комбинированная оценка
- **rag_quality_evaluation_duration_seconds**: Время оценки

### Производительность
- **Обновление**: Каждые 30 секунд
- **Хранение данных**: 15 дней в Prometheus
- **Масштабируемость**: Поддерживает до 1000 interactions/час
