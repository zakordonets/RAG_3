# Документация по индексации и структуре данных

## Обзор системы индексации

RAG-система edna Chat Center использует многоуровневую архитектуру индексации для обработки и хранения документации. Система поддерживает различные источники данных, автоматическое извлечение метаданных и гибридный поиск с использованием dense и sparse векторов.

**🎉 v4.2.0 - Критические исправления индексации завершены!**
- Исправлена схема коллекции для sparse векторов (sparse_vectors_config)
- Sparse векторы вынесены в отдельный параметр sparse_vectors
- Гибридный поиск dense + sparse работает корректно
- Автоматическое создание коллекций с правильной схемой
- Исправлена генерация doc_id: каждый документ получает уникальный URL
- Исправлена передача метаданных: site_url корректно передается через пайплайн
- Исправлена финальная статистика: отображаются реальные значения
- Исправлен параметр --max-pages: корректно ограничивает количество документов

## Архитектура индексации

### 1. Компоненты системы

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │    │  Universal      │    │   Chunking      │
│   (edna docs,   │───▶│  Loader         │───▶│   Engine        │
│    API, etc.)   │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Metadata      │    │   Embeddings    │    │   Qdrant        │
│   Processing    │◀───│   Generation    │◀───│   Storage       │
│                 │    │   (BGE-M3)      │    │   (Vectors)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2. Основные модули

- **`ingestion/universal_loader.py`** - Универсальный загрузчик контента
- **`ingestion/parsers.py`** - Парсеры для различных форматов
- **`ingestion/chunker.py`** - Система разбиения текста на чанки
- **`ingestion/semantic_chunker.py`** - Семантическое разбиение
- **`app/services/metadata_aware_indexer.py`** - Индексатор с метаданными
- **`app/services/optimized_pipeline.py`** - Оптимизированный pipeline
- **`scripts/indexer.py`** - Production модуль управления

## Источники данных

### 1. Поддерживаемые источники

#### edna Docs (основной)
- **URL**: `https://docs-chatcenter.edna.ru/`
- **Стратегия**: Jina Reader (рекомендуется)
- **Формат**: Docusaurus + Markdown
- **Типы страниц**: API, гайды, FAQ, релиз-ноты

#### Другие источники
- HTML страницы (generic)
- Markdown файлы
- API документация
- FAQ страницы

### 2. Стратегии загрузки

#### Jina Reader (рекомендуется)
```python
# Автоматическое извлечение структурированных данных
{
    "title": "Заголовок страницы",
    "url_source": "https://docs-chatcenter.edna.ru/...",
    "content_length": 2456,
    "language_detected": "Russian",
    "published_time": "2024-07-24T10:30:00Z",
    "images": 3,
    "links": 12,
    "content": "Markdown контент..."
}
```

#### HTML Docusaurus
```python
# Парсинг HTML структуры
{
    "title": "Заголовок из <h1>",
    "breadcrumbs": ["Документация", "Агент"],
    "content": "Основной текст статьи",
    "navigation": "Структура навигации"
}
```

#### Generic HTML
```python
# Базовый HTML парсинг
{
    "title": "Заголовок из <title>",
    "content": "Текст из <body>",
    "metadata": "Мета-теги"
}
```

## Система chunking

### 1. Стратегии разбиения

#### Простой chunker (по умолчанию)
- **Размер**: 60-250 токенов (настраивается)
- **Стратегия**: По абзацам с интеллектуальным объединением
- **Оптимизация**: 50-80% от максимального размера
- **Качество**: Дедупликация, фильтрация коротких чанков

#### Семантический chunker
- **Модель**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Порог сходства**: 0.7
- **Перекрытие**: 50 токенов (опционально)
- **Преимущества**: Сохранение семантической целостности

### 2. Адаптивный chunking

```python
def get_optimal_chunk_size(page_type: str, complexity: float) -> int:
    """Адаптивный размер чанка на основе типа страницы"""
    base_size = 250  # токенов

    if page_type == "api":
        return min(base_size * 1.5, 1200)  # API docs длиннее
    elif page_type == "guide":
        return min(base_size * 1.2, 1000)  # Гайды с контекстом
    elif page_type == "faq":
        return min(base_size * 0.8, 600)   # FAQ короче

    if complexity > 0.8:
        return min(base_size * 0.9, 800)   # Сложный контент
    elif complexity < 0.3:
        return min(base_size * 1.3, 1000)  # Простой контент

    return base_size
```

### 3. Quality Gates

- **Минимальный размер**: 60 токенов
- **Дедупликация**: SHA-256 хэши
- **Фильтрация**: Пустые и мусорные чанки
- **Валидация**: Проверка целостности

## Система метаданных

### 1. Enhanced Metadata

```python
@dataclass
class EnhancedMetadata:
    # Базовые метаданные
    url: str
    page_type: str  # api, guide, faq, release_notes
    title: str
    source: str = "docs-site"
    language: str = "ru"

    # Структурная информация
    section: Optional[str] = None
    subsection: Optional[str] = None
    chunk_index: int = 0

    # Анализ контента
    token_count: int = 0
    complexity_score: float = 0.0      # 0.0-1.0
    semantic_density: float = 0.0      # 0.0-1.0
    readability_score: float = 0.0     # 0.0-1.0

    # Технические метаданные
    content_length: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Семантическая информация
    keywords: List[str] = None
    topics: List[str] = None
    entities: List[str] = None

    # Оптимизация поиска
    search_priority: float = 1.0
    boost_factor: float = 1.0
    semantic_tags: List[str] = None
```

### 2. Извлечение метаданных

#### Из URL
```python
def extract_url_metadata(url: str) -> Dict[str, str]:
    """Извлечение метаданных из URL паттернов"""
    patterns = {
        r'/docs/start/': {'section': 'start', 'user_role': 'all', 'page_type': 'guide'},
        r'/docs/agent/': {'section': 'agent', 'user_role': 'agent', 'page_type': 'guide'},
        r'/docs/supervisor/': {'section': 'supervisor', 'user_role': 'supervisor', 'page_type': 'guide'},
        r'/docs/admin/': {'section': 'admin', 'user_role': 'admin', 'page_type': 'guide'},
        r'/docs/api/': {'section': 'api', 'user_role': 'integrator', 'page_type': 'api-reference'},
        r'/blog/': {'section': 'changelog', 'user_role': 'all', 'page_type': 'release-notes'},
        r'/faq': {'section': 'faq', 'user_role': 'all', 'page_type': 'faq'},
    }
```

#### Из контента
```python
def calculate_complexity_score(text: str) -> float:
    """Расчет сложности контента"""
    avg_sentence_length = len(text.split()) / max(len(text.split('.')), 1)
    technical_terms = len(re.findall(r'\b[A-Z]{2,}\b|\b\w+\.(py|js|ts|sql|api|sdk)\b', text))
    code_blocks = len(re.findall(r'```|`[^`]+`', text))

    complexity = min(1.0, (avg_sentence_length / 20) + (technical_terms / 100) + (code_blocks / 10))
    return round(complexity, 3)
```

### 3. Boost Factor

```python
def calculate_boost_factor(metadata: EnhancedMetadata) -> float:
    """Динамический boost на основе метаданных"""
    boost = 1.0

    # Boost по типу страницы
    if metadata.page_type == "guide": boost *= 1.2
    elif metadata.page_type == "api": boost *= 1.1
    elif metadata.page_type == "faq": boost *= 1.3

    # Boost по качеству контента
    if metadata.semantic_density > 0.6: boost *= 1.2
    if metadata.complexity_score > 0.5: boost *= 1.1

    # Boost для getting started
    if '/docs/start/' in metadata.url: boost *= 1.4

    return round(boost, 2)
```

## Схема Qdrant

### 1. Структура коллекции

```python
# Коллекция: chatcenter_docs
{
    "vectors_config": {
        "dense": VectorParams(size=1024, distance=Distance.COSINE),
        "sparse": SparseVectorParams()
    },
    "hnsw_config": {
        "m": 16,
        "ef_construct": 100,
        "ef_search": 50,
        "full_scan_threshold": 10000
    }
}
```

### 2. Named Vectors

#### Dense Vector
- **Размерность**: 1024
- **Модель**: BAAI/bge-m3
- **Расстояние**: COSINE
- **Использование**: Семантический поиск

#### Sparse Vector
- **Формат**: SparseVector(indices, values)
- **Модель**: BAAI/bge-m3 sparse
- **Использование**: Лексический поиск
- **Оптимизация**: Топ-1000 весов

### 3. Payload структура

```python
{
    # Базовые метаданные
    "url": "https://docs-chatcenter.edna.ru/docs/agent/routing",
    "page_type": "guide",
    "title": "Настройка маршрутизации",
    "source": "docs-site",
    "language": "ru",
    "section": "agent",
    "chunk_index": 0,

    # Анализ контента
    "content_length": 1250,
    "token_count": 180,
    "complexity_score": 0.65,
    "semantic_density": 0.72,
    "readability_score": 0.58,

    # Оптимизация поиска
    "boost_factor": 1.44,
    "search_priority": 1.0,
    "search_strategy": {"sparse_weight": 0.5, "dense_weight": 0.5},

    # Семантическая информация
    "keywords": ["маршрутизация", "агент", "настройка"],
    "semantic_tags": ["type:guide", "complexity:medium", "content:dense"],

    # Технические метаданные
    "hash": "uuid-4-format",
    "indexed_via": "jina",
    "indexed_at": 1703123456.789,
    "created_at": "2024-07-24T10:30:00Z",
    "updated_at": "2024-12-20T15:45:00Z"
}
```

## Pipeline индексации

### 1. Основной pipeline

```python
def crawl_and_index(
    incremental: bool = True,
    strategy: str = "jina",
    use_cache: bool = True,
    reindex_mode: str = "auto",
    max_pages: int = None
) -> dict[str, Any]:
    """Полный цикл индексации"""

    # 1. Краулинг
    pages = crawl_with_sitemap_progress(
        strategy=strategy,
        use_cache=use_cache,
        max_pages=max_pages
    )

    # 2. Обработка страниц
    all_chunks = []
    for page in pages:
        # Универсальная загрузка
        loaded_data = load_content_universal(
            url=page["url"],
            content=page.get("text") or page.get("html"),
            strategy=strategy
        )

        # Chunking
        chunks_text = chunk_text(loaded_data.get('content', ''))

        # Создание чанков с метаданными
        for i, chunk_text_content in enumerate(chunks_text):
            chunk = {
                "text": chunk_text_content,
                "payload": {
                    "url": page["url"],
                    "title": loaded_data.get('title', 'Untitled'),
                    "page_type": loaded_data.get('page_type', 'guide'),
                    "chunk_index": i,
                    **loaded_data  # Все метаданные
                }
            }
            all_chunks.append(chunk)

    # 3. Индексация с enhanced metadata
    metadata_indexer = MetadataAwareIndexer()
    indexed_count = metadata_indexer.index_chunks_with_metadata(all_chunks)

    return {"pages": len(pages), "chunks": indexed_count}
```

### 2. Оптимизированный pipeline

```python
def run_optimized_indexing(
    source_name: str = "edna_docs",
    max_pages: Optional[int] = None,
    chunk_strategy: str = "adaptive"
) -> Dict[str, Any]:
    """Оптимизированный pipeline с новой архитектурой"""

    pipeline = OptimizedPipeline()

    # Получение источника данных
    source = plugin_manager.get_source(source_name, source_config)

    # Загрузка страниц
    crawl_result = source.fetch_pages(max_pages)

    # Обработка в чанки
    chunks = pipeline._process_pages_to_chunks(
        crawl_result.pages,
        chunk_strategy
    )

    # Индексация с метаданными
    indexed_count = pipeline.indexer.index_chunks_with_metadata(chunks)

    return {
        "success": True,
        "pages": crawl_result.successful_pages,
        "chunks": indexed_count,
        "duration": time.time() - start_time
    }
```

### 3. Генерация эмбеддингов

```python
def embed_batch_optimized(
    texts: List[str],
    max_length: int = 1024,
    return_dense: bool = True,
    return_sparse: bool = True,
    context: str = "document"
) -> Dict[str, Any]:
    """Оптимизированная генерация эмбеддингов"""

    # Определение оптимального batch size
    batch_size = get_optimal_batch_size("unified")

    # Генерация dense эмбеддингов
    if return_dense:
        dense_vecs = generate_dense_embeddings(texts, batch_size)

    # Генерация sparse эмбеддингов
    if return_sparse:
        sparse_results = generate_sparse_embeddings(texts, batch_size)

    return {
        "dense_vecs": dense_vecs,
        "lexical_weights": sparse_results
    }
```

## Управление индексацией

### 1. Production модуль

```bash
# Проверка статуса
python scripts/indexer.py status

# Полная переиндексация
python scripts/indexer.py reindex --mode full

# Инкрементальное обновление
python scripts/indexer.py reindex --mode incremental

# Использование кеша
python scripts/indexer.py reindex --mode cache_only

# Очистка кеша страниц
python scripts/indexer.py clear-cache --confirm

# Инициализация коллекции
python scripts/indexer.py init

# Пересоздание коллекции
python scripts/indexer.py init --recreate
```

### 2. Управление кэшем

Система автоматически сохраняет загруженные страницы в кэш для ускорения последующих индексаций. Кэш сохраняется между запусками и не очищается автоматически.

```bash
# Проверка содержимого кэша
ls cache/crawl/pages/  # Просмотр закешированных страниц

# Очистка кэша (требует подтверждения)
python scripts/indexer.py clear-cache --confirm

# Индексация с очисткой устаревших записей из кэша
python scripts/indexer.py reindex --mode full --cleanup-cache

# Индексация только из кэша (без загрузки новых страниц)
python scripts/indexer.py reindex --mode cache_only
```

**Важные моменты:**
- Кэш сохраняется между запусками системы
- При `max_pages` ограничении кэш не очищается автоматически
- Очистка кэша требуется только при изменении структуры сайта
- Используйте `cache_only` для быстрого тестирования на закешированных данных

### 3. Конфигурация

```python
# Основные параметры
CHUNK_MIN_TOKENS = 60
CHUNK_MAX_TOKENS = 250
EMBEDDING_DIM = 1024
EMBEDDING_BATCH_SIZE = 16
EMBEDDING_MAX_LENGTH_DOC = 1024

# Qdrant настройки
QDRANT_HNSW_M = 16
QDRANT_HNSW_EF_CONSTRUCT = 100
QDRANT_HNSW_EF_SEARCH = 50
QDRANT_HNSW_FULL_SCAN_THRESHOLD = 10000

# Эмбеддинги
EMBEDDINGS_BACKEND = "auto"  # auto, onnx, bge, hybrid
EMBEDDING_DEVICE = "auto"    # auto, cpu, cuda, directml
USE_SPARSE = True
```

### 4. Мониторинг

```python
def get_collection_metadata_stats() -> Dict[str, Any]:
    """Статистика коллекции"""
    return {
        "total_documents": collection_info.points_count,
        "sparse_coverage": 100.0,  # Процент покрытия sparse векторами
        "page_type_distribution": {
            "guide": 150,
            "api": 45,
            "faq": 23,
            "release_notes": 12
        },
        "avg_complexity_score": 0.65,
        "avg_semantic_density": 0.72,
        "avg_boost_factor": 1.15,
        "metadata_enabled": True
    }
```

## Оптимизации производительности

### 1. Батчевая обработка

- **Dense эмбеддинги**: 16-32 текста за раз
- **Sparse эмбеддинги**: 8-16 текстов за раз
- **Индексация**: 100-500 точек за раз

### 2. Кеширование

- **Redis**: Эмбеддинги и результаты поиска
- **In-memory fallback**: При недоступности Redis
- **Crawl cache**: Кеширование загруженных страниц

### 3. GPU ускорение

- **ONNX + DirectML**: Windows/AMD GPU
- **CUDA**: NVIDIA GPU
- **CPU fallback**: Автоматический fallback

### 4. Адаптивные стратегии

```python
def get_search_strategy(metadata: EnhancedMetadata) -> Dict[str, float]:
    """Адаптивная стратегия поиска"""
    if metadata.page_type == "api":
        return {"sparse_weight": 0.7, "dense_weight": 0.3}  # API - точное совпадение
    elif metadata.complexity_score > 0.7:
        return {"sparse_weight": 0.3, "dense_weight": 0.7}  # Сложный контент - семантика
    else:
        return {"sparse_weight": 0.5, "dense_weight": 0.5}  # Сбалансированный подход
```

## Troubleshooting

### 1. Частые проблемы

#### Пустые чанки
```python
# Проверка качества chunking
if not chunks_text:
    logger.warning(f"Не удалось создать чанки для {url}")
    continue
```

#### Ошибки эмбеддингов
```python
# Fallback стратегии
try:
    embeddings = generate_embeddings(texts)
except Exception as e:
    logger.warning(f"Ошибка эмбеддингов: {e}")
    # Fallback к простому chunking
    chunks = _chunk_text_simple(text, min_tokens, max_tokens)
```

#### Проблемы с Qdrant
```python
# Проверка подключения
try:
    collection_info = client.get_collection(collection_name)
except Exception as e:
    logger.error(f"Ошибка подключения к Qdrant: {e}")
    return {"error": "Qdrant недоступен"}
```

### 2. Диагностика

```bash
# Проверка статуса системы
python scripts/indexer.py status

# Тестовая переиндексация
python scripts/indexer.py reindex --mode full --max-pages 5

# Проверка метаданных
pytest tests/test_data_validation.py -v
```

### 3. Логирование

```python
# Детальное логирование процесса
logger.info(f"Обработано {len(chunks)} чанков")
logger.debug(f"Chunk {i}: {len(chunk_text)} токенов")
logger.warning(f"Пропущен чанк: {reason}")
```

## Заключение

Система индексации edna Chat Center представляет собой комплексное решение для обработки и хранения документации с поддержкой:

- **Множественных источников данных** с универсальным загрузчиком
- **Интеллектуального chunking** с семантическим анализом
- **Богатых метаданных** для оптимизации поиска
- **Гибридного поиска** с dense и sparse векторами
- **Production-ready управления** через единый модуль
- **Мониторинга и диагностики** состояния системы

Архитектура обеспечивает высокую производительность, масштабируемость и качество поиска при работе с технической документацией.
