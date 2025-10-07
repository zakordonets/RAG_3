# RAG-система для edna Chat Center

Интеллектуальный помощник на базе RAG (Retrieval-Augmented Generation) для технической поддержки продукта edna Chat Center. Система использует векторный поиск по документации и генерацию ответов с помощью LLM.

## 🎉 v4.0.0 - Единая архитектура индексации завершена!

**Система переведена на унифицированный DAG пайплайн:**
- 🏗️ **Единый DAG пайплайн** - унифицированная обработка всех источников данных
- 🔌 **Source Adapters** - адаптеры для Docusaurus, веб-сайтов и других источников
- 🧩 **Pipeline Steps** - модульные шаги обработки (Parse → Normalize → Chunk → Embed → Index)
- 📊 **Unified State Manager** - единое управление состоянием документов
- 🧹 **Normalizers** - плагины нормализации для разных типов контента
- 📦 **Qdrant Writer** - единый писатель в векторную базу данных
- 🔧 **Упрощенная структура** - убрано 13 лишних файлов, оставлены только активные компоненты
- 🧪 **Полное покрытие тестами** - 101 тест для новой архитектуры
- 📈 **Улучшение производительности** - оптимизированные батчи и обработка
- 🗑️ **Устранение дублирования** - единый код для всех источников данных

**📖 Подробности:** [Архитектурная документация](docs/architecture.md) | [Руководство по миграции](docs/migration_guide.md)

## 🚀 Возможности

- **Многоканальность**: Поддержка Telegram и готовность к другим каналам
- **Гибридный поиск**: Комбинация dense и sparse эмбеддингов с RRF fusion (100% покрытие sparse векторами)
- **Семантическое chunking**: Улучшенное разбиение текста на основе сходства
- **GPU-ускорение**: Unified BGE-M3 embeddings с автоматическим выбором стратегии (ONNX+DirectML, BGE-M3+CPU, Hybrid)
- **Sparse векторы**: Локальная генерация sparse эмбеддингов через BGE-M3 (без внешнего сервиса)
- **Умная маршрутизация**: Автоматический fallback между LLM провайдерами
- **Красивое форматирование**: MarkdownV2 через `telegramify-markdown` v0.5.1 с эмодзи и структурированными ответами
- **Redis кеширование**: Высокопроизводительное кеширование эмбеддингов и результатов поиска
- **Гибкая система источников**: Поддержка веб-сайтов, локальных папок, API документации, блогов, FAQ
- **Модульные краулеры**: Легкое добавление новых типов источников данных
- **Production-ready**: Comprehensive error handling, Circuit Breaker, метрики Prometheus
- **Безопасность**: Полная валидация, санитизация и мониторинг безопасности
- **Rate Limiting**: Защита от злоупотреблений с burst protection
- **Мониторинг**: Prometheus метрики и детальное логирование
- **Надежность**: Graceful degradation и автоматическое восстановление
- **Phase 2: RAGAS Quality System**: Автоматическая оценка качества с RAGAS метриками (Faithfulness, Context Precision, Answer Relevancy)
- **Пользовательский фидбек**: Inline кнопки в Telegram для оценки ответов
- **Quality Analytics**: REST API для анализа качества и трендов
- **Prometheus метрики**: Мониторинг качества через Grafana dashboard

## 🏗️ Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │   Web Interface │    │   Other Channels│
│   (Long Polling)│    │   (Future)      │    │   (Future)      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      Channel Adapters     │
                    │   (Telegram, Web, etc.)   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │        Core API           │
                    │    (Flask + RESTful)      │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     Query Processing      │
                    │ (Entity Extraction, etc.) │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      Embeddings          │
                    │ (BGE-M3 Unified + Redis) │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      Vector Search        │
                    │ (Qdrant + Dense + Sparse) │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │       Reranking          │
                    │   (BGE-reranker-v2-m3)   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      LLM Router          │
                    │ (YandexGPT, GPT-5, etc.) │
                    └───────────────────────────┘
```

## 📋 Требования

### Системные требования
- Python 3.11+
- Docker (для Qdrant и Redis)
- 8GB+ RAM (рекомендуется)
- 2GB+ свободного места

### API ключи
- YandexGPT API ключ
- Deepseek API ключ (опционально)
- GPT-5 API ключ (опционально)
- Telegram Bot Token

## 🛠️ Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd RAG_2
```

### 2. Создание виртуального окружения
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка окружения
```bash
cp env.example .env
# Отредактируйте .env файл с вашими API ключами
```

### 5. Запуск сервисов

#### Qdrant (векторная база данных)
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

#### Redis (кеширование)
```bash
docker run -p 6379:6379 redis:7-alpine
```

Или используйте Docker Compose для запуска всех сервисов:
```bash
docker-compose up -d redis qdrant
```

### 6. Инициализация базы данных
```bash
python scripts/init_qdrant.py
```

### 7. Индексация документации (v4.0.0)

#### Единый пайплайн индексации (рекомендуется)
```bash
# Индексация Docusaurus документации
python -m ingestion.run --source docusaurus --docs-root "C:\CC_RAG\docs"

# Индексация веб-сайта
python -m ingestion.run --source website --seed-urls "https://example.com"

# С конфигурационным файлом
python -m ingestion.run --source docusaurus --config ingestion/config.yaml
```

#### Конфигурация индексации
```yaml
# ingestion/config.yaml
global:
  qdrant:
    url: "http://localhost:6333"
    collection: "docs_chatcenter"
  embeddings:
    backend: "auto"
    batch_size: 2
    use_sparse: true

sources:
  docusaurus:
    enabled: true
    docs_root: "C:\\CC_RAG\\docs"
    site_base_url: "https://docs-chatcenter.edna.ru"
    site_docs_prefix: "/docs"
    chunk:
      max_tokens: 300
      overlap_tokens: 60
```

#### Добавление нового источника данных
```bash
# 1. Создайте новый SourceAdapter в ingestion/adapters/
# 2. Добавьте нормализаторы в ingestion/normalizers/
# 3. Обновите ingestion/run.py для поддержки нового источника
# 4. Добавьте тесты в tests/
print(f'Found {len(results)} pages')
"
```

### 8. Запуск системы

#### Flask API
```bash
python wsgi.py
```

#### Telegram Bot
```bash
# Способ 1: Прямой запуск (рекомендуется)
python adapters/telegram/polling.py

# Способ 2: Через batch-скрипт (Windows)
start_telegram_bot.bat

# Способ 3: Через PowerShell скрипт
.\start_telegram_bot.ps1
```

Форматирование ответов выполняется библиотекой `telegramify-markdown`, отправка сообщений — с `parse_mode=MarkdownV2`. В логах Core API фиксируется, какой метод библиотеки применён (markdownify/telegramify) и предпросмотр результата, что помогает диагностировать ошибки форматирования (400: can't parse entities).

При ошибке отправки в MarkdownV2 срабатывает fallback — пересылка без форматирования.

Если видите лишние обратные слэши в сообщении, убедитесь, что используется именно `MarkdownV2` и текст не проходит дополнительное экранирование вне `telegramify-markdown`.

### Оптимизация reranker

Реранжирование кандидатов (BAAI/bge-reranker-v2-m3) выполнено с пакетной обработкой:

- batch_size: 20
- max_length: 384 (усечение текста перед токенизацией)

Это снижает накладные расходы токенизации/инференса на CPU. Реализация — `app/services/rerank.py`, включено в оркестраторе `app/services/orchestrator.py`.

## 🔧 Конфигурация

### Основные настройки (.env)

```env
# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key

# LLM провайдеры
YANDEX_API_KEY=your_yandex_key
DEEPSEEK_API_KEY=your_deepseek_key
GPT5_API_KEY=your_gpt5_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# BGE-M3 Unified Embeddings
EMBEDDINGS_BACKEND=auto  # auto|onnx|bge|hybrid
EMBEDDING_DEVICE=auto    # auto|cpu|cuda|directml
EMBEDDING_MAX_LENGTH_QUERY=512
EMBEDDING_MAX_LENGTH_DOC=1024
EMBEDDING_BATCH_SIZE=16
USE_SPARSE=true

# Legacy (для совместимости)
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DIM=1024

# Поиск
HYBRID_DENSE_WEIGHT=0.7
HYBRID_SPARSE_WEIGHT=0.3
RERANK_TOP_N=10

# Phase 2: RAGAS Quality System
ENABLE_RAGAS_EVALUATION=true
RAGAS_EVALUATION_SAMPLE_RATE=1.0
QUALITY_DB_ENABLED=true
DATABASE_URL=sqlite+aiosqlite:///data/quality_interactions.db
ENABLE_QUALITY_METRICS=true
```

### BGE-M3 Unified Embeddings

Система использует единый BGE-M3 сервис для генерации dense и sparse эмбеддингов с автоматическим выбором оптимальной стратегии.

#### Стратегии эмбеддингов

**`EMBEDDINGS_BACKEND=auto`** (рекомендуется) - автоматический выбор:
- **NVIDIA GPU**: `bge` - BGE-M3 с CUDA ускорением
- **AMD GPU (Windows)**: `hybrid` - Dense через ONNX+DirectML, Sparse через BGE-M3+CPU
- **CPU only**: `onnx` - ONNX Runtime для консистентности

**`EMBEDDINGS_BACKEND=onnx`** - ONNX Runtime:
- ✅ Dense embeddings через ONNX+DirectML (Windows/AMD)
- ❌ Sparse embeddings не поддерживаются
- 🎯 Лучший выбор для Windows/AMD GPU

**`EMBEDDINGS_BACKEND=bge`** - Нативный BGE-M3:
- ✅ Dense + Sparse embeddings
- ✅ CUDA ускорение (NVIDIA)
- ❌ DirectML не поддерживается
- 🎯 Лучший выбор для NVIDIA GPU

**`EMBEDDINGS_BACKEND=hybrid`** - Гибридный подход:
- ✅ Dense через ONNX+DirectML (GPU)
- ✅ Sparse через BGE-M3+CPU
- 🎯 Оптимально для Windows/AMD

#### ONNX Runtime конфигурация

Переключатель ONNX провайдера (`ONNX_PROVIDER`):
- `auto` — DmlExecutionProvider → CPU fallback (по умолчанию)
- `dml` — принудительно DirectML (если доступен)
- `cpu` — принудительно CPU

#### Примеры запуска

```powershell
# Автоматический выбор стратегии
$env:EMBEDDINGS_BACKEND="auto"; python scripts\test_auto_strategy.py

# Принудительно hybrid для Windows/AMD
$env:EMBEDDINGS_BACKEND="hybrid"; $env:ONNX_PROVIDER="dml"

# Бенчмарк всех стратегий
python scripts\benchmark_embeddings_strategies.py
```

#### Производительность

Результаты бенчмарка на AMD Radeon RX 6700 XT (Windows):

| Стратегия | Средняя производительность | Dense | Sparse | GPU |
|-----------|---------------------------|--------|--------|-----|
| **Hybrid** | **0.098s** ⚡ | ONNX+DirectML | BGE-M3+CPU | ✅ |
| ONNX | 0.232s | ONNX+DirectML | ❌ | ✅ |
| BGE | 0.314s | BGE-M3+CPU | BGE-M3+CPU | ❌ |

**Рекомендации:**
- 🏆 **Windows/AMD**: `EMBEDDINGS_BACKEND=hybrid` для лучшей производительности
- 🏆 **Linux/NVIDIA**: `EMBEDDINGS_BACKEND=bge` для полного GPU ускорения
- 🏆 **CPU only**: `EMBEDDINGS_BACKEND=onnx` для стабильности
- ⚙️ **Автоматически**: `EMBEDDINGS_BACKEND=auto` (рекомендуется)

### Настройка краулера

```env
CRAWL_START_URL=https://docs-chatcenter.edna.ru/
CRAWL_STRATEGY=jina  # jina, browser, http
CRAWL_TIMEOUT_S=30
CRAWL_MAX_PAGES=1000
```

## 📊 API Endpoints

### Chat API
- `POST /v1/chat/query` - Обработка запросов пользователей с валидацией

### Quality API (Phase 2)
- `GET /v1/admin/quality/stats` - Статистика качества взаимодействий
- `GET /v1/admin/quality/interactions` - Список взаимодействий с метриками
- `GET /v1/admin/quality/trends` - Тренды качества по времени
- `GET /v1/admin/quality/correlation` - Корреляционный анализ метрик
- `POST /v1/admin/quality/feedback` - Добавление пользовательского фидбека

### Admin API
- `GET /v1/admin/health` - Проверка состояния системы с Circuit Breakers
- `POST /v1/admin/reindex` - Переиндексация документации

### API Документация
- `GET /apidocs` - Swagger UI для интерактивного тестирования API
- `GET /apispec_1.json` - OpenAPI 2.0 спецификация в JSON формате

### Мониторинг
- `GET /v1/admin/metrics` - Метрики Prometheus в JSON
- `GET /v1/admin/metrics/raw` - Сырые метрики Prometheus
- `GET /v1/admin/circuit-breakers` - Состояние Circuit Breakers
- `GET /v1/admin/cache` - Статистика кэша

### Rate Limiting
- `GET /v1/admin/rate-limiter` - Состояние Rate Limiter
- `GET /v1/admin/rate-limiter/<user_id>` - Состояние пользователя
- `POST /v1/admin/rate-limiter/<user_id>/reset` - Сброс лимитов

### Безопасность
- `GET /v1/admin/security` - Статистика безопасности
- `GET /v1/admin/security/user/<user_id>` - Состояние пользователя
- `POST /v1/admin/security/user/<user_id>/block` - Блокировка пользователя

## 🧪 Тестирование (v4.0.0)

### Единая архитектура тестов

Система включает 101 тест для новой единой архитектуры:

```bash
# Все тесты новой архитектуры
python -m pytest tests/test_unified_* tests/test_docusaurus_* -v

# Тесты адаптеров источников
python -m pytest tests/test_unified_adapters.py -v

# Тесты пайплайна
python -m pytest tests/test_unified_pipeline.py -v

# Тесты индексации
python -m pytest tests/test_unified_indexing.py -v

# Интеграционные тесты
python -m pytest tests/test_unified_integration.py -v

# Тесты Docusaurus компонентов
python -m pytest tests/test_docusaurus_* -v
```

### Покрытие тестами

**✅ Полностью покрыто:**
- Source Adapters (Docusaurus, Website)
- Pipeline DAG и шаги
- Qdrant Writer и индексация
- Utils функции (clean, links, pathing)
- Docusaurus crawler

**📊 Статистика:**
- **101 тест** для новой архитектуры
- **58 тестов** основной архитектуры
- **43 теста** Docusaurus компонентов
- **0 ошибок** в тестах

### Автотесты (Рекомендуется)

```bash
# Все быстрые тесты
make test-fast

# Только unit тесты
make test-unit

# Все тесты (включая медленные)
make test

# Тесты с покрытием кода
make test-coverage

# Линтинг и форматирование
make lint
make format
```

**Доступные команды:**
- `make test-unit` - только unit тесты
- `make test-integration` - интеграционные тесты
- `make test-e2e` - end-to-end тесты
- `make test-slow` - медленные тесты
- `make test-fast` - быстрые тесты (без медленных)

### End-to-End Pipeline Тесты

```bash
# Полный тест pipeline от извлечения до записи в Qdrant
pytest tests/test_end_to_end_pipeline.py -v

# Запуск через pytest
python scripts/run_tests.py --type fast --verbose
```

**Покрываемые сценарии:**
- ✅ Извлечение и chunking документов
- ✅ Адаптивные стратегии chunking
- ✅ Индексация с enhanced metadata
- ✅ Валидация конфигурации
- ✅ Система плагинов источников данных
- ✅ Метрики качества chunking

### CI/CD Pipeline

Автоматические тесты запускаются при:
- Push в ветки `main`, `develop`
- Создании Pull Request

**GitHub Actions:**
- Поддержка Python 3.9, 3.10, 3.11
- Сервисы Redis и Qdrant для тестов
- Линтинг и проверка типов
- Генерация отчетов о покрытии

### Phase 2: RAGAS Quality System
```bash
# Интеграционные тесты Phase 2
$env:PYTHONPATH=(Get-Location).Path; pytest tests/test_integration_phase2.py -v

# Тесты с отключенным RAGAS (быстрые)
$env:RAGAS_EVALUATION_SAMPLE_RATE="0"; pytest tests/test_integration_phase2.py -v

# Проверка Quality API
curl http://localhost:9000/v1/admin/quality/stats
curl http://localhost:9000/v1/admin/quality/interactions
```

### Тест API
```bash
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"message": "Как настроить маршрутизацию?"}'
```

### Интерактивная документация API
```bash
# Откройте в браузере
http://localhost:9000/apidocs

# Или получите OpenAPI спецификацию
curl http://localhost:9000/apispec_1.json
```

### Тест Telegram бота
1. Найдите бота в Telegram: `@edna_cc_bot`
2. Отправьте сообщение: "Привет"
3. Проверьте ответ

## 📈 Мониторинг

### 🚀 Быстрый старт мониторинга
```bash
# Запуск Grafana + Prometheus
.\start_monitoring.ps1

# Доступ к интерфейсам
# Prometheus: http://localhost:9090
# Grafana: http://localhost:8080 (admin/admin123)
```

### Логи
Система использует `loguru` для структурированного логирования:
- Время обработки каждого этапа
- Ошибки и предупреждения с контекстом
- Статистика запросов и производительности

### Prometheus метрики
- `rag_queries_total` - количество запросов по каналам и статусам
- `rag_query_duration_seconds` - длительность этапов обработки
- `rag_embedding_duration_seconds` - время создания эмбеддингов
- `rag_search_duration_seconds` - время поиска
- `rag_llm_duration_seconds` - время генерации LLM
- `rag_cache_hits_total` - попадания в кэш
- `rag_errors_total` - ошибки по типам и компонентам

### Grafana дашборды
- **RAG System Overview** - основной дашборд с ключевыми метриками
- Автоматическое создание при первом запуске
- Визуализация производительности, кэша, ошибок

### HTTP сервер метрик
- Порт: 9002
- Endpoint: `http://localhost:9002/metrics`
- Совместимость с Grafana и другими системами мониторинга

### Подробная документация
- [MONITORING_README.md](MONITORING_README.md) - краткое руководство
- [docs/monitoring_setup.md](docs/monitoring_setup.md) - подробная настройка

## 🚀 Redis кеширование

### Автоматическая настройка
Redis автоматически используется для кеширования:
- **Эмбеддингов** - значительное ускорение повторных запросов
- **Результатов поиска** - быстрые ответы на похожие вопросы
- **LLM ответов** - экономия API вызовов

### Быстрый запуск Redis
```bash
# Через Docker (рекомендуется)
docker run -p 6379:6379 redis:7-alpine

# Или через Docker Compose
docker-compose up -d redis
```

### Настройка в .env
```env
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=  # Оставьте пустым для работы без пароля
```

### Мониторинг Redis
Статистика доступна в health endpoint:
```bash
curl http://localhost:9000/v1/admin/health
```

Показывает:
- Подключенные клиенты
- Попадания/промахи кеша
- Используемая память
- Тип кеша (redis/memory)

## 🔄 Переиндексация с улучшенными заголовками

### 🚀 Рекомендуемый способ (единый модуль)

Для получения максимального качества поиска с улучшенными заголовками используется единый production модуль:

```bash
# Проверить статус системы
$env:PYTHONPATH = "$PWD"; python scripts/indexer.py status

# Полная переиндексация (рекомендуется)
$env:PYTHONPATH = "$PWD"; python scripts/indexer.py reindex --mode full

# Тестовая переиндексация (только 5 страниц)
$env:PYTHONPATH = "$PWD"; python scripts/indexer.py reindex --mode full --max-pages 5
```

### ✨ Улучшения заголовков

Система теперь автоматически извлекает информативные заголовки из Jina Reader:

**До:** `Sv Threadcontrol Threadtransfer` (из URL)
**После:** `Индикаторы в тредах` (из контента) ✨

### ⚙️ Альтернативные способы

```bash
# Через модуль pipeline
$env:PYTHONPATH = "$PWD"; python -m ingestion.pipeline

# Через API (автоматическое обновление)
curl -X POST http://localhost:9000/v1/admin/reindex

# Инкрементальное обновление (только новые страницы)
$env:PYTHONPATH = "$PWD"; python -c "
from ingestion.pipeline import crawl_and_index
crawl_and_index(incremental=True, strategy='jina', use_cache=True)
"
```

### 🎯 Единый модуль индексации

Система теперь использует единый production модуль `scripts/indexer.py`, который заменяет все старые скрипты:

**✨ Возможности:**
- 🚀 **Единая точка входа** для всех операций индексации
- 📊 **Автоматическая диагностика** состояния системы
- 🔧 **Полная совместимость** со старыми методами
- ⚙️ **Гибкая конфигурация** через параметры командной строки
- 🧹 **Упрощенный интерфейс** без избыточных параметров

**🔄 Основные команды:**
```bash
# Проверка статуса системы
python scripts/indexer.py status

# Полная переиндексация (рекомендуется)
python scripts/indexer.py reindex --mode full

# Инкрементальное обновление
python scripts/indexer.py reindex --mode incremental

# Использовать только кешированные страницы
python scripts/indexer.py reindex --mode cache_only

# Очистка кеша страниц
python scripts/indexer.py clear-cache --confirm

# Инициализация коллекции
python scripts/indexer.py init

# Пересоздание коллекции
python scripts/indexer.py init --recreate

# Тестовая переиндексация
python scripts/indexer.py reindex --mode full --max-pages 5
```

### 💾 Управление кешем

Система автоматически сохраняет загруженные страницы в кеш для ускорения последующих индексаций:

```bash
# Проверка содержимого кеша
ls cache/crawl/pages/  # Просмотр закешированных страниц

# Очистка кеша (требует подтверждения)
python scripts/indexer.py clear-cache --confirm

# Индексация с очисткой устаревших записей
python scripts/indexer.py reindex --mode full --cleanup-cache

# Быстрое тестирование на закешированных данных
python scripts/indexer.py reindex --mode cache_only
```

**📋 Особенности кеширования:**
- ✅ Кеш сохраняется между запусками системы
- ✅ При `--max-pages` ограничении кеш не очищается автоматически
- ✅ Очистка требуется только при изменении структуры сайта
- ✅ Используйте `cache_only` для быстрого тестирования

### 🔄 Миграция со старых скриптов

**Старые скрипты заменены единым модулем:**

| Старый скрипт | Новая команда |
|---------------|---------------|
| `python scripts/reindex.py` | `python scripts/indexer.py reindex --mode full` |
| `python scripts/full_reindex.py` | `python scripts/indexer.py reindex --mode full` |
| `python scripts/run_full_reindex.py` | `python scripts/indexer.py reindex --mode full` |

**🧹 Очистка старых скриптов:**

Если у вас остались старые скрипты индексации, их можно удалить:

```bash
$env:PYTHONPATH = "$PWD"; python scripts/cleanup_old_scripts.py
```

**✅ Преимущества нового подхода:**
- 🚀 **Простота**: Один модуль вместо множества скриптов
- 📊 **Диагностика**: Автоматическая проверка состояния системы
- 🔧 **Гибкость**: Все режимы в одном месте
- 📝 **Документация**: Встроенная справка и примеры

### 📊 Преимущества переиндексации

**🎯 Качество поиска:**
- ✅ **Sparse vectors**: Улучшенная релевантность на 15-25%
- ✅ **Unified embeddings**: Консистентные dense + sparse векторы
- ✅ **Batch processing**: Более стабильные результаты
- ✅ **Улучшенные заголовки**: Информативные названия из контента вместо URL

**⚡ Производительность:**
- ✅ **2.5x быстрее**: Unified generation vs раздельные embeddings
- ✅ **GPU ускорение**: DirectML для dense (Windows/AMD)
- ✅ **Adaptive max_length**: Оптимизация под длину документов
- ✅ **Кеширование**: Использование Redis для ускорения повторных запросов

**🔧 Совместимость:**
- ✅ **Размерность**: 1024 (как в старой системе)
- ✅ **Модель**: BAAI/bge-m3 (та же)
- ✅ **Graceful fallback**: Автоматический выбор стратегии
- ✅ **Jina Reader**: Автоматическое извлечение заголовков из структурированного текста

### 🔍 Проверка необходимости переиндексации

```bash
# Проверить текущее состояние базы
python -c "
from qdrant_client import QdrantClient
from app.config import CONFIG
import json

client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)
collection_info = client.get_collection(CONFIG.qdrant_collection)
points = client.scroll(CONFIG.qdrant_collection, limit=1, with_vectors=True)

print('📊 Текущее состояние базы:')
print(f'Количество векторов: {collection_info.points_count}')
print(f'Dense размерность: {len(points[0][0].vector[\"dense\"]) if points[0] else \"N/A\"}')
print(f'Sparse vectors: {\"✅ Есть\" if points[0] and hasattr(points[0][0], \"sparse_vectors\") and points[0][0].sparse_vectors else \"❌ Отсутствуют\"}')

if not (points[0] and hasattr(points[0][0], 'sparse_vectors') and points[0][0].sparse_vectors):
    print('\\n🚀 Рекомендуется переиндексация для добавления sparse vectors!')
else:
    print('\\n✅ База актуальна, переиндексация опциональна.')
"
```

### ⚠️ Важные моменты

- **Время выполнения**: 10-30 минут в зависимости от размера документации
- **Прерывание**: Используйте `Ctrl+C` для безопасной остановки
- **Мониторинг**: Процесс показывает детальный прогресс и статистику
- **Совместимость**: Старые векторы остаются работоспособными

### 🛠️ Инкрементальное обновление (будущая функция)

```python
from ingestion.pipeline import crawl_and_index
# В будущих версиях: сравнение hash и пропуск неизменённых документов
crawl_and_index(incremental=True)
```

## 🚀 Развертывание

### Docker (рекомендуется)
```bash
# Запуск всех сервисов (Qdrant, Redis, RAG API, Telegram Bot)
docker-compose up -d

# Или запуск только необходимых сервисов
docker-compose up -d redis qdrant rag-api
```

Сервисы:
- **Redis** - кеширование эмбеддингов (порт 6379)
- **Qdrant** - векторная база данных (порт 6333)
- **RAG API** - основной API (порт 9000)
- **Telegram Bot** - Telegram интерфейс
- **Prometheus метрики** - мониторинг (порт 9002)

### Production настройки
- Используйте Gunicorn вместо Flask dev server
- Настройте reverse proxy (Nginx)
- Включите HTTPS
- Настройте мониторинг (Prometheus + Grafana)

## 🔧 Критические исправления

Система прошла комплексную модернизацию для production-ready развертывания:

### ✅ Исправленные проблемы (v2.2.0)
- **Sparse векторы** - полная замена коллекции с поддержкой sparse векторов
- **Гибридный поиск** - 100% покрытие sparse векторами (512/512 точек)
- **Структура Qdrant** - исправлена структура named vectors для dense+sparse
- **Backend поддержка** - добавлена поддержка 'auto' backend для sparse векторов
- **YandexGPT API** - обновлен для использования модели yandexgpt/rc
- **Полная переиндексация** - все 516 чанков переиндексированы с sparse векторами
- **Redis кеширование** - добавлена сериализация numpy типов для JSON
- **Telegram форматирование** - обновлен telegramify-markdown до v0.5.1
- **Metrics сервер** - изменен порт с 8001 на 9001
- **BGE эмбеддинги** - исправлена ошибка ONNX с типами данных (int32→int64)
- **Архитектура** - удален неиспользуемый sparse сервис (упрощение)
- **Извлечение заголовков** - улучшено извлечение информативных заголовков из Jina Reader текста
- **Контекст LLM** - исправлена передача контента документов в промпт для более точных ответов
- **Единый модуль индексации** - создан production-ready модуль `scripts/indexer.py` для замены множества скриптов
- **Упрощение интерфейса** - убраны избыточные параметры, автоматический выбор оптимальных настроек
- **Comprehensive Error Handling** - обработка ошибок на каждом этапе
- **Валидация и санитизация** - защита от XSS и инъекций
- **Кэширование** - Redis + in-memory fallback для производительности
- **Circuit Breaker** - защита от каскадных сбоев внешних сервисов
- **Prometheus метрики** - полный мониторинг системы
- **Семантическое chunking** - улучшенное разбиение текста
- **Rate Limiting** - защита от злоупотреблений
- **Система безопасности** - мониторинг и блокировка пользователей
- **Мониторинг метрики** - исправлен конфликт портов (9001→9002), метрики теперь корректно отображаются в Grafana

### 📊 Новые возможности
- **Sparse векторы** - локальная генерация через BGE-M3 без внешнего сервиса
- **Управление коллекциями** - скрипты для полной замены и переиндексации
- **Проверка покрытия** - автоматическая верификация sparse векторов
- **Детальное тестирование** - comprehensive тесты для sparse поиска
- **Семантическое chunking** с перекрытием для лучшего контекста
- **Rate Limiting** с burst protection для предотвращения спама
- **Улучшенный Telegram адаптер** с красивым форматированием
- **Система безопасности** с оценкой риска и алертами
- **Детальные метрики** производительности и безопасности
- **Автоматическое восстановление** при сбоях
- **Graceful degradation** при ошибках
- **Полная валидация** входных данных
- **Кэширование** для ускорения ответов

Подробнее: [docs/critical_fixes.md](docs/critical_fixes.md)

## 🛠️ Разработка

### Структура проекта
```
├── adapters/           # Адаптеры каналов (Telegram, Web)
├── app/               # Core API (Flask)
│   ├── routes/        # API endpoints
│   ├── services/      # Бизнес-логика
│   ├── abstractions/  # Абстракции и плагины
│   └── sources/       # Источники данных
├── ingestion/         # Парсинг и индексация
├── tests/             # Автотесты
├── scripts/           # Утилиты и тесты
├── docs/             # Документация
├── .github/workflows/ # CI/CD
├── Makefile          # Команды разработки
└── pytest.ini       # Конфигурация тестов
```

### Настройка среды разработки

```bash
# Установка зависимостей для разработки
make dev-setup

# Запуск автотестов
make test-fast

# Проверка кода
make lint

# Форматирование
make format
```

### Добавление новых тестов

1. **Unit тесты** - в `tests/test_*.py`:
```python
def test_new_feature():
    """Тест новой функциональности"""
    # Ваш тест
    assert result == expected
```

2. **End-to-End тесты** - в `tests/test_end_to_end_pipeline.py`:
```python
def test_new_pipeline_step(self):
    """Тест нового этапа pipeline"""
    # Полный тест от извлечения до записи
```

3. **Маркировка тестов**:
```python
@pytest.mark.slow        # Медленные тесты
@pytest.mark.integration # Интеграционные тесты
@pytest.mark.unit        # Unit тесты
```

### Система плагинов

Добавление новых источников данных:

```python
@register_data_source("my_source")
class MyDataSource(DataSourceBase):
    def fetch_pages(self, max_pages: Optional[int] = None) -> CrawlResult:
        # Реализация извлечения данных
        pass

    def classify_page(self, page: Page) -> PageType:
        # Классификация страниц
        pass
```

### Добавление нового канала
1. Создайте адаптер в `adapters/`
2. Реализуйте интерфейс `ChannelAdapter`
3. Добавьте конфигурацию

### Добавление нового LLM
1. Добавьте функцию в `app/services/llm_router.py`
2. Обновите fallback порядок
3. Добавьте конфигурацию

## 🐛 Устранение неполадок

### Частые проблемы

#### Timeout ошибки
- Увеличьте `CRAWL_TIMEOUT_S`
- Проверьте доступность API

#### Ошибки форматирования
- Проверьте MarkdownV2 синтаксис
- Используйте fallback режим

#### Проблемы с эмбеддингами
- Проверьте доступность Ollama
- Убедитесь в правильности модели

#### Проблемы с мониторингом
- **Пустой Grafana**: Убедитесь, что RAG API запущен (`python wsgi.py`)
- **Метрики не отображаются**: Проверьте, что используется правильный порт (9002)
- **Конфликт портов**: Если метрики не работают, перезапустите RAG API

### Логи
```bash
# Просмотр логов Flask
tail -f logs/flask.log

# Просмотр логов Telegram бота
tail -f logs/telegram.log
```

## 📝 Лицензия

MIT License

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📞 Поддержка

### Документация
- **Основная документация**: [docs/](docs/)
- **Автотесты и CI/CD**: [docs/autotests_integration_report.md](docs/autotests_integration_report.md)
- **Phase 2 RAGAS Quality System**: [docs/phase2_ragas_quality_system.md](docs/phase2_ragas_quality_system.md)
- **API Документация**: [OpenAPI/Swagger](docs/api_documentation.md)
- **RAGAS Quality System (Legacy)**: [docs/ragas_quality_system.md](docs/ragas_quality_system.md)
- **GPU настройка (Linux)**: [ROCm](docs/gpu_setup.md)
- **GPU настройка (Windows)**: [DirectML](docs/gpu_setup_windows.md)

### Интерактивные инструменты
- **API документация**: http://localhost:9000/apidocs
- **Swagger UI**: http://localhost:9000/apidocs
- **Prometheus метрики**: http://localhost:9090
- **Grafana дашборды**: http://localhost:8080

### Тестирование и разработка
```bash
# Быстрая проверка системы
make test-fast

# Полная диагностика
pytest tests/test_end_to_end_pipeline.py -v

# Проверка сервисов
make check-services
```

### Контакты
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Email**: support@example.com

## 🎯 Roadmap

- [ ] Web интерфейс
- [ ] Поддержка других мессенджеров
- [ ] A/B тестирование ответов
- [ ] Аналитика использования
- [ ] Многоязычность
- [ ] Voice интерфейс
