# RAG-система для edna Chat Center

Интеллектуальный ассистент на базе RAG (Retrieval-Augmented Generation) для технической поддержки edna Chat Center.

**Версия**: 4.3.1  
**Дата**: 9 октября 2024  
**Статус**: ✅ Production Ready

---

## 🎯 Что это?

RAG-система, которая:
- 🔍 Ищет информацию в документации через векторный поиск
- 🧠 Генерирует точные ответы с помощью LLM
- 🤖 Работает в Telegram и через REST API
- 📊 Контролирует качество с помощью RAGAS метрик

---

## ⚡ Быстрый старт (5 минут)

### 1. Установка

```bash
# Клонирование
git clone <repository-url>
cd RAG_clean

# Виртуальное окружение
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Зависимости
pip install -r requirements.txt
```

### 2. Конфигурация

```bash
# Копируйте env.example
cp env.example .env

# Отредактируйте .env с вашими ключами:
# - YANDEX_API_KEY
# - TELEGRAM_BOT_TOKEN
# - QDRANT_URL (по умолчанию localhost:6333)
```

### 3. Запуск сервисов

```bash
# Qdrant и Redis через Docker
docker-compose up -d qdrant redis

# Инициализация
python scripts/init_qdrant.py
python scripts/init_quality_db.py
```

### 4. Индексация документации

```bash
# Базовая индексация всех источников из config.yaml
python -m ingestion.run --config ingestion/config.yaml
```

### 5. Запуск системы

```bash
# Flask API
python wsgi.py

# Telegram Bot (в другом терминале)
python adapters/telegram/polling.py
```

**Готово!** 🎉 Система запущена на http://localhost:9000

👉 **Полная инструкция**: [docs/quickstart.md](docs/quickstart.md)

---

## 🚀 Ключевые возможности

### Core Features

| Возможность | Технология | Статус |
|-------------|------------|--------|
| **Гибридный поиск** | BGE-M3 dense + sparse + RRF | ✅ Production |
| **Multi-LLM** | YandexGPT + GPT-5 + Deepseek | ✅ Production |
| **Adaptive Chunking** | 150-300 токенов (оптимизировано) | ✅ Production |
| **Quality Control** | RAGAS + User Feedback | ✅ Production |
| **Monitoring** | Prometheus + Grafana | ✅ Production |

### Channels

- ✅ **Telegram Bot** - Long polling с HTML форматированием
- ✅ **REST API** - `/v1/chat/query` endpoint  
- 🔄 **Web Widget** - В разработке

### Infrastructure

- ✅ **Caching** - Redis + in-memory fallback
- ✅ **Security** - Rate limiting + validation + sanitization
- ✅ **Reliability** - Circuit breakers + graceful degradation
- ✅ **Observability** - Metrics + structured logging

👉 **Полный список**: [docs/complete_features.md](docs/complete_features.md)

## 🏗️ Архитектура

```
User Query
    ↓
Telegram/REST API
    ↓
Embeddings (BGE-M3: dense + sparse)
    ↓
Hybrid Search (Qdrant RRF fusion)
    ↓
Reranking (BGE-reranker-v2-m3)
    ↓
LLM Generation (YandexGPT → GPT-5 → Deepseek)
    ↓
Response + Quality Evaluation (RAGAS)
```

👉 **Детальная архитектура**: [docs/architecture.md](docs/architecture.md)

---

## 📋 Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| **Python** | 3.11+ | 3.11+ |
| **RAM** | 8GB | 16GB+ |
| **Storage** | 2GB | 10GB+ SSD |
| **Docker** | Для Qdrant/Redis | Для полного стека |

### Необходимые API ключи

- ✅ **YandexGPT API key** (обязательно)
- ✅ **Telegram Bot Token** (обязательно)
- ⚪ GPT-5 API key (fallback, опционально)
- ⚪ Deepseek API key (fallback, опционально)

---

## 📊 Основные компоненты

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| **Vector DB** | Qdrant 1.7+ | Хранение embeddings |
| **Embeddings** | BGE-M3 | Dense + sparse векторы |
| **LLM** | YandexGPT | Генерация ответов |
| **Cache** | Redis 7.x | Ускорение запросов |
| **Quality** | RAGAS 0.1.21 | Оценка качества |
| **Monitoring** | Prometheus + Grafana | Метрики |

---

## 📚 Документация

> **📖 Полная документация: [docs/README.md](docs/README.md)**

### Быстрый старт

| Документ | Время | Описание |
|----------|-------|----------|
| [Quick Start](docs/quickstart.md) | 10 минут | Запуск системы |
| [RAGAS Quick Start](docs/ragas_quickstart.md) | 5 минут | Система качества |
| [Monitoring Quick Start](docs/monitoring_quickstart.md) | 1 минута | Мониторинг |

### Руководства

| Документ | Для кого |
|----------|----------|
| [Architecture](docs/architecture.md) | Tech Leads, Architects |
| [Development Guide](docs/development_guide.md) | Разработчики |
| [Deployment Guide](docs/deployment_guide.md) | DevOps, Admins |
| [API Reference](docs/api_reference.md) | Интеграторы |

### Специализированные

| Документ | Тема |
|----------|------|
| [Technical Specification](docs/technical_specification.md) | Технические детали |
| [Indexing & Data Structure](docs/indexing_and_data_structure.md) | Индексация |
| [RAGAS Quality System](docs/ragas_quality_system.md) | Система качества |
| [Adding Data Sources](docs/adding_data_sources.md) | Новые источники |

---

## 🔧 Основные команды

### Разработка

```bash
# Запуск в dev режиме
python wsgi.py

# Тесты
make test-fast

# Линтинг
make lint
```

### Индексация

```bash
# Полная индексация всех источников
python -m ingestion.run --config ingestion/config.yaml --reindex-mode full

# Инкрементальная (режим changed по умолчанию)
python -m ingestion.run --config ingestion/config.yaml --reindex-mode changed
```

### Тонкая настройка поиска (boosting & тематики)

- `app/config/boosting.yaml` — конфигурация буста:
  - `page_type_boosts`, `section_boosts`, `platform_boosts` — веса для типов страниц/секций/платформ;
  - `url_patterns`, `title_keywords`, `length`, `structure`, `source_boosts`, `depth_penalty` — эвристики ранжирования;
  - `theme_boost` — мягкое усиление документов по выбранной тематике.
  Измените коэффициенты в этом файле и перезапустите backend — поведение поиска обновится без переиндексации.

- `app/config/themes.yaml` — список тематик (SDK Android/iOS/Web, АРМы и др.):
  - каждая тема описывает `domain/section/platform/role` и `display_name`;
  - используется в `route_query` для выбора корпуса документов и фильтрации;
  - вы можете добавлять/менять тематики (например, под новый продукт/модуль) и переиспользовать тот же RAG‑pipeline.

### Мониторинг

```bash
# Запуск Grafana + Prometheus
.\start_monitoring.ps1  # Windows

# Доступ
# Grafana: http://localhost:8080 (admin/admin123)
# Prometheus: http://localhost:9090
```

---

## 🧪 Тестирование

```bash
# Быстрые тесты
make test-fast

# Все тесты
make test

# С покрытием
make test-coverage

# Конкретный тип
python scripts/run_tests.py --type unit --verbose
```

**Подробнее**: [docs/autotests_guide.md](docs/autotests_guide.md)

---

## 📊 API Endpoints

### Chat
- `POST /v1/chat/query` - Обработка запросов

### Quality (RAGAS)
- `GET /v1/admin/quality/stats` - Статистика
- `GET /v1/admin/quality/trends` - Тренды

### Admin
- `GET /v1/admin/health` - Health check
- `POST /v1/admin/reindex` - Переиндексация
- `GET /apidocs` - Swagger UI

**Полная документация**: [docs/api_reference.md](docs/api_reference.md)

---

## 🚀 Deployment

### Development
```bash
python wsgi.py
```

### Docker Compose
```bash
docker-compose up -d
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

**Подробнее**: [docs/deployment_guide.md](docs/deployment_guide.md)

---

## 🐛 Troubleshooting

### Частые проблемы

| Проблема | Решение |
|----------|---------|
| **Timeout errors** | Увеличьте таймауты в `.env` |
| **Empty results** | Проверьте индексацию: `python scripts/check_full_text.py` |
| **LLM errors** | Проверьте API ключи в `.env` |
| **No data in Grafana** | Запустите RAG API: `python wsgi.py` |

**Детальное troubleshooting**: См. документацию конкретного компонента

---

## 📈 Changelog

См. [CHANGELOG.md](CHANGELOG.md) для детальной истории изменений.

### Последние обновления (v4.3.1)

- ✅ Chunking оптимизирован: **150-300 токенов** (практический опыт)
- ✅ Документация полностью обновлена (9 октября 2024)
- ✅ ADR обновлены с реальными параметрами
- ✅ Исправлены все несоответствия портов и паролей

---

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'feat: add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

**Руководство**: [docs/development_guide.md](docs/development_guide.md)

---

## 📞 Поддержка

- 📖 [Документация](docs/README.md)
- 🐛 [GitHub Issues](https://github.com/your-repo/issues)
- 💬 [Discussions](https://github.com/your-repo/discussions)

---

## 📝 Лицензия

MIT License - см. [LICENSE](LICENSE)

---

**Готовы начать?** → [docs/quickstart.md](docs/quickstart.md)
