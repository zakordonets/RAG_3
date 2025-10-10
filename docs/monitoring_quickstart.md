# 🚀 Monitoring Quick Start

Запуск системы мониторинга за 1 минуту.

**Версия**: 1.0
**Дата обновления**: 9 октября 2024

---

## ⚡ Запуск (3 команды)

```bash
# 1. Запустите RAG API (обязательно!)
python wsgi.py

# 2. Запустите мониторинг
.\start_monitoring.ps1  # Windows
# docker-compose -f docker-compose.monitoring.yml up -d  # Linux/Mac

# 3. Откройте в браузере
# Prometheus: http://localhost:9090
# Grafana: http://localhost:8080 (admin/admin123)
```

**Готово!** 🎉 Теперь вы видите метрики системы в реальном времени.

---

## 📊 Что доступно

### Prometheus (http://localhost:9090)
- ✅ Статус сбора метрик (Targets)
- ✅ Запросы к метрикам (Graph)
- ✅ Просмотр всех метрик

### Grafana (http://localhost:8080)
Автоматически загруженные дашборды:
- **RAG System Overview** - основные метрики системы
- **Query Performance** - производительность запросов
- **Quality Dashboard** - RAGAS метрики качества
- **Cache Analytics** - эффективность кэша

**Credentials:** admin / admin123

---

## 🛑 Остановка

```bash
docker-compose -f docker-compose.monitoring.yml down
```

---

## ⚠️ Частые проблемы

### "Порт 8080 уже используется"

```yaml
# docker-compose.monitoring.yml
services:
  grafana:
    ports:
      - "8081:3000"  # Измените на свободный порт
```

### "No data in Grafana"

1. Проверьте, что RAG API запущен:
   ```bash
   curl http://localhost:9000/metrics
   ```

2. Проверьте targets в Prometheus:
   http://localhost:9090/targets (должен быть UP)

3. Проверьте логи:
   ```bash
   docker logs rag-prometheus
   ```

### "Grafana не загружается"

```bash
# Проверка
docker ps | grep grafana

# Перезапуск
docker restart rag-grafana

# Логи
docker logs rag-grafana
```

---

## 📚 Подробнее

Для детальной настройки и production deployment см.:
- 📖 [Monitoring Setup Guide](monitoring_setup.md) - полная документация
- 🏗️ [Architecture](architecture.md) - архитектура системы
- 🔧 [Development Guide](development_guide.md) - разработка

---

**Нужна помощь?** См. [Troubleshooting](monitoring_setup.md#troubleshooting) в полной документации.
