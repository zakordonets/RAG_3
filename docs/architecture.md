## Архитектура RAG-ассистента для edna Chat Center

### Цели
- Ответы на вопросы пользователей о продукте edna Chat Center с использованием RAG.
- Поддержка нескольких интерфейсов (старт с Telegram; масштабирование на Web/Widget, email, внутренние панели).
- Гибридный поиск (dense + sparse) в Qdrant, RRF и ML-реранкинг (bge-reranker-v2-m3).
- Инкрементальная индексация HTML-портала `https://docs-chatcenter.edna.ru/` с сохранением структуры.
- Контроль качества чанков и метрик (retrieval + generation), с fallback логикой LLM.

### Высокоуровневые компоненты
1) Channel Adapters (внешние каналы)
   - Telegram Adapter (long polling): фоновый воркер получает апдейты и проксирует их в Core API/оркестратор.
   - Абстракция `ChannelAdapter` для будущих каналов: Web-виджет, edna API Bot Connect (email/WhatsApp — позже, без вложений на старте).

2) Core API (Flask)
   - REST эндпоинты:
     - `POST /v1/chat/query` — универсальный интерфейс запроса (для любых каналов, в т.ч. Telegram-поллинг воркер).
     - `POST /v1/admin/reindex` — ручной запуск инкрементального обновления (cron — позже).
   - Оркестровка пайплайна: Query Processing → Retrieval → Rerank → Generation → Postprocess.

3) Query Processing
   - Entity Extraction: выделение сущностей и терминов домена (разделы портала: «АРМ агента», «API» и т.п.).
   - Query Rewriting/Normalization: нормализация формы вопроса (синонимы, раскрытие сокращений).
   - Query Decomposition: пошаговая декомпозиция сложных вопросов (ограниченная глубина, например, max_depth=3).

4) Retrieval Layer
   - HybridRetriever для Qdrant:
     - Dense-векторы: BGE-M3 (через Ollama embedding API).
     - Sparse-векторы: BGE-M3 sparse (локальный сервис на FlagEmbedding). Хранение вместе с dense в Qdrant.
   - Fusion: RRF (Reciprocal Rank Fusion) поверх отдельных результатов dense и sparse.
   - Metadata-boost: учет `page_type` (API/FAQ/guide/release_notes), свежести `release_notes` и формы вопроса (вопросительные — boost FAQ).
   - Реранкинг (второй шаг): bge-reranker-v2-m3 по top-N (например, N=30 → топ-10).
   - Ресурсы: CPU-инференс (12 потоков, 48 GB RAM). Параллелизм ограничиваем по числу потоков.

5) Generation Layer
   - LLM Router:
     - Основные провайдеры: YandexGPT 5.1 Pro (дефолт), GPT-5 (быстрое переключение), Deepseek (fallback).
     - Fallback-логика: если недоступен YandexGPT — переключить на GPT-5; если и он недоступен — Deepseek.
   - Prompt Composer: формирование системного промпта с инструкциями, стилем и ограничениями на опору на контекст.
   - Iterative RAG (retrieve→generate→retrieve) для сложных запросов (ограничение глубины).
   - Правила ответов: один финальный ответ без streaming; включать цитаты-источники (URL) и списки; добавлять ссылку «Подробнее» на релевантную документацию; при отсутствии релевантного контекста — явно сообщать и запрашивать уточнение.

6) Ingestion & Indexing
   - HTML Crawler для `docs-chatcenter.edna.ru` (полное индексирование всего портала; карты сайта нет; без ограничений глубины/скорости).
   - Specialized Parsers:
     - API docs: извлечение endpoints/parameters/examples/responses.
     - Release Notes: version/features/fixes/breaking_changes + приоритизация свежих версий.
     - FAQ: извлечение QA-пар.
     - Guides/Manuals: заголовки, параграфы, таблицы, списки, ссылки и контекст изображений (alt/figcaption).
   - Chunker с Quality Gates:
     - Контроль min/max длины (в токенах), no-empty, deduplication (hash/SimHash/MinHash на нормализованном тексте).
     - Сохранение семантики заголовков (иерархия H1–H6) и таблиц.
   - Embedding Service:
     - Dense: Ollama (BGE-M3) → вектор.
     - Sparse: локальный сервис на `FlagEmbedding` (BGE-M3 sparse) → словарь {term: weight}.
   - Qdrant Writer:
     - Гибридная коллекция с полями: dense-вектор, sparse-вектор, payload.
     - Инкрементальность: сравнение хэшей контента/updated_at; upsert измененных чанков, удаление убывших. Запуск пока вручную (cron позже).
   - Визуальный прогресс: отображение хода краулинга и индексации (CLI прогресс-бар и/или простая страница статуса).

7) Storage (Qdrant)
   - Коллекция: `chatcenter_docs`
     - Dense vector size: соответствует BGE-M3 (как в модели).
     - Sparse vector: Qdrant sparse payload.
     - Payload (метаданные):
       - `url`, `title`, `breadcrumbs`, `section` (e.g., «АРМ агента»), `page_type` (api|faq|guide|release_notes),
       - `version` (для релиз-нот), `updated_at`, `hash`, `anchors`, `headings`, `images`, `links`.
       - `source` (docs-site), `language` (ru), `product` (edna Chat Center).
   - Индекс HNSW:
     - m=${QDRANT_HNSW_M}, ef_construct=${QDRANT_HNSW_EF_CONSTRUCT}, ef_search=${QDRANT_HNSW_EF_SEARCH}, full_scan_threshold=${QDRANT_HNSW_FULL_SCAN_THRESHOLD}.

8) Observability & Evaluation
   - **Comprehensive Error Handling**: Try-catch блоки для каждого этапа pipeline с graceful degradation
   - **Prometheus метрики**: Полный набор метрик для мониторинга производительности и ошибок
   - **Circuit Breaker**: Защита от каскадных сбоев внешних сервисов (LLM, эмбеддинги, Qdrant)
   - **Кэширование**: Redis + in-memory fallback для эмбеддингов и результатов поиска
   - **Валидация и санитизация**: Marshmallow схемы и защита от XSS/инъекций
   - Логи пайплайна (запрос, сущности, переформулировка, кандидаты, веса, оценки)
   - Метрики retrieval: Context Relevance, Context Coverage, Precision@K, Recall@K
   - Метрики generation: Answer Relevancy, Faithfulness, Completeness
   - Офлайн-оценка на golden set (когда появится) и онлайн-сигналы (user feedback, click-through на источники)
   - HTTP сервер метрик на порту 8000, admin endpoints для управления

### Логический поток запроса
1) **Channel Adapter** принимает сообщение → **Core API** `/v1/chat/query` с валидацией и санитизацией
2) **Query Processing**: извлечение сущностей и нормализация; при необходимости декомпозиция
3) **Embedding**: получение dense и sparse представлений запроса (с кэшированием)
4) **Retrieval**: параллельные dense и sparse запросы к Qdrant → RRF → metadata-boost → bge-reranker
5) **Generation**: выбор LLM по роутингу и fallback, формирование ответа на основе top-k контекста
6) **Postprocess**: формирование источников (список `url` + заголовки), сокращение/структурирование
7) **Delivery**: ответ через соответствующий Channel Adapter (Telegram)
8) **Мониторинг**: запись метрик, обработка ошибок, Circuit Breaker проверки

### Дизайн абстракций (упрощенные интерфейсы)
```python
# adapters/channel.py
class ChannelAdapter(Protocol):
    def send_message(self, chat_id: str, text: str) -> None: ...
    def send_rich_answer(self, chat_id: str, answer: dict) -> None: ...

# services/embeddings.py
def embed_dense(text: str) -> list[float]: ...  # via Ollama (BGE-M3)
def embed_sparse(text: str) -> dict[str, float]: ...  # via FlagEmbedding (BGE-M3 sparse)

# services/retrieval.py
def hybrid_search(query_dense: list[float], query_sparse: dict[str, float], k: int, boosts: dict) -> list[dict]: ...

# services/rerank.py
def rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]: ...  # bge-reranker-v2-m3

# services/llm_router.py
def generate_answer(query: str, context: list[dict], policy: dict) -> str: ...

# ingestion/pipeline.py
def crawl_and_index(incremental: bool = True) -> dict: ...
```

### Qdrant: схема коллекции и запросы
- Коллекция `chatcenter_docs`:
  - vectors: `dense: float32[dim]`
  - sparse: `sparse` (Qdrant sparse vector)
  - payload: поля метаданных

- Пример гибридного поиска (концептуально):
```python
client.search(collection_name,
    query_vector=("dense", dense_vec),
    query_sparse=SparseVector(indices, values),
    with_payload=True,
    limit=k,
    params={"hnsw_ef": EF_SEARCH})
```

### Конфигурация и окружение
- **ENV переменные** (полный список в `env.example`):
  - **Qdrant**: QDRANT_URL, QDRANT_API_KEY, QDRANT_HNSW_M, QDRANT_HNSW_EF_CONSTRUCT, QDRANT_HNSW_EF_SEARCH, QDRANT_HNSW_FULL_SCAN_THRESHOLD
  - **Эмбеддинги**: OLLAMA_URL, EMBEDDING_MODEL_TYPE=BGE-M3, EMBEDDING_MODEL_NAME=bge-m3:latest, SPARSE_SERVICE_URL, USE_SPARSE
  - **LLM провайдеры**: DEEPSEEK_API_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, YANDEX_API_URL, YANDEX_CATALOG_ID, YANDEX_API_KEY, YANDEX_MODEL, YANDEX_MAX_TOKENS, GPT5_API_URL, GPT5_API_KEY, GPT5_MODEL
  - **Telegram**: TELEGRAM_BOT_TOKEN, TELEGRAM_POLL_INTERVAL
  - **Кэширование**: REDIS_URL, CACHE_ENABLED
  - **Краулинг**: CRAWL_START_URL, CRAWL_CONCURRENCY, CRAWL_TIMEOUT_S, CRAWL_MAX_PAGES, CRAWL_DELAY_MS, CRAWL_JITTER_MS, CRAWL_STRATEGY
  - **Безопасность**: MAX_MESSAGE_LENGTH, ALLOWED_CHANNELS, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW

### ADR (ключевые решения)
1) **Qdrant** как единая база для dense+sparse → упрощение стека и гибридный поиск «из коробки»
2) **BGE-M3**: dense → SentenceTransformers (локально); sparse → локальный FlagEmbedding. Хранение обоих представлений в одной коллекции
3) **RRF + bge-reranker-v2-m3** (CPU, 12 потоков): старт равные веса (0.5/0.5), затем A/B-тест (например 0.6/0.4)
4) **Инкрементальная индексация** по hash/updated_at и дифф-стратегии; запуск вручную (cron позднее)
5) **Ограниченная глубина** пошагового RAG (max_depth=3) для контроля стоимости и латентности
6) **Comprehensive Error Handling**: Try-catch на каждом этапе с graceful degradation и fallback логикой
7) **Circuit Breaker Pattern**: Защита от каскадных сбоев внешних сервисов с автоматическим восстановлением
8) **Кэширование**: Redis + in-memory fallback для эмбеддингов и результатов поиска
9) **Валидация и санитизация**: Marshmallow схемы и защита от XSS/инъекций
10) **Prometheus метрики**: Полный мониторинг производительности, ошибок и состояния системы

### Масштабирование и производительность
- **Асинхронная индексация** и парсинг (пулы воркеров)
- **Кэширование**: Redis + in-memory fallback для эмбеддингов и результатов поиска
- **Семантическое chunking**: Улучшенное разбиение текста на основе сходства
- **Батчевое вычисление** эмбеддингов с перекрытием
- **Настройка HNSW** параметров под объём (из ENV)
- **Горизонтальное масштабирование** Core API за счёт stateless дизайна
- **Circuit Breaker** для защиты от перегрузки внешних сервисов
- **Rate Limiting** для защиты от злоупотреблений
- **Метрики производительности** для оптимизации и мониторинга
- **Graceful degradation** при сбоях компонентов

### Безопасность и приватность
- **Конфигурация**: Ключи и конфиги в `.env` (добавлен в `.gitignore`), примеры — в `env.example` без секретов
- **Валидация входных данных**: Marshmallow схемы для всех API endpoints
- **Санитизация**: HTML экранирование и защита от XSS/инъекций
- **Ограничения**: Максимальная длина сообщений, разрешенные каналы
- **Rate Limiting**: Защита от злоупотреблений с burst protection
- **Система безопасности**: Мониторинг подозрительной активности и блокировка пользователей
- **Оценка риска**: Автоматическая оценка риска для каждого пользователя
- **Логирование**: Детальное логирование для аудита и отладки
- **Мониторинг**: Отслеживание подозрительной активности через метрики
- **Алерты**: Автоматические уведомления о критических событиях
- При расширении каналов — переоценка требований безопасности

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

#### Rate Limiting
- **`GET /v1/admin/rate-limiter`** — состояние Rate Limiter
- **`GET /v1/admin/rate-limiter/<user_id>`** — состояние пользователя
- **`POST /v1/admin/rate-limiter/<user_id>/reset`** — сброс лимитов

#### Безопасность
- **`GET /v1/admin/security`** — статистика безопасности
- **`GET /v1/admin/security/user/<user_id>`** — состояние пользователя
- **`POST /v1/admin/security/user/<user_id>/block`** — блокировка пользователя

#### Метрики Prometheus
- **`rag_queries_total`** — количество запросов по каналам и статусам
- **`rag_query_duration_seconds`** — длительность этапов обработки
- **`rag_embedding_duration_seconds`** — время создания эмбеддингов
- **`rag_search_duration_seconds`** — время поиска
- **`rag_llm_duration_seconds`** — время генерации LLM
- **`rag_cache_hits_total`** — попадания в кэш
- **`rag_errors_total`** — ошибки по типам и компонентам

### Будущие интерфейсы
- Реализация дополнительных `ChannelAdapter`: Web-виджет и edna API Bot Connect (двусторонние вложения не требуются на старте)
- Единый `/v1/chat/query` остаётся стабильным контрактом
