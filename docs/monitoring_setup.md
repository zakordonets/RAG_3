# Monitoring Setup Guide

Полное руководство по настройке мониторинга RAG-системы.

**Версия**: 1.0
**Дата обновления**: 9 октября 2024

---

## 📖 Содержание

- [Обзор](#обзор)
- [Быстрый старт](#быстрый-старт)
- [Архитектура](#архитектура-мониторинга)
- [Метрики](#метрики)
- [Дашборды](#дашборды)
- [Настройка](#настройка)
- [Production](#мониторинг-в-продакшене)
- [Troubleshooting](#troubleshooting)
- [Расширение](#расширение-мониторинга)

---

## Обзор

Система мониторинга включает три компонента:

| Компонент | Назначение | Порт |
|-----------|------------|------|
| **RAG API** | Экспорт метрик | 9000 (/metrics) |
| **Prometheus** | Сбор и хранение метрик | 9090 |
| **Grafana** | Визуализация и дашборды | 8080 |

### Возможности

- ✅ Мониторинг производительности в реальном времени
- ✅ Метрики качества (RAGAS)
- ✅ Отслеживание ошибок
- ✅ Автоматические дашборды
- ✅ Готовые алерты (опционально)

---

## Быстрый старт

👉 **Для быстрого запуска см.**: [monitoring_quickstart.md](monitoring_quickstart.md)

### Полная последовательность

```bash
# 1. Запустите RAG API
python wsgi.py

# 2. Запустите мониторинг
# Windows
.\start_monitoring.ps1

# Linux/Mac
docker-compose -f docker-compose.monitoring.yml up -d

# 3. Откройте интерфейсы
# Prometheus: http://localhost:9090
# Grafana: http://localhost:8080 (admin/admin123)
```

### Проверка работоспособности

```bash
# Метрики RAG API
curl http://localhost:9000/metrics

# Prometheus targets
curl http://localhost:9090/api/v1/targets

# Grafana health
curl http://localhost:8080/api/health
```

## Архитектура мониторинга

```
┌─────────────────────┐
│   RAG API           │  Экспортирует метрики
│   :9000/metrics     │  через Prometheus client
└─────────┬───────────┘
          │ HTTP GET /metrics (каждые 5 сек)
          ▼
┌─────────────────────┐
│   Prometheus        │  Собирает и хранит метрики
│   :9090             │  Retention: 200h (по умолчанию)
└─────────┬───────────┘
          │ PromQL queries
          ▼
┌─────────────────────┐
│   Grafana           │  Визуализирует данные
│   :8080             │  Автоматические дашборды
└─────────────────────┘
```

### Поток данных

1. **RAG API** экспортирует метрики через `/metrics` endpoint
2. **Prometheus** периодически (каждые 5 сек) собирает метрики
3. **Grafana** запрашивает данные из Prometheus через PromQL
4. **Дашборды** обновляются в реальном времени (каждые 5-10 сек)

---

## Метрики

### Performance Metrics

| Метрика | Тип | Описание | Labels |
|---------|-----|----------|--------|
| `rag_queries_total` | Counter | Общее количество запросов | channel, status |
| `rag_query_duration_seconds` | Histogram | Время обработки запросов | channel, stage |
| `rag_embedding_duration_seconds` | Histogram | Время создания embeddings | type (dense/sparse) |
| `rag_search_duration_seconds` | Histogram | Время векторного поиска | type (hybrid/dense/sparse) |
| `rag_llm_duration_seconds` | Histogram | Время генерации LLM | provider |

### Quality Metrics

| Метрика | Тип | Описание |
|---------|-----|----------|
| `ragas_score` | Gauge | RAGAS метрики качества (metric_type: faithfulness, context_precision, answer_relevancy) |
| `user_satisfaction_rate` | Gauge | Удовлетворенность пользователей (из 👍/👎) |
| `quality_evaluation_duration_seconds` | Histogram | Время оценки качества |

### System Metrics

| Метрика | Тип | Описание |
|---------|-----|----------|
| `rag_active_connections` | Gauge | Активные соединения |
| `rag_cache_hits_total` | Counter | Попадания в кэш |
| `rag_cache_misses_total` | Counter | Промахи кэша |
| `rag_errors_total` | Counter | Ошибки (error_type: timeout, validation, network) |

### Использование

```bash
# Просмотр всех метрик
curl http://localhost:9000/metrics

# Конкретная метрика
curl http://localhost:9000/metrics | grep rag_queries_total

# Через Prometheus UI
# http://localhost:9090 → Graph → введите имя метрики
```

## Дашборды

Автоматически загружаемые дашборды в Grafana.

### 1. RAG System Overview

**Назначение**: Общий обзор производительности системы

**Панели**:
- Query Rate (QPS по каналам)
- Query Duration (p50, p95, p99 percentiles)
- Embedding Duration (dense vs sparse)
- Search Duration (по типам поиска)
- LLM Duration (по провайдерам)
- Active Connections
- Cache Hit Rate
- Error Rate

### 2. Quality Dashboard

**Назначение**: Мониторинг качества ответов

**Панели**:
- RAGAS Scores (faithfulness, context precision, answer relevancy)
- User Satisfaction Rate (👍/👎)
- Correlation Analysis
- Quality Trends

### 3. Performance Dashboard

**Назначение**: Детальный анализ производительности

**Панели**:
- Response Time Distribution
- Throughput (requests/sec)
- Resource Usage
- Bottleneck Analysis

### 4. Error Monitoring

**Назначение**: Отслеживание ошибок

**Панели**:
- Error Rate by Type
- Failed Requests Timeline
- Error Distribution
- Recovery Time

### Доступ к дашбордам

```
Grafana → Dashboards → Browse
- RAG System Overview
- Quality Dashboard
- Performance Dashboard
- Error Monitoring
```

---

## Настройка

### Prometheus

**Файл**: `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 5s           # Частота сбора метрик
  evaluation_interval: 5s       # Частота проверки правил
  scrape_timeout: 4s            # Таймаут сбора

scrape_configs:
  - job_name: 'rag-api'
    static_configs:
      - targets: ['host.docker.internal:9000']  # RAG API метрики
    scrape_interval: 5s
```

**Параметры**:
- `scrape_interval`: как часто собирать метрики
- `scrape_timeout`: таймаут сбора метрик
- `evaluation_interval`: частота проверки алертов

### Grafana

**Автоматическая конфигурация**:
- ✅ Datasource (Prometheus) настраивается автоматически
- ✅ Дашборды загружаются из `monitoring/grafana/dashboards/`
- ✅ Provisioning через `monitoring/grafana/provisioning/`

**Ручная настройка** (опционально):

1. Добавить новый Datasource:
   - Configuration → Data Sources → Add data source
   - Выберите Prometheus
   - URL: `http://prometheus:9090`

2. Импорт дашборда:
   - Dashboards → Import
   - Загрузите JSON из `monitoring/grafana/dashboards/`

### Переменные окружения

```bash
# docker-compose.monitoring.yml
environment:
  # Prometheus
  PROMETHEUS_RETENTION_TIME: '200h'

  # Grafana
  GF_SECURITY_ADMIN_USER: admin
  GF_SECURITY_ADMIN_PASSWORD: admin123
  GF_USERS_ALLOW_SIGN_UP: 'false'
  GF_INSTALL_PLUGINS: ''
```

## Мониторинг в продакшене

### Чек-лист для Production

- [ ] **Security**: Измените пароли по умолчанию
- [ ] **Retention**: Увеличьте хранение метрик (720h = 30 дней)
- [ ] **Alerting**: Настройте алерты на критические метрики
- [ ] **Backup**: Регулярное сохранение дашбордов
- [ ] **HTTPS**: Secure connections для Grafana
- [ ] **Authentication**: SSO/LDAP интеграция (опционально)

### Конфигурация Production

```bash
# docker-compose.monitoring.yml
environment:
  # Prometheus
  PROMETHEUS_RETENTION_TIME: '720h'          # 30 дней
  PROMETHEUS_STORAGE_TSDB_PATH: '/prometheus'

  # Grafana
  GF_SECURITY_ADMIN_PASSWORD: '${GRAFANA_PASSWORD}'  # Из .env
  GF_USERS_ALLOW_SIGN_UP: 'false'
  GF_AUTH_ANONYMOUS_ENABLED: 'false'
  GF_SERVER_ROOT_URL: 'https://grafana.yourdomain.com'
  GF_SECURITY_COOKIE_SECURE: 'true'
```

### Alerting Rules

**Файл**: `monitoring/prometheus/alerts.yml`

```yaml
groups:
  - name: rag_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(rag_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      # Slow responses
      - alert: SlowResponses
        expr: histogram_quantile(0.95, rag_query_duration_seconds) > 120
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "95th percentile response time > 2 minutes"

      # Low RAGAS score
      - alert: LowQualityScore
        expr: ragas_score{metric_type="overall"} < 0.5
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "RAGAS quality score dropped below 0.5"
```

### Backup дашбордов

```bash
# Экспорт всех дашбордов
docker exec rag-grafana grafana-cli admin export \
  --output-dir /var/lib/grafana/backups

# Копирование на хост
docker cp rag-grafana:/var/lib/grafana/backups ./grafana-backups

# Восстановление
docker cp ./grafana-backups rag-grafana:/var/lib/grafana/
```

---

## Troubleshooting

Решение распространенных проблем.

### 1. "No data in Grafana"

**Симптомы**: Дашборды пустые, нет данных

**Диагностика**:
```bash
# 1. Проверьте RAG API метрики
curl http://localhost:9000/metrics

# 2. Проверьте Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[0].health'

# 3. Проверьте Grafana datasource
curl -u admin:admin123 http://localhost:8080/api/datasources
```

**Решение**:
1. Убедитесь, что RAG API запущен: `python wsgi.py`
2. Проверьте, что порт 9000 доступен
3. Проверьте `host.docker.internal` в `prometheus.yml`

### 2. "Prometheus target DOWN"

**Симптомы**: Target показывает статус DOWN в http://localhost:9090/targets

**Решение**:
```bash
# Проверьте network connectivity
docker exec rag-prometheus ping -c 3 host.docker.internal

# Проверьте порт
telnet localhost 9000

# Проверьте логи Prometheus
docker logs rag-prometheus --tail 50
```

### 3. "Port 8080 already in use"

**Симптомы**: Grafana не запускается из-за занятого порта

**Решение**:
```yaml
# Измените порт в docker-compose.monitoring.yml
services:
  grafana:
    ports:
      - "8081:3000"  # Используйте другой порт
```

### 4. "Grafana не сохраняет изменения"

**Причина**: Недостаточно прав на volume

**Решение**:
```bash
# Проверьте права
ls -la monitoring/grafana/

# Исправьте права
chmod -R 777 monitoring/grafana/
```

### Логи и диагностика

```bash
# Просмотр логов
docker logs rag-prometheus
docker logs rag-grafana

# Следить за логами в реальном времени
docker logs -f rag-prometheus
docker logs -f rag-grafana

# Проверка статуса контейнеров
docker ps | grep -E "prometheus|grafana"

# Перезапуск сервисов
docker-compose -f docker-compose.monitoring.yml restart
```

---

## Расширение мониторинга

### Добавление новых метрик

**Шаг 1**: Добавьте метрику в код

```python
# app/infrastructure/metrics.py
from prometheus_client import Counter, Histogram

custom_metric = Counter(
    'rag_custom_operation_total',
    'Custom operation counter',
    ['operation_type', 'status']
)

# Использование
custom_metric.labels(operation_type='processing', status='success').inc()
```

**Шаг 2**: Создайте панель в Grafana
1. Откройте дашборд
2. Add Panel → Add new panel
3. PromQL query: `rate(rag_custom_operation_total[5m])`
4. Настройте визуализацию
5. Save

### Кастомные дашборды

```bash
# 1. Создайте JSON в monitoring/grafana/dashboards/
cat > monitoring/grafana/dashboards/custom-dashboard.json << 'EOF'
{
  "dashboard": {
    "title": "Custom RAG Dashboard",
    "panels": [...]
  }
}
EOF

# 2. Перезапустите Grafana
docker restart rag-grafana

# 3. Дашборд появится автоматически
```

### Интеграция с внешними системами

**Slack алерты**:
```yaml
# Grafana → Alerting → Notification channels
webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Email алерты**:
```bash
# docker-compose.monitoring.yml
GF_SMTP_ENABLED: 'true'
GF_SMTP_HOST: 'smtp.gmail.com:587'
GF_SMTP_USER: 'your-email@gmail.com'
GF_SMTP_PASSWORD: '${EMAIL_PASSWORD}'
```

---

## 📚 Связанная документация

- [Monitoring Quick Start](monitoring_quickstart.md) - Быстрый запуск
- [Architecture](architecture.md) - Архитектура системы
- [Technical Specification](technical_specification.md) - Технические детали
- [RAGAS Quality System](ragas_quality_system.md) - Метрики качества

### Внешние ресурсы

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Python Client](https://prometheus.github.io/client_python/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)

---

## 🛑 Остановка мониторинга

```bash
# Остановка без удаления данных
docker-compose -f docker-compose.monitoring.yml stop

# Остановка с удалением контейнеров (данные сохраняются)
docker-compose -f docker-compose.monitoring.yml down

# Полная очистка (включая данные)
docker-compose -f docker-compose.monitoring.yml down -v
```

---

**Версия документа**: 1.0
**Последнее обновление**: 9 октября 2024
**Статус**: Production Ready
