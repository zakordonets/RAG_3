# Мониторинг RAG системы с Grafana и Prometheus

## Обзор

Система мониторинга включает в себя:
- **Prometheus** - сбор метрик
- **Grafana** - визуализация и дашборды
- **RAG API** - экспорт метрик на порту 9001

## Быстрый старт

### 1. Запуск RAG API (обязательно!)

```bash
# Запустите RAG API для сбора метрик
python wsgi.py
```

### 2. Запуск мониторинга

```bash
# Windows (PowerShell)
.\start_monitoring.ps1

# Windows (CMD)
start_monitoring.bat

# Linux/Mac
docker-compose -f docker-compose.monitoring.yml up -d
```

### 3. Доступ к интерфейсам

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:8080
  - Логин: `admin`
  - Пароль: `admin123`

## Архитектура мониторинга

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RAG API       │    │   Prometheus    │    │    Grafana      │
│   :9001/metrics │───▶│   :9090         │───▶│   :8080         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Метрики

### Основные метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `rag_queries_total` | Counter | Общее количество запросов |
| `rag_query_duration_seconds` | Histogram | Длительность обработки запросов |
| `rag_embedding_duration_seconds` | Histogram | Время создания эмбеддингов |
| `rag_search_duration_seconds` | Histogram | Время поиска |
| `rag_llm_duration_seconds` | Histogram | Время генерации LLM |
| `rag_active_connections` | Gauge | Активные соединения |
| `rag_cache_hits_total` | Counter | Попадания в кэш |
| `rag_cache_misses_total` | Counter | Промахи кэша |
| `rag_errors_total` | Counter | Ошибки по типам |

### Метки (Labels)

- **channel**: telegram, api, web
- **status**: success, error
- **type**: dense, sparse, hybrid
- **provider**: yandex, openai
- **stage**: embedding, search, llm, total
- **error_type**: timeout, validation, network

## Дашборды

### RAG System Overview

Основной дашборд включает:

1. **Query Rate** - частота запросов по каналам
2. **Query Duration** - 95-й и 50-й процентили длительности
3. **Embedding Duration** - время создания эмбеддингов
4. **Search Duration** - время поиска (dense/sparse/hybrid)
5. **LLM Duration** - время генерации ответов
6. **Active Connections** - активные соединения
7. **Cache Performance** - эффективность кэша
8. **Error Rate** - частота ошибок

## Настройка

### Prometheus конфигурация

Файл: `monitoring/prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'rag-api'
    static_configs:
      - targets: ['host.docker.internal:9002']
    scrape_interval: 5s
```

### Grafana конфигурация

- **Datasource**: автоматически настроен Prometheus
- **Dashboards**: автоматически загружаются из `monitoring/grafana/dashboards/`

## Мониторинг в продакшене

### Рекомендации

1. **Retention**: настройте хранение метрик в Prometheus (по умолчанию 200h)
2. **Alerting**: добавьте правила алертинга в Prometheus
3. **Backup**: регулярно сохраняйте дашборды Grafana
4. **Security**: измените пароли по умолчанию

### Переменные окружения

```bash
# Prometheus
PROMETHEUS_RETENTION_TIME=720h

# Grafana
GF_SECURITY_ADMIN_PASSWORD=your_secure_password
GF_USERS_ALLOW_SIGN_UP=false
```

## Troubleshooting

### Проблемы с подключением

1. **Метрики не доступны**:
   - Проверьте, что RAG API запущен на порту 9002
   - Убедитесь, что `host.docker.internal` доступен
   - **Важно**: RAG API должен быть запущен (`python wsgi.py`) для сбора метрик

2. **Grafana не загружается**:
   - Проверьте логи: `docker logs rag-grafana`
   - Убедитесь, что порт 8080 свободен

3. **Prometheus не собирает метрики**:
   - Проверьте статус: http://localhost:9090/targets
   - Проверьте конфигурацию в `prometheus.yml`

### Логи

```bash
# Просмотр логов
docker logs rag-prometheus
docker logs rag-grafana

# Следить за логами
docker logs -f rag-prometheus
docker logs -f rag-grafana
```

## Остановка

```bash
docker-compose -f docker-compose.monitoring.yml down
```

## Расширение мониторинга

### Добавление новых метрик

1. Добавьте метрику в `app/metrics.py`
2. Обновите дашборд в Grafana
3. Перезапустите контейнеры

### Кастомные дашборды

1. Создайте JSON файл в `monitoring/grafana/dashboards/`
2. Перезапустите Grafana
3. Дашборд появится автоматически

## Полезные ссылки

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Client Library](https://prometheus.github.io/client_python/)
