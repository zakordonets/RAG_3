# 📊 Мониторинг RAG системы

## 🚀 Быстрый старт

### Запуск мониторинга
```bash
# Windows PowerShell
.\start_monitoring.ps1

# Windows CMD
start_monitoring.bat

# Linux/Mac
docker-compose -f docker-compose.monitoring.yml up -d
```

### Доступ к интерфейсам
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:8080
  - Логин: `admin`
  - Пароль: `admin123`

## 📈 Что мониторится

### Основные метрики
- **Запросы**: количество и скорость обработки
- **Производительность**: время эмбеддингов, поиска, генерации LLM
- **Кэш**: эффективность кэширования
- **Ошибки**: частота и типы ошибок
- **Соединения**: активные подключения

### Дашборды
- **RAG System Overview** - основной дашборд с ключевыми метриками
- Автоматически создается при первом запуске

## 🔧 Архитектура

```
RAG API (:9001) → Prometheus (:9090) → Grafana (:8080)
```

## 📁 Файлы мониторинга

- `docker-compose.monitoring.yml` - конфигурация Docker
- `monitoring/prometheus.yml` - настройки Prometheus
- `monitoring/grafana/` - конфигурация Grafana
- `docs/monitoring_setup.md` - подробная документация

## 🛑 Остановка

```bash
docker-compose -f docker-compose.monitoring.yml down
```

## ❓ Troubleshooting

1. **Порт 8080 занят**: измените порт в `docker-compose.monitoring.yml`
2. **Метрики не видны**: проверьте, что RAG API запущен на порту 9001
3. **Prometheus не видит RAG API**: проверьте IP адрес в `prometheus.yml`

Подробнее: [docs/monitoring_setup.md](docs/monitoring_setup.md)
