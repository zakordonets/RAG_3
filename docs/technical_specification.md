# Техническая спецификация RAG-системы

Полная техническая спецификация RAG-системы для edna Chat Center.

**Версия**: 4.3.1
**Дата обновления**: 9 октября 2024
**Статус**: Production Ready

---

## 📖 Содержание

- [Обзор системы](#обзор-системы)
- [Архитектура](#архитектура)
  - [Channel Adapters](#1-channel-adapters-адаптеры-каналов)
  - [Core API](#2-core-api)
  - [Query Processing](#3-query-processing)
  - [Embeddings](#4-embeddings)
  - [Vector Search](#5-vector-search)
  - [Reranking](#6-reranking)
  - [LLM Router](#7-llm-router)
- [Quality System](#quality-system-phase-2)
- [Testing & CI/CD](#testing--cicd)
- [Data Pipeline](#data-pipeline)
- [Performance](#performance-characteristics)
- [Security](#security)
- [Monitoring](#monitoring--observability)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#future-enhancements)

---

## Обзор системы

RAG-система для edna Chat Center - интеллектуальный ассистент с комплексной системой оценки качества, использующий:
- 🔍 Гибридный векторный поиск (dense + sparse)
- 🧠 LLM генерацию с fallback механизмом
- 📊 RAGAS метрики для контроля качества
- 🤖 Интеграцию с Telegram и другими каналами

### Ключевые возможности

| Компонент | Технология | Статус |
|-----------|------------|--------|
| **Embeddings** | BGE-M3 (dense + sparse) | ✅ Production |
| **Vector DB** | Qdrant 1.7+ | ✅ Production |
| **LLM** | YandexGPT + fallbacks | ✅ Production |
| **Quality** | RAGAS + User Feedback | ✅ Production |
| **Testing** | pytest + CI/CD | ✅ Production |
| **Monitoring** | Prometheus + Grafana | ✅ Production |

### Связанная документация

- 🏗️ [Architecture](architecture.md) - Детальная архитектура
- 🔧 [Development Guide](development_guide.md) - Руководство разработчика
- 🧪 [Autotests Guide](autotests_guide.md) - Тестирование
- 📊 [RAGAS Quality System](ragas_quality_system.md) - Система качества
- 🚀 [Deployment Guide](deployment_guide.md) - Развертывание

---

## Quality System (Phase 2)

Система оценки качества RAG ответов с использованием RAGAS метрик и пользовательского фидбека.

**Полная документация**: [RAGAS Quality System](ragas_quality_system.md)

### Компоненты

#### 1. RAGAS Evaluator
- **Версии**: RAGAS 0.1.21 + LangChain 0.2.16
- **Метрики**: Faithfulness, Context Precision, Answer Relevancy
- **LLM**: YandexGPT с детерминированными параметрами
- **Embeddings**: BGE-M3 unified embeddings
- **Производительность**: 2-5 сек с fallback <100ms

#### 2. Quality Manager
- Центральный менеджер оценки качества
- RAGAS оценка + сохранение в БД
- Генерация статистики и трендов

#### 3. Quality Database
- **Технология**: SQLAlchemy 2.0 + SQLite/PostgreSQL
- **Схема**: JSON сериализация для сложных структур
- **Оптимизация**: Индексы по дате и interaction_id

#### 4. Quality API
```http
GET  /v1/admin/quality/stats?days=7
GET  /v1/admin/quality/interactions?limit=10
GET  /v1/admin/quality/trends?days=30&metric=faithfulness
GET  /v1/admin/quality/correlation?days=30
POST /v1/admin/quality/feedback
```

#### 5. Telegram Feedback
- Inline кнопки 👍/👎 для сбора оценок
- Автоматическое сохранение в Quality DB
- Корреляционный анализ с RAGAS метриками

### Использование

```python
from app.services.quality_manager import quality_manager

# Инициализация
await quality_manager.initialize()

# Оценка взаимодействия
interaction_id = await quality_manager.evaluate_interaction(
    query="Как настроить маршрутизацию?",
    response="Маршрутизация настраивается...",
    contexts=["context1", "context2"],
    sources=["https://docs.example.com"]
)

# Статистика
stats = await quality_manager.get_quality_statistics(days=7)
```

👉 **Детали**: [ragas_quality_system.md](ragas_quality_system.md)

---

## Testing & CI/CD

Комплексная система автоматического тестирования и непрерывной интеграции.

**Полная документация**: [Autotests Guide](autotests_guide.md)

### Test Suite Architecture

| Компонент | Технология | Покрытие |
|-----------|------------|----------|
| **Framework** | pytest 8.3.2 + pytest-asyncio | Unit, Integration, E2E |
| **Fixtures** | Redis, Qdrant in Docker | Изолированное окружение |
| **Coverage** | pytest-cov | >80% целевое |
| **CI/CD** | GitHub Actions | Python 3.9, 3.10, 3.11 |

### Типы тестов

**Unit Tests:**
- Отдельные функции и классы
- Моки внешних зависимостей
- Быстрое выполнение (<1 сек)

**Integration Tests:**
- Взаимодействие компонентов
- Реальные сервисы (Redis, Qdrant)
- Маркер: `@pytest.mark.integration`

**End-to-End Tests:**
- Полный pipeline: извлечение → chunking → индексация
- Валидация metadata и конфигурации
- Маркер: `@pytest.mark.slow`

### Быстрый запуск

```bash
# Быстрые тесты
make test-fast

# Полный набор
make test

# С покрытием
make test-coverage

# Конкретный тип
python scripts/run_tests.py --type unit --verbose
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml (упрощенно)
name: CI/CD
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    services:
      redis: redis:7-alpine
      qdrant: qdrant/qdrant:latest
    steps:
      - Checkout code
      - Setup Python
      - Install dependencies
      - Run linting (flake8, black, mypy)
      - Run tests with coverage
      - Upload coverage reports
```

👉 **Детали**: [autotests_guide.md](autotests_guide.md)

---

## Архитектура

### 1. Channel Adapters (Адаптеры каналов)

#### Telegram Adapter
- **Технология**: Long Polling API
- **Форматирование**: HTML с whitelist тегов и автоматическим разбиением
- **Обработка ошибок**: Timeout handling, retry logic
- **Логирование**: Длины HTML, количество частей, ошибки Telegram

```python
# Пример использования
from adapters.telegram_polling import run_polling_loop
run_polling_loop(api_base="http://localhost:9000")
```

#### Web Adapter (планируется)
- **Технология**: WebSocket + REST API
- **Аутентификация**: JWT токены
- **UI**: React/Vue.js интерфейс

### 2. Core API

Flask приложение с RESTful endpoints для обработки запросов.

#### Технический стек
- **Framework**: Flask + Flask-RESTful
- **Port**: 9000 (configurable)
- **CORS**: Cross-origin support
- **Logging**: Structured logging с loguru
- **Docs**: Swagger/Flasgger documentation

#### Chat API

**Endpoint:**
```http
POST /v1/chat/query
Content-Type: application/json
```

**Request:**
```json
{
  "channel": "telegram",
  "chat_id": "123456789",
  "message": "Как настроить маршрутизацию?"
}
```

**Response:**
```json
{
  "answer": "Для настройки маршрутизации...",
  "sources": [
    {
      "title": "Настройка маршрутизации",
      "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/"
    }
  ],
  "channel": "telegram",
  "chat_id": "123456789",
  "interaction_id": "abc123"
}
```

#### Admin API

```http
GET  /v1/admin/health            # Health check
POST /v1/admin/reindex           # Reindex documents
GET  /v1/admin/stats             # System statistics
```

**Полная документация**: [api_reference.md](api_reference.md)

---

### 3. Query Processing

Препроцессинг пользовательских запросов для улучшения качества поиска.

#### Entity Extraction
- **Назначение**: Извлечение ключевых сущностей
- **Технология**: NER модели (планируется)
- **Применение**: Boost релевантных документов

#### Query Rewriting
Переформулирование запроса для расширения поиска:
- "Как настроить?" → "настройка конфигурация параметры"
- "Проблема с API" → "API ошибка проблема решение troubleshooting"

#### Query Decomposition
Разбиение сложных запросов:
- "Как настроить маршрутизацию и сегментацию?" →
  - Запрос 1: "настройка маршрутизации"
  - Запрос 2: "настройка сегментации"

---

### 4. Embeddings

Гибридная система embeddings для семантического и keyword поиска.

#### Dense Embeddings
- **Модель**: BAAI/bge-m3 (1024 dimensions)
- **Framework**: SentenceTransformers
- **Использование**: Семантический поиск
- **Производительность**: ~5-10 сек на запрос

```python
from app.services.core.embeddings import embed_dense

vector = embed_dense("Как настроить маршрутизацию?")
# Returns: list[float] длиной 1024
```

#### Sparse Embeddings
- **Модель**: BGE-M3 sparse component
- **Framework**: FlagEmbedding
- **Использование**: Keyword matching, BM25-like
- **Формат**: {indices: [...], values: [...]}

```python
from app.services.core.embeddings import embed_sparse_optimized

sparse = embed_sparse_optimized("Как настроить маршрутизацию?")
# Returns: {"indices": [1, 42, 567], "values": [0.8, 0.6, 0.4]}
```

---

### 5. Vector Search

Гибридный поиск в Qdrant с RRF fusion.

#### Qdrant Configuration
- **Version**: 1.7+
- **Collection**: edna_docs
- **Dense Index**: HNSW (m=16, ef_construct=100)
- **Sparse Index**: SparseVector
- **Distance**: Cosine similarity

#### Hybrid Search Algorithm

```python
from app.services.search.retrieval import hybrid_search

# Гибридный поиск
results = hybrid_search(
    dense_vector=[0.1, 0.2, ...],  # 1024 dim
    sparse_vector={"indices": [1, 2], "values": [0.8, 0.6]},
    k=20  # Top-20 candidates
)

# Результат: список документов с релевантностью
```

**RRF Fusion:**
- Dense weight: 0.7
- Sparse weight: 0.3
- K parameter: 60
- Top results: 20 documents

**Параметры поиска:**
- `ef_search`: 50 (trade-off скорость/качество)
- `limit`: 20 кандидатов для reranking
- `score_threshold`: 0.3 (минимальная релевантность)

---

### 6. Reranking

Переранжирование результатов для улучшения precision@10.

#### BGE Reranker
- **Модель**: BAAI/bge-reranker-v2-m3
- **Device**: CPU (configurable для GPU)
- **Input**: Query + Top-20 documents
- **Output**: Top-10 reranked documents

```python
from app.services.search.rerank import rerank_candidates

# Reranking
reranked = rerank_candidates(
    query="Как настроить маршрутизацию?",
    candidates=search_results,  # Top-20
    top_n=10
)

# Результат: Top-10 с улучшенной precision
```

**Производительность:**
- Время: 20-30 сек на CPU
- Время: 2-5 сек на GPU (рекомендуется)
- Batch size: 20 documents

---

### 7. LLM Router

Интеллектуальный роутинг между LLM провайдерами с fallback механизмом.

#### Поддерживаемые провайдеры

| Провайдер | Приоритет | Модель | Таймаут |
|-----------|-----------|--------|---------|
| **YandexGPT** | 1 (default) | yandexgpt/latest | 60 сек |
| **GPT-5** | 2 (fallback) | gpt-5-turbo | 60 сек |
| **Deepseek** | 3 (fallback) | deepseek-chat | 60 сек |

#### Fallback Logic

```python
from app.services.core.llm_router import generate_answer

# Автоматический fallback при ошибках
answer = generate_answer(
    query="Как настроить маршрутизацию?",
    context=search_results,
    policy={"max_tokens": 800}
)

# Попытка: YandexGPT → GPT-5 → Deepseek
```

#### Prompt Engineering

```python
prompt_template = """
Вы — ассистент по edna Chat Center.

Правила:
- Используйте ТОЛЬКО предоставленный контекст
- Отвечайте структурировано с заголовками и списками
- Используйте markdown: **жирный**, ### заголовки, * списки
- В конце добавьте "Подробнее: [ссылка]"

Вопрос: {query}

Контекст:
{context}

Ответ:
"""
```

**Оптимизации:**
- Ограничение токенов контекста: 2000
- Детерминированные параметры (temperature=0.1)
- Кэширование частых запросов
- Retry logic с экспоненциальной задержкой

---

## Data Pipeline

Обработка документов от извлечения до индексации.

**Полная документация**: [adding_data_sources.md](adding_data_sources.md)

### 1. Crawling

#### Стратегии извлечения

| Стратегия | Технология | Использование |
|-----------|------------|---------------|
| **Jina Reader** | Jina AI Reader API | Обход антибота, чистый контент |
| **Browser** | Playwright | Сложные SPA, JavaScript |
| **HTTP** | Requests | Простые статические страницы |

**Конфигурация:**
```bash
CRAWL_STRATEGY=jina           # jina, browser, http
CRAWL_TIMEOUT_S=30           # Таймаут на страницу
CRAWL_MAX_PAGES=1000         # Лимит страниц
CRAWL_DELAY_MS=1000          # Задержка между запросами
CRAWL_JITTER_MS=500          # Случайная задержка
```

**Обработка URL:**
- Нормализация API ссылок (`/docs/api` → `/docs/api/index`)
- Фильтрация по префиксам (whitelist/blacklist)
- Парсинг sitemap.xml для обнаружения страниц
- Дедупликация по canonical URLs

---

### 2. Parsing

#### Docusaurus Parser

Специализированный парсер для документации на Docusaurus:

```python
def extract_main_text(soup):
    # Основной контент
    main = soup.select_one(".theme-doc-markdown")

    # Извлечение структуры
    sidebar = soup.select_one(".theme-doc-sidebar-menu")
    pagination = soup.select_one(".pagination-nav")

    return {
        "content": main.get_text(),
        "navigation": extract_navigation(sidebar),
        "links": extract_links(pagination)
    }
```

#### Типы страниц

- **Guides**: Руководства и инструкции
- **API Documentation**: Endpoints, параметры, примеры
- **Release Notes**: Версии, features, bagfixes
- **FAQ**: Вопросы и ответы

---

### 3. Chunking

Интеллектуальное структурное разбиение документов.

**Production параметры** (v4.3.1):
- **Min size**: 150 токенов (фокус на одной теме)
- **Max size**: 300 токенов (предотвращение смешивания контекста)
- **Overlap**: 50 токенов (адаптивный)
- **Deduplication**: По content hash

**Обоснование размеров**:
- Большие чанки (350-600) вызывали смешивание информации из разных разделов
- Меньшие чанки (150-300) обеспечивают точные, фокусированные ответы
- **См.**: [ADR-002](adr-002-adaptive-chunking.md) для деталей эксперимента

```python
from ingestion.chunking.universal_chunker import UniversalChunker

chunker = UniversalChunker(
    max_tokens=300,
    min_tokens=150,
    overlap_base=50,
    oversize_block_policy="split"
)

# Структурное разбиение (заголовки, параграфы, code blocks)
chunks = chunker.chunk(
    text=document_text,
    fmt="markdown",
    meta={"doc_id": "...", "url": "..."}
)
```

**Важно**: Размер определяется **структурой документа**, не фиксированными правилами.

---

### 4. Indexing

Запись чанков в Qdrant с rich metadata.

#### Metadata Schema

```python
payload = {
    # Основные поля
    "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/",
    "title": "Настройка маршрутизации",
    "text": "Содержимое чанка...",

    # Классификация
    "page_type": "guide",  # guide, api, faq, release_notes
    "source": "docs-site",
    "language": "ru",

    # Техническая информация
    "chunk_id": "unique_id_abc123",
    "created_at": "2024-10-09T00:00:00Z",
    "doc_id": "routing-guide",

    # Навигация
    "heading_path": ["Admin", "Routing", "Configuration"]
}
```

#### Batch Processing

```python
from ingestion.pipeline.indexers import QdrantWriter

writer = QdrantWriter(collection_name="edna_docs")

# Batch upsert (100 chunks per batch)
result = writer.upsert_chunks(
    chunks=prepared_chunks,
    batch_size=100
)

print(f"Indexed {result['count']} chunks")
```

---

## Performance Characteristics

Целевые показатели производительности системы.

### Время обработки запроса

| Этап | Целевое время | Комментарий |
|------|---------------|-------------|
| Query Processing | <1 сек | Preprocessing, entity extraction |
| Dense Embedding | 5-10 сек | BGE-M3 encoding |
| Sparse Embedding | 3-5 сек | BGE-M3 sparse component |
| Vector Search | 1-2 сек | Qdrant hybrid search |
| Reranking | 20-30 сек | BGE reranker (CPU) |
| LLM Generation | 30-60 сек | YandexGPT/GPT-5 |
| **Total** | **60-120 сек** | End-to-end latency |

### Масштабируемость

| Параметр | Значение | Примечание |
|----------|----------|------------|
| **Concurrent Users** | 100+ | С горизонтальным масштабированием |
| **Documents** | 10,000+ | Страниц документации |
| **Chunks** | 100,000+ | Индексированных чанков |
| **QPS** | 10+ | Запросов в секунду |
| **Uptime** | 99.9% | Production SLA |

### Требования к ресурсам

**Минимальные:**
- RAM: 8GB
- CPU: 4 cores
- Storage: 2GB
- Network: 10 Mbps

**Рекомендуемые (Production):**
- RAM: 16GB+
- CPU: 8+ cores
- Storage: 10GB+ SSD
- Network: 100 Mbps+
- GPU: опционально (для reranking)

---

## Security

Обеспечение безопасности системы и данных.

### API Security

**Rate Limiting:**
- Защита от DDoS атак
- Лимиты по IP/User
- Backoff mechanism

**Input Validation:**
- Sanitization входных данных
- Максимальная длина запросов
- Фильтрация опасных паттернов

**Error Handling:**
- Безопасные сообщения об ошибках
- Без раскрытия внутренней информации
- Structured error logging

### Data Security

**API Keys:**
```bash
# Хранение в переменных окружения
YANDEX_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# НЕ коммитить в Git!
# Использовать .env файлы
```

**HTTPS:**
- Обязательно для production
- TLS 1.2+
- Valid SSL certificates

**Access Control:**
- Ограничение admin endpoints
- Role-based access control (планируется)
- API key authentication

### Privacy & Compliance

**Logging:**
- Без персональных данных в логах
- Анонимизация chat_id
- Retention policies

**Data Retention:**
- Настраиваемые политики хранения
- Automatic cleanup старых данных
- GDPR compliance ready

---

## Monitoring & Observability

Мониторинг состояния системы и качества ответов.

**Полная документация**: [monitoring_setup.md](monitoring_setup.md)

### Prometheus метрики

```bash
# Доступны на /metrics endpoint
curl http://localhost:9000/metrics

# Основные метрики:
rag_queries_total                    # Общее количество запросов
rag_query_duration_seconds           # Latency запросов
rag_llm_usage_total{provider="..."}  # Использование LLM
ragas_score{metric_type="..."}       # RAGAS оценки качества
user_satisfaction_rate               # Удовлетворенность пользователей
```

### Grafana Dashboards

**Основные дашборды:**
- System Overview - общие метрики
- Quality Dashboard - RAGAS + user feedback
- LLM Usage - использование провайдеров
- Performance - latency и throughput

**Запуск:**
```bash
.\start_monitoring.ps1  # Windows
./start_monitoring.sh   # Linux/Mac

# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

### Логирование

**Структурированные логи:**
```python
from loguru import logger

# Успешная обработка
logger.info("Query processed",
           query_len=len(query),
           duration_s=elapsed,
           sources_count=len(sources))

# Ошибка
logger.error("LLM failed",
            provider="yandex",
            error=str(e),
            fallback="gpt5")
```

**Уровни:**
- `DEBUG` - детальная отладка
- `INFO` - нормальная работа
- `WARNING` - проблемы, не критичные
- `ERROR` - критические ошибки

### Health Checks

```python
# GET /v1/admin/health
{
  "status": "ok",
  "components": {
    "qdrant": "ok",
    "llm_providers": {
      "yandex": "ok",
      "gpt5": "ok"
    },
    "embeddings": "ok",
    "quality_db": "ok"
  },
  "uptime_seconds": 12345
}
```

---

## Deployment

Развертывание системы в различных окружениях.

**Полная документация**: [deployment_guide.md](deployment_guide.md)

### Development

```bash
# Локальная разработка
python wsgi.py                        # Flask API
python adapters/telegram/polling.py  # Telegram bot

# Или через make
make dev
```

### Docker Compose

```bash
# Запуск полного стека
docker-compose up -d

# Сервисы:
# - rag-api (Flask API)
# - telegram-bot (Telegram adapter)
# - qdrant (Vector DB)
# - redis (Cache)
# - prometheus (Metrics)
# - grafana (Visualization)
```

### Kubernetes

```bash
# Применение манифестов
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/

# Проверка статуса
kubectl get pods -n rag-system

# Логи
kubectl logs -f deployment/rag-api -n rag-system
```

### CI/CD

```yaml
# GitHub Actions workflow
- Linting (flake8, black, mypy)
- Testing (pytest + coverage)
- Security (bandit, safety)
- Build Docker images
- Deploy to staging/production
```

---

## Troubleshooting

Решение распространенных проблем.

### High Response Time

**Симптомы:** Запросы обрабатываются > 2 минут

**Причины и решения:**
- ❌ LLM API недоступен → Проверьте API ключи
- ❌ Медленный reranking → Используйте GPU или уменьшите top_n
- ❌ Большие чанки → Оптимизируйте chunking параметры

### Poor Search Quality

**Симптомы:** Нерелевантные результаты поиска

**Причины и решения:**
- ❌ Устаревшие данные → Переиндексируйте документацию
- ❌ Неоптимальные веса → Настройте RRF веса (dense/sparse)
- ❌ Плохой парсинг → Проверьте качество извлечения текста

### Memory Issues

**Симптомы:** Out of Memory errors

**Причины и решения:**
- ❌ Большие batch размеры → Уменьшите batch_size
- ❌ Утечки памяти → Проверьте цикл garbage collection
- ❌ Много concurrent запросов → Настройте rate limiting

### Debug Mode

```bash
# Включение debug логирования
export DEBUG=true
export LOG_LEVEL=DEBUG

# Профилирование
python -m cProfile -o profile.stats wsgi.py

# Анализ профиля
python -m pstats profile.stats
```

---

## Future Enhancements

Планы развития системы.

### Short Term (Q4 2024)

- [ ] Web интерфейс для администрирования
- [ ] A/B тестирование разных prompt стратегий
- [ ] Кэширование частых запросов
- [ ] Batch обработка запросов
- [ ] Улучшенная аналитика использования

### Medium Term (Q1-Q2 2025)

- [ ] Многоязычность (EN, RU поддержка)
- [ ] Voice интерфейс (voice-to-text)
- [ ] Персонализация ответов по пользователю
- [ ] Feedback loop для улучшения качества
- [ ] Advanced analytics dashboard

### Long Term (2025+)

- [ ] Fine-tuning моделей на domain data
- [ ] Real-time обучение на пользовательском фидбеке
- [ ] Multi-modal поиск (text + images)
- [ ] Автоматическое обновление knowledge base
- [ ] Enterprise features (SSO, RBAC)

---

## 📚 Связанная документация

- [Architecture Overview](architecture.md) - Детальная архитектура
- [Internal API Reference](internal_api.md) - Внутренние API
- [Development Guide](development_guide.md) - Руководство разработчика
- [Autotests Guide](autotests_guide.md) - Тестирование
- [RAGAS Quality System](ragas_quality_system.md) - Система качества
- [Deployment Guide](deployment_guide.md) - Развертывание
- [API Reference](api_reference.md) - REST API документация

---

**Версия документа**: 4.3.1
**Последнее обновление**: 9 октября 2024
**Статус**: Production Ready
