# 🚀 Быстрый старт мониторинга

## Запуск за 30 секунд

```bash
# 1. Запуск RAG API (обязательно!)
python wsgi.py

# 2. Запуск мониторинга
.\start_monitoring.ps1

# 3. Открыть в браузере
# Prometheus: http://localhost:9090
# Grafana: http://localhost:8080 (admin/admin123)
```

## Что вы увидите

### Prometheus (http://localhost:9090)
- **Targets** - статус сбора метрик с RAG API
- **Graph** - запросы метрик и построение графиков
- **Alerts** - настройка алертов (в будущем)

### Grafana (http://localhost:8080)
- **RAG System Overview** - основной дашборд
- **Query Performance** - производительность запросов
- **Cache Analytics** - эффективность кэширования
- **Error Monitoring** - мониторинг ошибок

## Основные метрики

| Метрика | Описание |
|---------|----------|
| `rag_queries_total` | Количество запросов |
| `rag_query_duration_seconds` | Время обработки запросов |
| `rag_embedding_duration_seconds` | Время создания эмбеддингов |
| `rag_search_duration_seconds` | Время поиска |
| `rag_llm_duration_seconds` | Время генерации LLM |
| `rag_cache_hits_total` | Попадания в кэш |
| `rag_errors_total` | Ошибки по типам |

## Остановка

```bash
docker-compose -f docker-compose.monitoring.yml down
```

## Troubleshooting

### Порт 8080 занят
Измените порт в `docker-compose.monitoring.yml`:
```yaml
ports:
  - "8081:3000"  # Новый порт
```

### Метрики не видны
1. Проверьте, что RAG API запущен на порту 9001
2. Проверьте targets в Prometheus: http://localhost:9090/targets
3. Проверьте логи: `docker logs rag-prometheus`

### Grafana не загружается
```bash
# Проверка статуса
docker ps | grep grafana

# Перезапуск
docker restart rag-grafana
```

## Подробнее

- [MONITORING_README.md](../MONITORING_README.md) - краткое руководство
- [docs/monitoring_setup.md](monitoring_setup.md) - подробная настройка
- [docs/architecture.md](architecture.md) - архитектура мониторинга
