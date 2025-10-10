# Внутреннее API - Документация для разработчиков

## 📚 Обзор

Данная документация описывает внутреннюю архитектуру и API компонентов RAG-системы для разработчиков, работающих с кодовой базой.

**Целевая аудитория**: backend разработчики, контрибьюторы, системные архитекторы

**Версия**: 4.3.0
**Дата**: Октябрь 2025

---

## 🏗️ Архитектура

### Общая структура

```
app/
├── routes/          # Flask blueprints (публичное API)
├── services/        # Бизнес-логика (внутреннее API)
│   ├── core/        # Основные сервисы
│   ├── search/      # Поиск и retrieval
│   ├── quality/     # Система качества
│   └── infrastructure/  # Оркестрация
├── models/          # Модели данных
├── infrastructure/  # Circuit breakers, кэш, метрики
└── utils/           # Утилиты
```

---

## 🔧 Core Services

### 1. Query Processing (`app/services/core/query_processing.py`)

Препроцессинг пользовательских запросов перед эмбеддингом.

#### `process_query(text: str) -> Dict[str, Any]`

Основная функция обработки запроса.

**Параметры**:
- `text` (str): Исходный текст запроса пользователя

**Возвращает**:
```python
{
    "normalized_text": str,      # Нормализованный запрос для эмбеддинга
    "entities": List[str],        # Извлеченные доменные сущности
    "boosts": Dict[str, float],   # Boosts для поиска по метаданным
    "subqueries": List[str]       # Декомпозированные подзапросы (если есть)
}
```

**Пример использования**:
```python
from app.services.core.query_processing import process_query

result = process_query("Как настроить арм агента?")
# {
#     'normalized_text': 'Как настроить АРМ агента?',
#     'entities': ['арм агента'],
#     'boosts': {'user_role:agent': 1.3},
#     'subqueries': []
# }
```

**Внутренние функции**:

##### `extract_entities(text: str) -> List[str]`
Извлечение доменных терминов (арм агента, api, faq, etc.)

##### `rewrite_query(text: str) -> str`
Нормализация аббревиатур и терминов
- АРМ агента → АРМ агента (uppercase)
- api → API
- faq → FAQ

##### `maybe_decompose(text: str, max_depth: int = 3) -> List[str]`
Попытка разбить сложный запрос на подзапросы

---

### 2. Embeddings Service (`app/services/core/embeddings.py`)

Генерация эмбеддингов через BGE-M3 модель (dense + sparse).

#### `embed_unified(text: str, ...) -> Dict[str, Any]`

Унифицированная генерация всех типов эмбеддингов.

**Параметры**:
- `text` (str): Входной текст
- `max_length` (Optional[int]): Макс. длина в токенах (None = auto)
- `return_dense` (bool): Генерировать dense векторы (default: True)
- `return_sparse` (bool): Генерировать sparse векторы (default: True)
- `return_colbert` (bool): Генерировать ColBERT векторы (default: False)
- `context` (str): Контекст ("query" или "document")

**Возвращает**:
```python
{
    "dense_vecs": List[float],              # [1024] dense embedding
    "lexical_weights": Dict[str, float],    # {token: weight} sparse
    "colbert_vecs": Optional[List[List[float]]]  # token-level embeddings
}
```

**Пример использования**:
```python
from app.services.core.embeddings import embed_unified

result = embed_unified(
    text="Как настроить маршрутизацию?",
    context="query",
    return_dense=True,
    return_sparse=True
)

dense_vector = result["dense_vecs"]  # [1024] размерность
sparse_dict = result["lexical_weights"]  # {"настроить": 0.8, ...}
```

**Кэширование**:
- Использует декоратор `@cache_embedding(ttl=3600)`
- TTL: 1 час для query, 24 часа для document
- Кэш: Redis (если доступен) или in-memory

**Бэкенды**:
1. **ONNX** - оптимизированная версия для CPU
2. **BGE** - полная версия PyTorch
3. **Hybrid** - автоматический выбор

---

### 3. LLM Router (`app/services/core/llm_router.py`)

Маршрутизация запросов к LLM провайдерам с fallback.

#### `generate_answer(query: str, context: List[Dict], policy: Optional[Dict] = None) -> Dict[str, Any]`

Генерация ответа с использованием контекста.

**Параметры**:
- `query` (str): Вопрос пользователя
- `context` (List[Dict]): Найденные документы из Qdrant
- `policy` (Optional[Dict]): Настройки генерации (temperature, top_p)

**Возвращает**:
```python
{
    "answer_text": str,              # Ответ в plain text (deprecated)
    "answer_markdown": str,          # Ответ в Markdown формате
    "sources": List[Dict],           # Whitelisted источники
    "meta": {
        "llm_provider": str,         # Использованный провайдер
        "model": str,                # Модель
        "total_tokens": int          # Количество токенов
    }
}
```

**Поддерживаемые провайдеры** (с fallback):
1. **YandexGPT** (по умолчанию) - `yandexgpt/rc`
2. **GPT-4** (fallback #1) - через Azure OpenAI
3. **DeepSeek** (fallback #2) - бюджетная альтернатива

**Особенности**:
- **List intent detection**: автоматически определяет запросы на перечисление
- **Source whitelisting**: фильтрация источников по URL паттернам
- **Markdown sanitization**: чистка вывода от непредвиденных ссылок
- **Circuit breaker**: автоматический fallback при недоступности

**Пример использования**:
```python
from app.services.core.llm_router import generate_answer

documents = [
    {"text": "Для настройки...", "url": "https://docs...", "title": "..."},
    ...
]

result = generate_answer(
    query="Как настроить маршрутизацию?",
    context=documents,
    policy={"temperature": 0.3}
)

print(result["answer_markdown"])
print(result["meta"]["llm_provider"])  # "yandex"
```

---

### 4. Context Optimizer (`app/services/core/context_optimizer.py`)

Оптимизация и дедупликация контекста для LLM.

#### `class ContextOptimizer`

##### `optimize_context(query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]`

Оптимизация контекста перед передачей в LLM.

**Выполняет**:
1. **Дедупликация** - удаление дублирующихся чанков (по URL + позиции)
2. **Auto-merge** - объединение соседних чанков одного документа
3. **Ranking** - сортировка по релевантности
4. **Trimming** - обрезка по лимиту токенов

**Параметры**:
- `query` (str): Запрос пользователя (для контекстной оптимизации)
- `documents` (List[Dict]): Документы из поиска

**Возвращает**:
- Оптимизированный список документов с метаданными:
  - `auto_merged` (bool): Был ли чанк объединен
  - `merged_chunk_count` (int): Количество объединенных чанков
  - `chunk_span` (Dict): Диапазон чанков

**Пример**:
```python
from app.services.core.context_optimizer import optimize_context

documents = [
    {"url": "https://...", "chunk_index": 1, "text": "...", "score": 0.9},
    {"url": "https://...", "chunk_index": 2, "text": "...", "score": 0.88},
    {"url": "https://...", "chunk_index": 3, "text": "...", "score": 0.85},
]

optimized = optimize_context("Как настроить?", documents)
# [
#     {
#         "url": "https://...",
#         "text": "merged text...",  # Объединенный текст чанков 1-3
#         "auto_merged": True,
#         "merged_chunk_count": 3,
#         "chunk_span": {"start": 1, "end": 3}
#     }
# ]
```

**Конфигурация**:
```python
max_context_tokens = 6000        # Максимум токенов контекста
auto_merge_enabled = True        # Включить auto-merge
merge_similarity_threshold = 0.85  # Порог для объединения
max_merge_span = 5               # Макс. чанков в одном merge
```

---

## 🔍 Search Services

### 5. Hybrid Search (`app/services/search/retrieval.py`)

Гибридный поиск (dense + sparse) с BM25 reranking.

#### `hybrid_search(query_dense: List[float], query_sparse: Dict, k: int, ...) -> List[Dict]`

Основная функция гибридного поиска.

**Параметры**:
- `query_dense` (List[float]): Dense эмбеддинг запроса [1024]
- `query_sparse` (Dict[str, float]): Sparse вектор (BM25 scores)
- `k` (int): Количество результатов
- `boosts` (Optional[Dict[str, float]]): Метаданные boosts (e.g., `{"user_role:agent": 1.3}`)
- `categories` (Optional[List[str]]): Фильтр по категориям

**Возвращает**:
- Список документов с полями:
  - `id` (str): Qdrant point ID
  - `score` (float): Гибридная оценка релевантности
  - `payload` (Dict): Метаданные и текст

**Алгоритм**:
1. **Parallel search**: Dense + Sparse запросы параллельно
2. **Reciprocal Rank Fusion (RRF)**: Объединение результатов
3. **Metadata boosting**: Применение boosts к оценкам
4. **Reranking**: Переранжирование BM25 (если enabled)

**Пример**:
```python
from app.services.search.retrieval import hybrid_search
from app.services.core.embeddings import embed_unified

# 1. Получаем эмбеддинги запроса
embeddings = embed_unified("Как настроить маршрутизацию?", context="query")

# 2. Гибридный поиск
results = hybrid_search(
    query_dense=embeddings["dense_vecs"],
    query_sparse=embeddings["lexical_weights"],
    k=10,
    boosts={"user_role:admin": 1.2}
)

# 3. Результаты
for doc in results:
    print(f"Score: {doc['score']:.3f} - {doc['payload']['title']}")
```

**Конфигурация**:
```python
# В app.config.app_config
search_top_k = 10                # Количество результатов
dense_weight = 0.7               # Вес dense поиска
sparse_weight = 0.3              # Вес sparse поиска
use_bm25_reranking = True        # BM25 reranking
```

---

## 📊 Quality System

### 6. Quality Manager (`app/services/quality/quality_manager.py`)

Управление системой оценки качества (RAGAS).

#### `class QualityManager`

##### `async evaluate_interaction(query: str, answer: str, contexts: List[str]) -> Dict`

Оценка качества взаимодействия через RAGAS метрики.

**Параметры**:
- `query` (str): Запрос пользователя
- `answer` (str): Ответ системы
- `contexts` (List[str]): Использованные контексты

**Возвращает**:
```python
{
    "ragas_overall_score": float,     # Общая оценка RAGAS (0-1)
    "faithfulness": float,            # Соответствие контексту
    "answer_relevancy": float,        # Релевантность ответа
    "context_precision": float        # Точность выбора контекста
}
```

**RAGAS Метрики**:

1. **Faithfulness** (0-1): Насколько ответ соответствует предоставленному контексту
   - 1.0 = полное соответствие, нет галлюцинаций
   - 0.0 = ответ не соответствует контексту

2. **Answer Relevancy** (0-1): Насколько ответ релевантен запросу
   - 1.0 = полностью отвечает на вопрос
   - 0.0 = не относится к запросу

3. **Context Precision** (0-1): Точность выбора контекста
   - 1.0 = все контексты релевантны
   - 0.0 = контекст нерелевантен

**Пример**:
```python
import asyncio
from app.services.quality.quality_manager import quality_manager

async def evaluate():
    scores = await quality_manager.evaluate_interaction(
        query="Как настроить маршрутизацию?",
        answer="Для настройки маршрутизации откройте...",
        contexts=["Маршрутизация настраивается в разделе..."]
    )

    print(f"Overall: {scores['ragas_overall_score']:.2f}")
    print(f"Faithfulness: {scores['faithfulness']:.2f}")
    print(f"Relevancy: {scores['answer_relevancy']:.2f}")

asyncio.run(evaluate())
```

##### `async save_interaction(interaction_data: Dict) -> str`

Сохранение взаимодействия в БД качества.

**Возвращает**: `interaction_id` (UUID)

##### `async get_quality_statistics(days: int = 30) -> Dict`

Получение агрегированной статистики качества.

##### `async add_user_feedback(interaction_id: str, feedback_type: str, feedback_text: str = "") -> bool`

Добавление пользовательского фидбека.

---

## 🛠️ Infrastructure

### 7. Circuit Breaker (`app/infrastructure/circuit_breaker.py`)

Защита от каскадных сбоев внешних сервисов.

#### `class CircuitBreaker`

**Состояния**:
- `CLOSED` - нормальная работа
- `OPEN` - сервис недоступен, запросы блокируются
- `HALF_OPEN` - тестирование восстановления

**Конфигурация**:
```python
threshold = 3              # Ошибок до открытия
timeout_seconds = 30       # Время до попытки восстановления
half_open_attempts = 1     # Попыток в half-open
```

**Использование**:
```python
from app.infrastructure import llm_circuit_breaker

@llm_circuit_breaker.call
def call_llm_api():
    # Вызов внешнего LLM API
    response = requests.post(...)
    return response.json()

try:
    result = call_llm_api()
except CircuitBreakerOpen:
    # Fallback логика
    result = use_alternative_llm()
```

**Доступные breakers**:
- `llm_circuit_breaker` - защита LLM сервисов
- `embedding_circuit_breaker` - защита embedding сервисов
- `qdrant_circuit_breaker` - защита Qdrant
- `sparse_circuit_breaker` - защита sparse embedding сервиса

---

### 8. Cache Manager (`app/infrastructure/cache_manager.py`)

Двухуровневое кэширование (Redis + in-memory).

#### `class CacheManager`

##### `get(key: str) -> Optional[Any]`

Получение значения из кэша (сначала memory, потом Redis).

##### `set(key: str, value: Any, ttl: int = 3600)`

Сохранение значения в оба уровня кэша.

##### `invalidate(pattern: str)`

Инвалидация по паттерну (например, `"embedding:*"`).

**Пример**:
```python
from app.infrastructure import cache_manager

# Сохранение
cache_manager.set("query:hash123", result, ttl=3600)

# Получение
cached = cache_manager.get("query:hash123")
if cached:
    return cached

# Инвалидация
cache_manager.invalidate("query:*")
```

**Метрики**:
```python
stats = cache_manager.get_stats()
# {
#     "hits": 1523,
#     "misses": 456,
#     "hit_rate": 0.77,
#     "size": 1200
# }
```

---

### 9. Prometheus Metrics (`app/infrastructure/metrics.py`)

Метрики производительности и мониторинга.

#### Доступные метрики

**Счетчики**:
```python
queries_total = Counter('rag_queries_total',
    'Total number of queries',
    ['channel', 'status'])

cache_hits_total = Counter('rag_cache_hits_total',
    'Cache hits')

errors_total = Counter('rag_errors_total',
    'Errors',
    ['error_type'])
```

**Гистограммы**:
```python
query_duration = Histogram('rag_query_duration_seconds',
    'Query processing time')

embedding_duration = Histogram('rag_embedding_duration_seconds',
    'Embedding generation time')

llm_duration = Histogram('rag_llm_duration_seconds',
    'LLM generation time')
```

**Gauge**:
```python
quality_score = Gauge('rag_quality_score',
    'Average RAGAS score')
```

**Использование**:
```python
from app.infrastructure.metrics import queries_total, query_duration
import time

# Счетчик
queries_total.labels(channel="telegram", status="success").inc()

# Гистограмма (таймер)
start = time.time()
# ... обработка запроса ...
query_duration.observe(time.time() - start)

# Контекстный менеджер
with query_duration.time():
    # ... обработка запроса ...
    pass
```

---

## 🔐 Security

### 10. Security Monitor (`app/infrastructure/security_monitor.py`)

Мониторинг безопасности и защита от злоупотреблений.

#### `class SecurityMonitor`

##### `validate_and_sanitize(message: str) -> Tuple[str, List[str]]`

Валидация и санитизация входящего сообщения.

**Возвращает**:
- `sanitized_message` (str): Очищенное сообщение
- `warnings` (List[str]): Список предупреждений

**Проверки**:
- SQL injection паттерны
- XSS атаки
- Command injection
- Path traversal
- Excessive length

##### `track_user_activity(user_id: str, event_type: str)`

Отслеживание активности пользователя.

##### `get_user_risk_score(user_id: str) -> int`

Оценка риска пользователя (0-10).

##### `is_user_blocked(user_id: str) -> bool`

Проверка блокировки пользователя.

**Пример**:
```python
from app.infrastructure import security_monitor

# Валидация
sanitized, warnings = security_monitor.validate_and_sanitize(
    "<script>alert('xss')</script>Как настроить?"
)
# sanitized = "Как настроить?"
# warnings = ["XSS pattern detected"]

# Отслеживание
security_monitor.track_user_activity("user123", "query")

# Проверка риска
risk = security_monitor.get_user_risk_score("user123")
if risk > 7:
    # Блокировка
    security_monitor.block_user("user123", "High risk score")
```

---

## 🔗 Orchestrator

### 11. Query Orchestrator (`app/services/infrastructure/orchestrator.py`)

Главный оркестратор обработки запросов (главный entry point).

#### `handle_query(channel: str, chat_id: str, message: str) -> Dict[str, Any]`

Полный цикл обработки запроса пользователя.

**Этапы**:
1. **Query Processing** - нормализация и извлечение сущностей
2. **Embedding Generation** - создание эмбеддингов (dense + sparse)
3. **Hybrid Search** - поиск в Qdrant
4. **Context Optimization** - оптимизация и дедупликация
5. **LLM Generation** - генерация ответа
6. **Quality Evaluation** - оценка через RAGAS
7. **Metrics Collection** - сбор метрик

**Параметры**:
- `channel` (str): Канал ("telegram", "web", "api")
- `chat_id` (str): ID пользователя
- `message` (str): Текст запроса

**Возвращает**:
```python
{
    "answer": str,                    # Plain text (deprecated)
    "answer_markdown": str,           # Markdown ответ
    "sources": List[Dict],            # Источники
    "meta": Dict,                     # Метаданные LLM
    "channel": str,
    "chat_id": str,
    "processing_time": float,         # Секунды
    "interaction_id": str,            # UUID для quality system
    "security_warnings": List[str]    # Предупреждения
}
```

**Пример**:
```python
from app.services.infrastructure.orchestrator import handle_query

result = handle_query(
    channel="telegram",
    chat_id="123456789",
    message="Как настроить маршрутизацию?"
)

print(result["answer_markdown"])
print(f"Обработано за {result['processing_time']:.2f}с")
print(f"Interaction ID: {result['interaction_id']}")
```

**Error Handling**:
- `RAGError` - базовый класс ошибок
- `EmbeddingError` - ошибка генерации эмбеддингов
- `SearchError` - ошибка поиска
- `LLMError` - ошибка генерации LLM
- `QualityError` - ошибка RAGAS оценки

---

## 📦 Models

### 12. Data Models (`app/models/`)

#### `EnhancedMetadata` (`enhanced_metadata.py`)

Модель метаданных для документов в Qdrant.

```python
@dataclass
class EnhancedMetadata:
    # Основные поля
    title: str
    url: str
    canonical_url: str
    text: str
    chunk_index: int

    # SEO и структура
    section: str                    # start, agent, admin, api, etc.
    user_role: str                  # all, agent, supervisor, admin
    page_type: str                  # guide, api-reference, faq, etc.

    # Анализ контента
    token_count: int
    complexity_score: float         # 0.0-1.0
    semantic_density: float         # 0.0-1.0
    readability_score: float        # 0.0-1.0

    # Оптимизация поиска
    search_priority: float          # 1.0 = normal
    boost_factor: float             # Boost для метаданных
    semantic_tags: List[str]
```

#### `QualityInteraction` (`quality_interaction.py`)

Модель для хранения взаимодействий в БД качества.

```python
class QualityInteraction(Base):
    __tablename__ = 'quality_interactions'

    id = Column(Integer, primary_key=True)
    interaction_id = Column(String, unique=True)    # UUID
    query = Column(Text)
    response = Column(Text)
    contexts = Column(JSON)                          # List[str]

    # RAGAS метрики
    ragas_overall_score = Column(Float)
    faithfulness = Column(Float)
    answer_relevancy = Column(Float)
    context_precision = Column(Float)

    # Пользовательский фидбек
    user_feedback_type = Column(String)             # positive/negative
    feedback_text = Column(Text)
    combined_score = Column(Float)                  # RAGAS + feedback

    # Метаданные
    channel = Column(String)
    chat_id = Column(String)
    created_at = Column(DateTime)
```

---

## 🧪 Testing

### Юнит-тесты

```python
# tests/test_query_processing.py
def test_extract_entities():
    result = extract_entities("Как настроить арм агента?")
    assert "арм агента" in result

# tests/test_embeddings.py
def test_embed_unified():
    result = embed_unified("test query", return_dense=True)
    assert len(result["dense_vecs"]) == 1024

# tests/test_hybrid_search.py
def test_hybrid_search():
    results = hybrid_search(
        query_dense=[0.1]*1024,
        query_sparse={"test": 1.0},
        k=10
    )
    assert len(results) <= 10
```

### Интеграционные тесты

```python
# tests/test_end_to_end_pipeline.py
def test_full_pipeline():
    result = handle_query(
        channel="api",
        chat_id="test",
        message="Как настроить?"
    )

    assert "answer_markdown" in result
    assert len(result["sources"]) > 0
    assert result["processing_time"] < 10.0
```

---

## 📈 Best Practices

### 1. Добавление нового сервиса

```python
# app/services/core/my_service.py
from typing import Any, Dict
from loguru import logger

def my_function(param: str) -> Dict[str, Any]:
    """
    Краткое описание функции.

    Args:
        param: Описание параметра

    Returns:
        Описание возвращаемого значения

    Raises:
        ValueError: Когда возникает ошибка

    Example:
        >>> result = my_function("test")
        >>> print(result)
    """
    logger.info(f"Processing: {param}")

    try:
        # Логика
        result = {}
        return result
    except Exception as e:
        logger.error(f"Error in my_function: {e}")
        raise
```

### 2. Использование Circuit Breaker

```python
from app.infrastructure import create_circuit_breaker

# Создание breaker
my_service_breaker = create_circuit_breaker("my_service", threshold=3, timeout=30)

# Использование
@my_service_breaker.call
def call_external_api():
    response = requests.get("https://external-api.com")
    return response.json()
```

### 3. Добавление метрик

```python
from prometheus_client import Counter, Histogram

# Определение метрик
my_requests_total = Counter(
    'my_service_requests_total',
    'Total requests to my service',
    ['status']
)

my_duration = Histogram(
    'my_service_duration_seconds',
    'Request duration'
)

# Использование
def my_handler():
    with my_duration.time():
        try:
            # Обработка
            result = process()
            my_requests_total.labels(status="success").inc()
            return result
        except Exception as e:
            my_requests_total.labels(status="error").inc()
            raise
```

### 4. Кэширование

```python
from app.infrastructure import cache_manager
import hashlib

def get_cache_key(query: str) -> str:
    """Создание стабильного ключа кэша"""
    return f"query:{hashlib.md5(query.encode()).hexdigest()}"

def cached_function(query: str):
    key = get_cache_key(query)

    # Проверка кэша
    cached = cache_manager.get(key)
    if cached:
        return cached

    # Вычисление
    result = expensive_computation(query)

    # Сохранение
    cache_manager.set(key, result, ttl=3600)
    return result
```

---

## 🔧 Configuration

### Конфигурация приложения (`app/config/app_config.py`)

```python
class Config:
    # Qdrant
    qdrant_host = "localhost"
    qdrant_port = 6333
    qdrant_collection = "chatcenter_docs"

    # Embeddings
    embedding_model = "BAAI/bge-m3"
    embedding_device = "cpu"
    max_embedding_length = 1024

    # Search
    search_top_k = 10
    dense_weight = 0.7
    sparse_weight = 0.3
    use_bm25_reranking = True

    # LLM
    default_llm = "yandex"
    llm_max_tokens = 800
    llm_temperature = 0.3

    # Quality
    quality_db_enabled = True
    quality_db_path = "data/quality_interactions.db"

    # Cache
    redis_host = "localhost"
    redis_port = 6379
    cache_ttl_query = 3600
    cache_ttl_document = 86400
```

---

## 📚 Дополнительные ресурсы

- [Architecture Overview](architecture.md) - Общая архитектура системы
- [API Reference](api_reference.md) - Публичное REST API
- [Development Guide](development_guide.md) - Руководство разработчика
- [Testing Strategy](testing_strategy.md) - Стратегия тестирования

---

**Версия**: 4.3.0
**Последнее обновление**: Октябрь 2025
**Статус**: ✅ Production Ready
