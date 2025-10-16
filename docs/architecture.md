## Архитектура RAG-ассистента для edna Chat Center

### Цели
- Ответы на вопросы пользователей о продукте edna Chat Center с использованием RAG.
- Поддержка нескольких интерфейсов (старт с Telegram; масштабирование на Web/Widget, email, внутренние панели).
- Гибридный поиск (dense + sparse) в Qdrant, RRF и ML-реранкинг (bge-reranker-v2-m3).
- Инкрементальная индексация HTML-портала `https://docs-chatcenter.edna.ru/` с сохранением структуры.
- Контроль качества чанков и метрик (retrieval + generation), с fallback логикой LLM.

### 🎉 Текущая версия: v4.3.0 (2025-10-08)

**Критические исправления и улучшения:**
- 🔧 **Исправлено дублирование текста** - удалено поле `chunk_text`, размер индекса уменьшен ~в 2 раза
- ⚙️ **Исправлены параметры чанкинга** - настройки из `.env` теперь применяются корректно (CHUNK_MIN/MAX_TOKENS)
- 🔗 **Исправлена обработка ContentRef** - сохранены семантические связи между документами Docusaurus
- 📊 **Улучшено логирование** - прогресс индексации отображается в формате X/Y (Z%)
- 🐳 **Восстановлен Redis** - контейнер `rag-redis` запущен и работает

**Предыдущие достижения (v4.2.0):**
- 🔧 **Критические исправления QdrantWriter** - sparse векторы вынесены в отдельный параметр
- 🎯 **Корректный гибридный поиск** - dense + sparse с RRF fusion работает как задумано
- 🛡️ **Надежность и стабильность** - ретраи, валидация, защита от ошибок
- 📊 **Расширенные индексы** - doc_id, heading_path для удобной фильтрации
- 🔍 **Улучшенный retrieval** - фильтрация по категориям, увеличенный recall
- 🏗️ **Автоматическое создание коллекций** - ensure_collection() с гибридной схемой

### Высокоуровневые компоненты

#### 1) Channel Adapters (внешние каналы)
- **Telegram Adapter** (long polling): фоновый воркер получает апдейты и проксирует их в Core API/оркестратор.
  - Красивое HTML-форматирование ответов
  - Автоматическое разбиение длинных сообщений
  - Inline кнопки для оценки качества ответов
  - Санитизация HTML для безопасности
- **Абстракция ChannelAdapter**: готовность к Web-виджет, edna API Bot Connect (email/WhatsApp — позже, без вложений на старте).

#### 2) Core API (Flask)
- **REST эндпоинты**:
  - `POST /v1/chat/query` — универсальный интерфейс запроса (для любых каналов)
  - `POST /v1/admin/reindex` — ручной запуск инкрементального обновления
  - `GET /v1/admin/health` — проверка состояния системы с Circuit Breakers
  - `GET /v1/admin/metrics` — метрики Prometheus
  - `GET /apidocs` — Swagger UI для интерактивного тестирования
- **Оркестровка пайплайна**: Query Processing → Retrieval → Rerank → Generation → Postprocess
- **Валидация и безопасность**: Marshmallow схемы, санитизация входных данных, rate limiting

#### 3) Ingestion Pipeline (ЕДИНАЯ АРХИТЕКТУРА DAG) ⭐

**Основной прорыв v4.1.0+:** Создана единая архитектура индексации с одним DAG вместо трех параллельных конвейеров.

**Единый entrypoint** (`ingestion/run.py`):
- Поддержка всех источников данных через адаптеры
- Унифицированный DAG: Parse → Normalize → Chunk → Embed → Index
- Конфигурация через YAML и CLI аргументы
- Инкрементальная индексация с StateManager

**Source Adapters** (`ingestion/adapters/`):
- `DocusaurusAdapter` - для файловой системы Docusaurus
- `WebsiteAdapter` - для веб-сайтов (HTTP/HTML)
- Единый интерфейс `SourceAdapter` для всех источников
- Автоматическое извлечение метаданных и URL

**Pipeline Steps** (`ingestion/pipeline/`):
- `Parser` - универсальный парсер (Markdown/HTML)
- `DocusaurusNormalizer` - специфичная нормализация Docusaurus
- `URLMapper` - преобразование путей в URL
- `HtmlNormalizer` - нормализация HTML контента
- `UnifiedChunkerStep` - интеллектуальное чанкование с поддержкой структуры документа
- `Embedder` - генерация dense и sparse векторов
- `QdrantWriter` - запись в векторную базу данных

**State Management** (`ingestion/state/`):
- `StateManager` - единое управление состоянием документов
- Отслеживание изменений по hash и mtime
- Инкрементальная индексация для всех источников

**Normalizers** (`ingestion/normalizers/`):
- Плагины нормализации для разных типов контента
- Очистка JSX, импортов, admonitions для Docusaurus
- Извлечение контента из HTML
- Обработка ContentRef ссылок (преобразование в текст с URL)

**Chunker** (`ingestion/chunking/`):
- `UniversalChunker` - структурно-осознанный чанкинг
- Оптимальное разбиение: 150-300 токенов (настраивается через CHUNK_MIN/MAX_TOKENS)
- Сохранение целостности параграфов
- Автоматический выбор между семантическим и простым чанкингом
- Контроль min/max длины, deduplication
- Сохранение семантики заголовков (иерархия H1–H6) и таблиц

**Embedding Service** (`app/services/core/embeddings.py`):
- Dense: BGE-M3 через ONNX с DirectML (GPU ускорение) → вектор 1024 измерений
- Sparse: BGE-M3 sparse (локальная генерация на CPU) → словарь {term: weight}
- Кэширование через Redis с in-memory fallback

**Qdrant Writer** (`ingestion/pipeline/indexers/qdrant_writer.py`):
- Гибридная коллекция с named vectors: dense-вектор, sparse-вектор, payload
- Автоматическое создание коллекции с правильной схемой (ensure_collection)
- **Критические исправления**: sparse векторы в отдельном параметре sparse_vectors
- **Оптимизация payload**: удалено дублирование текста (chunk_text)
- Расширенные индексы: doc_id, heading_path для фильтрации
- Надежность: ретраи, валидация размерности, защита от numpy типов
- Инкрементальность: сравнение хэшей контента/updated_at; upsert измененных чанков

#### 4) Query Processing
- **Entity Extraction**: выделение сущностей и терминов домена (разделы портала: «АРМ агента», «API» и т.п.)
- **Query Rewriting/Normalization**: нормализация формы вопроса (синонимы, раскрытие сокращений)
- **Query Decomposition**: пошаговая декомпозиция сложных вопросов (ограниченная глубина, max_depth=3)

#### 5) Retrieval Layer

**HybridRetriever для Qdrant**:
- **Dense-векторы**: BGE-M3 через ONNX с DirectML (GPU ускорение) или CPU fallback
- **Sparse-векторы**: BGE-M3 sparse (локальная генерация через BGE-M3 на CPU)
- **Хранение**: вместе с dense в Qdrant как named vectors
- **Fusion**: RRF (Reciprocal Rank Fusion) поверх отдельных результатов dense и sparse
- **Metadata-boost**: учет `page_type` (API/FAQ/guide/release_notes), свежести и формы вопроса

**Реранкинг**:
- bge-reranker-v2-m3 по top-N (например, N=30 → топ-10)

**Auto-Merge** (v4.3.0):
- Автоматическое объединение соседних чанков одного документа после rerank
- Интеллектуальное расширение контекстных окон в рамках token budget
- TTL-кеширование документов (maxsize=1000, ttl=300s)
- Точная оценка токенов через tiktoken (fallback: эвристика len//4)
- Динамическая адаптация под context optimizer
- Метаданные слияния: auto_merged, merged_chunk_indices, chunk_span
- Документация: [AUTO_MERGE.md](./AUTO_MERGE.md)

**Context Optimizer**:
- Специальный режим для списочных запросов
- Извлечение конкретных разделов Markdown
- Сохранение структуры (списки, заголовки, форматирование)
- Приоритет релевантным разделам, а не началу документа

**Ресурсы**: Hybrid CPU+GPU инференс (DirectML для dense, CPU для sparse, 12 потоков, 48 GB RAM)

#### 6) Generation Layer

**LLM Router**:
- **Основные провайдеры**:
  - YandexGPT RC (yandexgpt/rc) - дефолт
  - GPT-5 - быстрое переключение
  - Deepseek - fallback
- **Fallback-логика**: если недоступен YandexGPT → переключить на GPT-5; если и он недоступен → Deepseek
- **Circuit Breaker**: защита от каскадных сбоев с автоматическим восстановлением

**Prompt Composer**:
- Формирование системного промпта с инструкциями, стилем и ограничениями
- Опора на контекст из retrieval

**Iterative RAG**:
- retrieve→generate→retrieve для сложных запросов (ограничение глубины)

**Правила ответов**:
- Один финальный ответ без streaming
- Включать цитаты-источники (URL) и списки
- Добавлять ссылку «Подробнее» на релевантную документацию
- При отсутствии релевантного контекста — явно сообщать и запрашивать уточнение

#### 7) Storage (Qdrant)

**Коллекция**: `chatcenter_docs`
- **Named vectors**:
  - `dense` (1024 измерения, float32)
  - `sparse` (SparseVectorParams)
- **100% покрытие** sparse векторами с корректной архитектурой

**Payload (метаданные)**:
- `url`, `title`, `breadcrumbs`, `section` (e.g., «АРМ агента»)
- `page_type` (api|faq|guide|release_notes)
- `version` (для релиз-нот), `updated_at`, `hash`
- `anchors`, `headings`, `images`, `links`
- `source` (docs-site), `language` (ru), `product` (edna Chat Center)
- `doc_id`, `heading_path` - индексы для удобной фильтрации
- `text` - текст чанка (оптимизировано: без дублирования в chunk_text)

**Индекс HNSW**:
- m=${QDRANT_HNSW_M}
- ef_construct=${QDRANT_HNSW_EF_CONSTRUCT}
- ef_search=${QDRANT_HNSW_EF_SEARCH}
- full_scan_threshold=${QDRANT_HNSW_FULL_SCAN_THRESHOLD}

#### 8) Observability & Evaluation

**Error Handling & Resilience**:
- **Comprehensive Error Handling**: Try-catch блоки для каждого этапа pipeline с graceful degradation
- **Circuit Breaker**: Защита от каскадных сбоев внешних сервисов (LLM, эмбеддинги, Qdrant)
- **Кэширование**: Redis + in-memory fallback для эмбеддингов и результатов поиска
- **Валидация и санитизация**: Marshmallow схемы и защита от XSS/инъекций
- **Rate Limiting**: Защита от злоупотреблений с burst protection

**Monitoring & Metrics**:
- **Prometheus метрики**: Полный набор метрик для мониторинга производительности и ошибок
- **HTTP сервер метрик** на порту 9001 для экспорта в формате Prometheus
- **Grafana dashboard** "RAG System Overview" с ключевыми метриками
- **Admin endpoints** для управления и мониторинга

**Quality System (RAGAS)**:
- **Метрики retrieval**: Context Relevance, Context Coverage, Precision@K, Recall@K
- **Метрики generation**: Answer Relevancy, Faithfulness, Completeness
- **Пользовательский фидбек**: Inline кнопки в Telegram для оценки ответов
- **Quality Analytics**: REST API для анализа качества и трендов
- **Офлайн-оценка** на golden set и онлайн-сигналы (user feedback, click-through на источники)

**Logging**:
- Логи пайплайна (запрос, сущности, переформулировка, кандидаты, веса, оценки)
- Детальное логирование для аудита и отладки

### Логический поток запроса

1. **Channel Adapter** принимает сообщение → **Core API** `/v1/chat/query` с валидацией и санитизацией
2. **Query Processing**: извлечение сущностей и нормализация; при необходимости декомпозиция
3. **Embedding**: получение dense и sparse представлений запроса (с кэшированием)
4. **Retrieval**: параллельные dense и sparse запросы к Qdrant → RRF → metadata-boost → bge-reranker
5. **Auto-Merge**: объединение соседних чанков одного документа для расширения контекста
6. **Context Optimization**: оптимизация контекста для списочных запросов и извлечение релевантных разделов
7. **Generation**: выбор LLM по роутингу и fallback, формирование ответа на основе top-k контекста
8. **Postprocess**: формирование источников (список `url` + заголовки), сокращение/структурирование
9. **Delivery**: ответ через соответствующий Channel Adapter (Telegram)
10. **Мониторинг**: запись метрик, обработка ошибок, Circuit Breaker проверки
11. **Quality Feedback**: пользователь может оценить ответ, данные сохраняются для аналитики

### Дизайн абстракций (упрощенные интерфейсы)

```python
# adapters/channel.py
class ChannelAdapter(Protocol):
    def send_message(self, chat_id: str, text: str) -> None: ...
    def send_rich_answer(self, chat_id: str, answer: dict) -> None: ...

# app/services/core/embeddings.py
def embed_dense(text: str) -> list[float]: ...  # BGE-M3 via ONNX
def embed_sparse(text: str) -> dict[str, float]: ...  # BGE-M3 sparse

# app/services/search/retrieval.py
def hybrid_search(query_dense: list[float], query_sparse: dict[str, float], k: int, boosts: dict) -> list[dict]: ...

# app/services/search/rerank.py
def rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]: ...  # bge-reranker-v2-m3

# app/services/core/llm_router.py
def generate_answer(query: str, context: list[dict], policy: dict) -> str: ...

# ingestion/run.py
def run_ingestion(source: str, config: dict) -> dict: ...
```

### Рабочие секции и групповой бустинг

Для поддержания релевантной выдачи используется набор секционных метаданных,
собранных из `_category_.json` Docusaurus (`group_labels`, `groups_path`).
Конфигурация этих разделов задаётся через переменную `GROUP_BOOST_SYNONYMS`
(JSON), что позволяет адаптировать систему под другие проекты без правки кода.

Использование:
- Query Processing выделяет `group_boosts` по ключевым словам запроса.
- Hybrid Search повышает вес документов, чьи `groups_path` содержит
  соответствующие секции (например, "АРМ администратора", "API").
- В ответе ассистента источники отображаются с пометкой раздела, чтобы
  пользователю было легче ориентироваться.

### Qdrant: схема коллекции и запросы

**Коллекция** `chatcenter_docs`:
- Named vectors: `dense: float32[1024]`, `sparse: SparseVector`
- Payload: поля метаданных
- 100% покрытие sparse векторами

**Пример гибридного поиска** (концептуально):
```python
client.search(
    collection_name="chatcenter_docs",
    query_vector=("dense", dense_vec),
    query_sparse=SparseVector(indices, values),
    with_payload=True,
    limit=k,
    params={"hnsw_ef": EF_SEARCH}
)
```

### Конфигурация и окружение

**ENV переменные** (полный список в `env.example`):

**Qdrant**:
- QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
- QDRANT_HNSW_M, QDRANT_HNSW_EF_CONSTRUCT, QDRANT_HNSW_EF_SEARCH, QDRANT_HNSW_FULL_SCAN_THRESHOLD

**Эмбеддинги**:
- EMBEDDINGS_BACKEND=auto, EMBEDDING_DEVICE=auto, USE_SPARSE=true
- BGE_MODEL_NAME, BGE_ONNX_MODEL_PATH, BGE_EMBEDDING_DIM

**Чанкинг**:
- CHUNK_MIN_TOKENS=150, CHUNK_MAX_TOKENS=300 (настраивается)
- CHUNK_OVERLAP_BASE=100

**LLM провайдеры**:
- DEEPSEEK_API_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL
- YANDEX_API_URL, YANDEX_CATALOG_ID, YANDEX_API_KEY, YANDEX_MODEL, YANDEX_MAX_TOKENS
- GPT5_API_URL, GPT5_API_KEY, GPT5_MODEL

**Telegram**:
- TELEGRAM_BOT_TOKEN, TELEGRAM_POLL_INTERVAL

**Кэширование**:
- REDIS_URL, CACHE_ENABLED, CACHE_TTL

**Индексация**:
- DOCS_ROOT_PATH (путь к документации Docusaurus)
- SITE_BASE_URL (базовый URL сайта)
- SITE_DOCS_PREFIX (префикс для документов)

**Безопасность**:
- MAX_MESSAGE_LENGTH, ALLOWED_CHANNELS
- RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW

### ADR (ключевые архитектурные решения)

1. **Qdrant** как единая база для dense+sparse → упрощение стека и гибридный поиск «из коробки»
2. **BGE-M3**: dense → ONNX с DirectML (GPU ускорение); sparse → локальная генерация через BGE-M3 на CPU
3. **RRF + bge-reranker-v2-m3** (Hybrid CPU+GPU, 12 потоков): равные веса (0.5/0.5), с возможностью A/B-теста
4. **Единая DAG архитектура** индексации вместо трех параллельных конвейеров → упрощение поддержки
5. **Инкрементальная индексация** по hash/updated_at с кешированием → быстрые обновления
6. **Ограниченная глубина** пошагового RAG (max_depth=3) → контроль стоимости и латентности
7. **Comprehensive Error Handling**: Try-catch на каждом этапе с graceful degradation
8. **Circuit Breaker Pattern**: Защита от каскадных сбоев с автоматическим восстановлением
9. **Кэширование**: Redis + in-memory fallback → высокая производительность
10. **Валидация и санитизация**: Marshmallow схемы → защита от уязвимостей
11. **Prometheus метрики**: Полный мониторинг производительности и состояния
12. **Sparse векторы**: Полная замена коллекции с 100% покрытием
13. **Оптимальный чанкинг**: 150-300 токенов с сохранением целостности параграфов
14. **Единый модуль индексации**: Замена множества скриптов одним production-ready модулем
15. **Оптимизация payload**: Удаление дублирования текста → уменьшение размера индекса в 2 раза

### API Endpoints

#### Основные endpoints
- **`POST /v1/chat/query`** — универсальный интерфейс запроса с валидацией и санитизацией
- **`POST /v1/admin/reindex`** — ручной запуск инкрементального обновления

#### API Документация
- **`GET /apidocs`** — Swagger UI для интерактивного тестирования API
- **`GET /apispec_1.json`** — OpenAPI 2.0 спецификация в JSON формате

#### Мониторинг и администрирование
- **`GET /v1/admin/health`** — проверка состояния системы с Circuit Breakers и кэшем
- **`GET /v1/admin/metrics`** — метрики Prometheus в JSON формате
- **`GET /v1/admin/metrics/raw`** — сырые метрики Prometheus для мониторинга
- **`GET /v1/admin/circuit-breakers`** — состояние Circuit Breakers
- **`POST /v1/admin/circuit-breakers/reset`** — сброс Circuit Breakers
- **`GET /v1/admin/cache`** — статистика кэша
- **`POST /v1/admin/metrics/reset`** — сброс метрик (только для тестирования)

#### Система мониторинга
- **Prometheus** (порт 9090) — сбор метрик с RAG API
- **Grafana** (порт 8080) — визуализация метрик и дашборды
- **HTTP сервер метрик** (порт 9001) — экспорт метрик в формате Prometheus
- **Готовый дашборд** "RAG System Overview" с ключевыми метриками
- **Автоматическая конфигурация** через Docker Compose

#### Rate Limiting
- **`GET /v1/admin/rate-limiter`** — состояние Rate Limiter
- **`GET /v1/admin/rate-limiter/<user_id>`** — состояние пользователя
- **`POST /v1/admin/rate-limiter/<user_id>/reset`** — сброс лимитов

#### Безопасность
- **`GET /v1/admin/security`** — статистика безопасности
- **`GET /v1/admin/security/user/<user_id>`** — состояние пользователя
- **`POST /v1/admin/security/user/<user_id>/block`** — блокировка пользователя

#### Quality System
- **`POST /v1/admin/quality/feedback`** — сохранение пользовательского фидбека
- **`GET /v1/quality/analytics`** — аналитика качества ответов
- **`GET /v1/quality/trends`** — тренды качества

#### Метрики Prometheus
- **`rag_queries_total`** — количество запросов по каналам и статусам
- **`rag_query_duration_seconds`** — длительность этапов обработки
- **`rag_embedding_duration_seconds`** — время создания эмбеддингов
- **`rag_search_duration_seconds`** — время поиска
- **`rag_llm_duration_seconds`** — время генерации LLM
- **`rag_cache_hits_total`** — попадания в кэш
- **`rag_errors_total`** — ошибки по типам и компонентам
- **`rag_quality_score`** — оценки качества ответов

### Структура проекта (v4.3.0)

```
RAG_clean/
├── ingestion/                    # 🏗️ Единая архитектура индексации
│   ├── adapters/                 # 🔌 Адаптеры источников данных
│   │   ├── base.py              # Базовые интерфейсы (SourceAdapter, PipelineStep)
│   │   ├── docusaurus.py        # Адаптер для Docusaurus файловой системы
│   │   └── website.py           # Адаптер для веб-сайтов
│   ├── normalizers/              # 🧹 Плагины нормализации
│   │   ├── base.py              # Базовые нормализаторы
│   │   ├── docusaurus.py        # Docusaurus-специфичная нормализация
│   │   └── html.py              # HTML нормализация
│   ├── pipeline/                 # 🧩 Шаги пайплайна
│   │   ├── dag.py               # Единый DAG пайплайн
│   │   ├── chunker.py           # Шаг чанкинга
│   │   ├── embedder.py          # Шаг эмбеддингов
│   │   └── indexers/
│   │       └── qdrant_writer.py # Единый писатель в Qdrant
│   ├── state/                    # 📊 Управление состоянием
│   │   └── state_manager.py     # Единый менеджер состояния
│   ├── utils/                    # 📦 Утилиты
│   │   └── docusaurus_utils.py  # Объединенные утилиты Docusaurus
│   ├── crawlers/                 # 🕷️ Краулеры
│   │   └── docusaurus_fs_crawler.py # Файловый краулер Docusaurus
│   ├── chunking/                 # 🧩 Чанкинг
│   │   └── universal_chunker.py # Универсальный чанкер
│   ├── run.py                    # 🚀 Единый entrypoint
│   ├── indexer.py               # 📦 Простой индексер (совместимость)
│   └── config.yaml              # ⚙️ Конфигурация
├── app/                          # 🏗️ Основное приложение
│   ├── services/                 # 🔧 Сервисы
│   │   ├── core/                # Основные сервисы (embeddings, llm_router, query_processing, context_optimizer)
│   │   ├── search/              # Поиск (retrieval, rerank)
│   │   ├── quality/             # Контроль качества (quality_manager, ragas_evaluator)
│   │   └── infrastructure/      # Инфраструктурные сервисы (orchestrator, connection_pool)
│   ├── routes/                   # 🛣️ API маршруты
│   │   ├── chat.py              # Чат endpoints
│   │   ├── admin.py             # Админ endpoints
│   │   └── quality.py           # Quality endpoints
│   ├── models/                   # 📊 Модели данных
│   ├── config/                   # ⚙️ Конфигурация
│   ├── validation.py            # Валидация входных данных
│   ├── caching.py               # Кэширование
│   ├── circuit_breaker.py       # Circuit Breaker
│   └── metrics.py               # Prometheus метрики
├── adapters/                     # 🔌 Channel Adapters
│   └── telegram/                # Telegram адаптер
│       ├── telegram_adapter.py  # Основной адаптер
│       └── html_renderer.py     # HTML рендеринг
├── tests/                        # 🧪 Тесты
│   ├── test_unified_*           # Тесты единой архитектуры
│   ├── test_docusaurus_*        # Тесты Docusaurus компонентов
│   └── services/                # Тесты сервисов
├── scripts/                      # 📜 Утилитные скрипты
├── docs/                        # 📚 Документация
├── k8s/                         # ☸️ Kubernetes манифесты
├── monitoring/                  # 📊 Конфигурация мониторинга
│   ├── prometheus.yml           # Конфигурация Prometheus
│   └── grafana/                 # Grafana дашборды
├── docker-compose.yml           # 🐳 Docker Compose конфигурация
├── requirements.txt             # 📦 Python зависимости
├── .env.example                 # 🔧 Пример конфигурации
└── README.md                    # 📖 Главная документация
```

### Использование

#### Запуск индексации (Docusaurus)

```bash
# Полная индексация с очисткой коллекции
python ingestion/run.py docusaurus \
    --docs-root docs \
    --reindex-mode full \
    --clear-collection

# Инкрементальная индексация
python ingestion/run.py docusaurus \
    --docs-root docs \
    --reindex-mode incremental

# С кастомными параметрами чанкинга
python ingestion/run.py docusaurus \
    --docs-root docs \
    --chunk-min-tokens 150 \
    --chunk-max-tokens 300 \
    --reindex-mode full
```

#### Запуск индексации (Website)

```bash
python ingestion/run.py website \
    --seed-urls "https://example.com" \
    --max-depth 3 \
    --reindex-mode full
```

#### Запуск через API

```bash
# Полная переиндексация
curl -X POST http://localhost:5001/admin/reindex \
     -H "Content-Type: application/json" \
     -d '{"force_full": true}'

# Инкрементальная переиндексация
curl -X POST http://localhost:5001/admin/reindex \
     -H "Content-Type: application/json" \
     -d '{"incremental": true}'
```

### Масштабирование и производительность

- **Асинхронная индексация** и парсинг (пулы воркеров)
- **Кэширование**: Redis + in-memory fallback для эмбеддингов и результатов поиска
- **Структурный chunking**: Улучшенное разбиение текста с учетом заголовков и структуры
- **Батчевое вычисление** эмбеддингов
- **Настройка HNSW** параметров под объём (из ENV)
- **Горизонтальное масштабирование** Core API за счёт stateless дизайна
- **Circuit Breaker** для защиты от перегрузки внешних сервисов
- **Rate Limiting** для защиты от злоупотреблений
- **Метрики производительности** для оптимизации и мониторинга
- **Graceful degradation** при сбоях компонентов
- **Оптимизация payload**: удаление дублирования → уменьшение размера индекса в 2 раза

### Безопасность и приватность

- **Конфигурация**: Ключи и конфиги в `.env` (добавлен в `.gitignore`), примеры в `env.example`
- **Валидация входных данных**: Marshmallow схемы для всех API endpoints
- **Санитизация**: HTML экранирование и защита от XSS/инъекций
- **Ограничения**: Максимальная длина сообщений, разрешенные каналы
- **Rate Limiting**: Защита от злоупотреблений с burst protection
- **Система безопасности**: Мониторинг подозрительной активности и блокировка пользователей
- **Оценка риска**: Автоматическая оценка риска для каждого пользователя
- **Логирование**: Детальное логирование для аудита и отладки
- **Мониторинг**: Отслеживание подозрительной активности через метрики
- **Алерты**: Автоматические уведомления о критических событиях

### Будущие направления

- Реализация дополнительных `ChannelAdapter`: Web-виджет и edna API Bot Connect
- Единый `/v1/chat/query` остаётся стабильным контрактом
- Расширение источников данных (API документации, блоги, FAQ)
- Улучшение Quality System с ML-моделями для предсказания качества
- A/B тестирование различных стратегий retrieval и generation
