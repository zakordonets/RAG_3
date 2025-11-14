# Indexing & Data Structure Guide

Детальное руководство по системе индексации и структурам данных RAG-системы.

**Версия**: 4.3.1
**Дата обновления**: 9 октября 2024
**Статус**: Production Ready

---

## 📖 Содержание

- [Обзор](#обзор)
- [Архитектура](#архитектура-индексации)
- [Data Structures](#data-structures)
  - [Qdrant Schema](#qdrant-schema)
  - [Metadata Structure](#система-метаданных)
- [Chunking System](#система-chunking)
- [Indexing Pipeline](#pipeline-индексации)
- [Performance](#оптимизации-производительности)
- [Management](#управление-индексацией)
- [Troubleshooting](#troubleshooting)

---

## Обзор

Система индексации обрабатывает документацию через унифицированный DAG pipeline с:

- ✅ **Гибридные векторы** - Dense (BGE-M3 1024d) + Sparse (keyword matching)
- ✅ **Rich metadata** - 20+ полей для оптимизации поиска
- ✅ **Adaptive chunking** - Размер чанков зависит от типа контента
- ✅ **Production-ready** - Batch processing, caching, monitoring

### Ключевые возможности

| Компонент | Технология | Статус |
|-----------|------------|--------|
| **Vector DB** | Qdrant 1.7+ | ✅ Production |
| **Embeddings** | BGE-M3 (dense + sparse) | ✅ Production |
| **Chunking** | Universal + Adaptive | ✅ Production |
| **Pipeline** | DAG architecture | ✅ Production |
| **Metadata** | Enhanced 20+ fields | ✅ Production |

### Связанная документация

- 📦 [Adding Data Sources](adding_data_sources.md) - Добавление источников данных
- 🏗️ [Architecture](architecture.md) - Общая архитектура системы
- 🔧 [Technical Specification](technical_specification.md) - Техническая спецификация

---

## Архитектура индексации

### DAG Pipeline

```
Data Source (Docusaurus, Website)
    ↓ SourceAdapter.iter_documents()
RawDoc (uri, bytes, meta)
    ↓ Parser
ParsedDoc (text, url, title)
    ↓ Normalizer
Normalized Text
    ↓ UniversalChunker
Chunks (text + metadata)
    ↓ Embedder (BGE-M3)
Chunks + Vectors (dense + sparse)
    ↓ QdrantWriter
Qdrant Collection (indexed)
```

### Ключевые компоненты

| Компонент | Модуль | Назначение |
|-----------|--------|------------|
| **SourceAdapter** | `ingestion/adapters/` | Извлечение документов |
| **Normalizers** | `ingestion/normalizers/` | Очистка и нормализация |
| **UniversalChunker** | `ingestion/chunking/` | Разбиение на чанки |
| **Embedder** | `ingestion/pipeline/embedder.py` | Генерация векторов |
| **QdrantWriter** | `ingestion/pipeline/indexers/` | Запись в Qdrant |
| **PipelineDAG** | `ingestion/pipeline/dag.py` | Оркестрация |

**Подробнее**: См. [adding_data_sources.md](adding_data_sources.md) для деталей DAG архитектуры.

---

## Data Structures

### Qdrant Schema

#### Collection Configuration

```python
from qdrant_client.models import VectorParams, Distance, SparseVectorParams

collection_config = {
    "vectors_config": {
        # Dense vector (BGE-M3)
        "dense": VectorParams(
            size=1024,
            distance=Distance.COSINE
        )
    },
    # Sparse vectors (keyword matching)
    "sparse_vectors_config": {
        "sparse": SparseVectorParams()
    },
    # HNSW index configuration
    "hnsw_config": {
        "m": 16,                      # Связей на узел
        "ef_construct": 100,          # Качество построения
        "ef_search": 50,              # Качество поиска
        "full_scan_threshold": 10000  # Порог полного сканирования
    }
}
```

**Параметры**:
- **m**: Количество двунаправленных связей (trade-off память/качество)
- **ef_construct**: Глубина поиска при построении (выше = медленнее build, лучше recall)
- **ef_search**: Глубина поиска запросов (выше = медленнее search, лучше precision)

#### Point Structure

```python
# Точка в Qdrant
{
    "id": "abc123-chunk-0",  # Уникальный ID
    "vector": {
        "dense": [0.1, 0.2, ..., 0.9],  # 1024 float
        "sparse": {                      # Отдельный параметр!
            "indices": [1, 42, 567],
            "values": [0.8, 0.6, 0.4]
        }
    },
    "payload": {
        # См. Metadata Structure ниже
    }
}
```

**Критично**: Sparse векторы передаются через `sparse_vectors` parameter, НЕ в `vector`!

---

---

## Система метаданных

### Payload Structure

Полная структура метаданных, сохраняемых в Qdrant payload:

```python
payload = {
    # === Базовые поля (обязательные) ===
    "url": str,              # URL документа
    "title": str,            # Заголовок страницы
    "text": str,             # Текст чанка
    "page_type": str,        # guide | api | faq | release_notes
    "source": str,           # docs-site | api-docs | blog
    "language": str,         # ru | en

    # === Структура документа ===
    "doc_id": str,           # Уникальный ID документа
    "chunk_id": str,         # Уникальный ID чанка
    "chunk_index": int,      # Порядковый номер чанка
    "heading_path": List[str],  # Иерархия заголовков

    # === Анализ контента ===
    "token_count": int,      # Количество токенов
    "content_length": int,   # Длина в символах
    "complexity_score": float,  # 0.0-1.0
    "semantic_density": float,  # 0.0-1.0 (опционально)

    # === Оптимизация поиска ===
    "boost_factor": float,   # 1.0-2.0 (множитель релевантности)
    "search_priority": float,  # 0.0-1.0

    # === Временные метки ===
    "created_at": str,       # ISO 8601
    "updated_at": str,       # ISO 8601 (опционально)
    "indexed_at": float      # Unix timestamp
}
```

### Извлечение метаданных

#### Из URL паттернов

```python
# URL → metadata mapping
url_patterns = {
    r'/docs/start/':      {'section': 'start', 'page_type': 'guide'},
    r'/docs/agent/':      {'section': 'agent', 'page_type': 'guide'},
    r'/docs/supervisor/': {'section': 'supervisor', 'page_type': 'guide'},
    r'/docs/admin/':      {'section': 'admin', 'page_type': 'guide'},
    r'/docs/api/':        {'section': 'api', 'page_type': 'api'},
    r'/blog/':            {'section': 'changelog', 'page_type': 'release_notes'},
    r'/faq':              {'section': 'faq', 'page_type': 'faq'}
}
```

#### Анализ контента

**Complexity Score** (сложность текста):
```python
def calculate_complexity(text: str) -> float:
    """0.0 (простой) → 1.0 (сложный)"""
    avg_sentence_len = len(text.split()) / max(len(text.split('.')), 1)
    technical_terms = len(re.findall(r'\b[A-Z]{2,}\b', text))
    code_blocks = len(re.findall(r'```', text))

    complexity = (
        (avg_sentence_len / 20) * 0.4 +
        (technical_terms / 100) * 0.3 +
        (code_blocks / 10) * 0.3
    )
    return min(1.0, complexity)
```

**Boost Factor** (приоритет в поиске):
```python
def calculate_boost(metadata: dict) -> float:
    """1.0 (нормальный) → 2.0 (высокий приоритет)"""
    boost = 1.0

    # По типу страницы
    if metadata["page_type"] == "faq":   boost *= 1.3
    if metadata["page_type"] == "guide": boost *= 1.2

    # По секции
    if "start" in metadata.get("section", ""): boost *= 1.4

    return round(boost, 2)
```

---

## Система Chunking

### UniversalChunker

**Модуль**: `ingestion/chunking/universal_chunker.py`

```python
from ingestion.chunking.universal_chunker import UniversalChunker

chunker = UniversalChunker(
    max_tokens=300,            # Оптимизировано для точности ответов
    min_tokens=150,            # Фокус на одной теме
    overlap_base=50,           # Адаптивное перекрытие
    oversize_block_policy="split",  # Разбиение больших блоков
    oversize_block_limit=600   # Лимит для принудительного split
)

# Чанкинг
chunks = chunker.chunk(
    text="Текст документа...",
    content_type="markdown",   # markdown | html | text
    metadata={"url": "...", "title": "..."}
)
```

### Параметры Chunking (Production)

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| `max_tokens` | **300** | Предотвращение смешивания разных тем |
| `min_tokens` | **150** | Достаточно для семантического понимания |
| `overlap_base` | **50** | Сохранение контекста между чанками |
| `oversize_block_policy` | split | Разбиение больших code/table блоков |
| `oversize_block_limit` | 600 | Максимум перед принудительным split |

### Почему 150-300, а не больше?

**Проблема с большими чанками** (350-600 токенов):
- ❌ Информация из разных подразделов сливалась
- ❌ LLM генерировал некорректные ответы
- ❌ Контекст из нерелевантных частей чанка

**Преимущества меньших чанков** (150-300 токенов):
- ✅ Один чанк = одна конкретная тема
- ✅ Точные, фокусированные ответы
- ✅ Лучшая релевантность retrieval

**См. детали**: [ADR-002](adr-002-adaptive-chunking.md) - почему практика отличается от теории

### Типичные размеры по типам

| Тип контента | Типичный размер | Почему |
|--------------|-----------------|--------|
| **Параграф guide** | 150-250 токенов | Одна мысль/концепция |
| **FAQ answer** | 100-200 токенов | Короткий ответ |
| **Code block** | 100-400 токенов | Сохранение целостности |
| **API endpoint** | 200-350 токенов | Описание + примеры |

### Quality Gates

Автоматическая фильтрация:
- ✅ Минимальный размер: 50 токенов (discard smaller)
- ✅ Дедупликация: по content hash
- ✅ Валидация: проверка metadata completeness
- ✅ Фильтрация: пустых и мусорных чанков

---

## Pipeline индексации

### Unified DAG Pipeline (v4.3+)

**Модуль**: `ingestion/run.py`

```python
from ingestion.run import run_unified_indexing

# Запуск индексации
result = run_unified_indexing(
    source_type="docusaurus",
    config={
        "collection_name": "edna_docs",
        "docs_root": "/path/to/docs",
        "chunk_max_tokens": 600,
        "chunk_min_tokens": 350
    }
)

print(f"Indexed {result['chunks_count']} chunks from {result['docs_count']} documents")
```

### Pipeline Steps

| Шаг | Компонент | Вход | Выход |
|-----|-----------|------|-------|
| 1 | **SourceAdapter** | Config | RawDoc(uri, bytes, meta) |
| 2 | **Parser** | RawDoc | ParsedDoc(text, url, title) |
| 3 | **Normalizer** | ParsedDoc | Normalized ParsedDoc |
| 4 | **UniversalChunker** | ParsedDoc | List[Chunk] |
| 5 | **Embedder** | List[Chunk] | Chunks + Vectors |
| 6 | **QdrantWriter** | Chunks + Vectors | Indexed count |

### Генерация Embeddings

**Модуль**: `ingestion/pipeline/embedder.py`

```python
from ingestion.pipeline.embedder import Embedder

embedder = Embedder()

# Обработка чанков
chunks_with_embeddings = []
for chunk in chunks:
    # Dense embedding (BGE-M3)
    dense_vec = embedder.embed_dense(chunk.text)

    # Sparse embedding (BGE-M3 sparse)
    sparse_vec = embedder.embed_sparse(chunk.text)

    chunks_with_embeddings.append({
        "text": chunk.text,
        "dense_vector": dense_vec,     # List[float] 1024 dim
        "sparse_vector": sparse_vec,   # {"indices": [...], "values": [...]}
        "metadata": chunk.metadata
    })
```

**Производительность**:
- Dense batch size: 16-32 texts
- Sparse batch size: 8-16 texts
- Total time: ~5-10 сек на batch

### Запись в Qdrant

**Модуль**: `ingestion/pipeline/indexers/qdrant_writer.py`

```python
from ingestion.pipeline.indexers.qdrant_writer import QdrantWriter

writer = QdrantWriter(collection_name="edna_docs")

# Batch upsert
result = writer.upsert_points(
    points=[
        {
            "id": chunk_id,
            "vector": {"dense": dense_vec},  # Named vector
            "sparse_vectors": {"sparse": sparse_vec},  # Отдельный параметр!
            "payload": metadata
        }
        for chunk_id, dense_vec, sparse_vec, metadata in batch
    ]
)

print(f"Upserted {result.count} points")
```

**Важно**: Sparse векторы передаются через `sparse_vectors` parameter!

---

## Управление индексацией

### CLI Commands

**Основной entrypoint**: `ingestion/run.py`

```bash
# Полная переиндексация
python -m ingestion.run --config ingestion/config.yaml --reindex-mode full

# Инкрементальная индексация (только changed)
python -m ingestion.run --config ingestion/config.yaml --reindex-mode changed

# Ограничение количества страниц (для тестов)
python -m ingestion.run --config ingestion/config.yaml --max-pages 10
```

### Инициализация Qdrant

```bash
# Создать коллекцию с правильной схемой
python scripts/init_qdrant.py

# Пересоздать (удалить + создать)
python scripts/init_qdrant.py --recreate

# Очистить все точки
python scripts/clear_collection.py --collection edna_docs
```

### Конфигурация

**Файл**: `ingestion/config.yaml`

```yaml
sources:
  docusaurus:
    enabled: true
    docs_root: "C:\CC_RAG\docs"
    site_base_url: "https://docs-chatcenter.edna.ru"
    site_docs_prefix: "/docs"
    chunk:
      max_tokens: 600
      min_tokens: 350
      overlap_base: 100
      oversize_block_policy: split
      oversize_block_limit: 1200
  docusaurus_sdk:
    enabled: true
    docs_root: "C:\CC_RAG\SDK_docs\docs"
    site_base_url: "https://docs-sdk.edna.ru"
    site_docs_prefix: ""
    top_level_meta:
      android:
        sdk_platform: "android"
        product: "sdk"
      ios:
        sdk_platform: "ios"
        product: "sdk"
      web:
        sdk_platform: "web"
        product: "sdk"
      main:
        sdk_platform: "main"
        product: "sdk"

global:
  qdrant:
    collection: "chatcenter_docs"
  indexing:
    batch_size: 16
    reindex_mode: "changed"
```

Запустите все активированные источники одной командой:

```bash
python -m ingestion.run --config ingestion/config.yaml --profile production
```








### Мониторинг индексации

**Проверка статуса коллекции**:
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")
info = client.get_collection("edna_docs")

print(f"Points: {info.points_count}")
print(f"Vectors: {info.config.params.vectors}")
print(f"Sparse: {info.config.params.sparse_vectors}")
```

**Статистика метаданных**:
```bash
# Проверка distribution по page_type
python scripts/check_text_field.py

# Анализ конкретного документа
python scripts/check_file_indexed.py --url "https://docs..."

# Full-text search для отладки
python scripts/check_full_text.py --query "маршрутизация"
```

---

## Оптимизации производительности

### Batch Processing

| Операция | Batch Size | Время | Оптимизация |
|----------|------------|-------|-------------|
| **Dense embeddings** | 16-32 | 5-10 сек | GPU если доступен |
| **Sparse embeddings** | 8-16 | 3-5 сек | CPU оптимизирован |
| **Qdrant upsert** | 100-500 | 1-2 сек | Parallel requests |

### Caching Strategy

**Crawl Cache** (файловая):
- Локация: `cache/crawl/`
- Формат: JSON files
- Retention: Не очищается автоматически
- Размер: ~100KB на страницу

```bash
# Просмотр кэша
ls -lh cache/crawl/*.json

# Очистка
rm -rf cache/crawl/*
```

**Redis Cache** (опционально):
- Embeddings cache (TTL: 24h)
- Search results cache (TTL: 1h)
- In-memory fallback при недоступности

### GPU Acceleration

| Тип GPU | Технология | Ускорение |
|---------|------------|-----------|
| **NVIDIA** | CUDA | 10-20x vs CPU |
| **AMD/Intel** | DirectML + ONNX | 5-10x vs CPU |
| **CPU** | Fallback | Baseline |

**Настройка**:
```bash
# .env
EMBEDDING_DEVICE=cuda        # cuda | directml | cpu | auto
EMBEDDINGS_BACKEND=onnx      # onnx | bge | hybrid
```

### Adaptive Search Weights

Веса dense/sparse адаптируются под тип контента:

```python
# Для API документации - приоритет keyword matching
{"sparse_weight": 0.7, "dense_weight": 0.3}

# Для сложных guides - приоритет semantic
{"sparse_weight": 0.3, "dense_weight": 0.7}

# Для FAQ - сбалансированный подход
{"sparse_weight": 0.5, "dense_weight": 0.5}
```

---

## Troubleshooting

### 1. "Sparse vectors error"

**Симптомы**:
```python
ValueError: Cannot pass both vector and sparse_vectors
```

**Причина**: Неправильная передача sparse векторов в Qdrant

**Решение**:
```python
# ❌ Неправильно
point = {
    "vector": {
        "dense": dense_vec,
        "sparse": sparse_vec  # ОШИБКА!
    }
}

# ✅ Правильно
point = {
    "vector": {"dense": dense_vec},
    "sparse_vectors": {"sparse": sparse_vec}  # Отдельный параметр
}
```

### 2. "Empty chunks"

**Симптомы**: Некоторые документы не разбиваются на чанки

**Причины**:
- Документ слишком короткий (< min_tokens)
- Парсер не извлек текст
- Текст только whitespace

**Диагностика**:
```bash
# Проверьте parsed текст
python scripts/check_file_indexed.py --url "https://problem-doc-url"

# Проверьте логи
grep "пропущен\|skipped" logs/app.log
```

**Решение**:
- Проверьте parser для данного типа страниц
- Уменьшите `min_tokens` в конфигурации
- Добавьте специфичный normalizer

### 3. "Embeddings generation timeout"

**Симптомы**: Pipeline зависает на embeddings

**Причины**:
- Слишком большой batch
- Нет GPU, медленный CPU
- Модель не загружена

**Решение**:
```bash
# Уменьшите batch size в config.yaml
performance:
  embedding_batch_size: 8  # было 16

# Или используйте ONNX для ускорения
EMBEDDINGS_BACKEND=onnx
EMBEDDING_DEVICE=directml  # для AMD/Intel GPU
```

### 4. "Qdrant connection refused"

**Симптомы**: Не удается подключиться к Qdrant

**Диагностика**:
```bash
# Проверьте, что Qdrant запущен
curl http://localhost:6333/collections

# Проверьте Docker
docker ps | grep qdrant

# Проверьте порт
netstat -an | grep 6333
```

**Решение**:
```bash
# Запустите Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# Или через docker-compose
docker-compose up -d qdrant
```

### 5. "Duplicate points"

**Симптомы**: Одинаковые документы индексируются несколько раз

**Причина**: ID генерируется не уникально

**Решение**:
```python
# Убедитесь, что используется уникальный ID
chunk_id = f"{doc_id}-chunk-{chunk_index}"

# Или используйте upsert вместо insert
writer.upsert_points(...)  # Обновит существующие
```

### Диагностические скрипты

```bash
# Полный анализ коллекции
python scripts/deep_analysis.py

# Проверка конкретного URL
python scripts/check_file_indexed.py --url "https://docs..."

# Проверка full-text поиска
python scripts/check_full_text.py --query "ваш запрос"

# Тестирование retrieval
python scripts/test_retrieval_for_url.py --url "https://docs..."

# Валидация pipeline
pytest tests/test_unified_pipeline.py -v
```

### Логирование

**Уровни для индексации**:
```python
# DEBUG - детали каждого шага
logger.debug(f"Processing document: {url}")
logger.debug(f"Created {len(chunks)} chunks")

# INFO - общий прогресс
logger.info(f"Indexed {count} documents")

# WARNING - пропущенные документы
logger.warning(f"Skipped {url}: {reason}")

# ERROR - критические ошибки
logger.error(f"Failed to index {url}: {error}")
```

---

## 📚 Связанная документация

- [Adding Data Sources](adding_data_sources.md) - Добавление новых источников
- [Architecture](architecture.md) - Архитектура системы
- [Technical Specification](technical_specification.md) - Техническая спецификация
- [Development Guide](development_guide.md) - Руководство разработчика

### Полезные скрипты

| Скрипт | Назначение |
|--------|------------|
| `scripts/init_qdrant.py` | Инициализация Qdrant коллекции |
| `scripts/clear_collection.py` | Очистка коллекции |
| `scripts/check_file_indexed.py` | Проверка индексации URL |
| `scripts/deep_analysis.py` | Глубокий анализ коллекции |
| `scripts/pipeline_text_flow.py` | Отладка pipeline |

---

**Версия документа**: 4.3.1
**Последнее обновление**: 9 октября 2024
**Статус**: Production Ready
### Категориальные метки из _category_.json

Каждый документ получает метаданные group_labels и groups_path, которые отражают структуру
docументации (дерево директорий Docusaurus) и используются для:

- **Бустинга** в поиске: если запрос содержит термины из раздела (например, "АРМ администратора" или "API"),
  система повышает релевантность документов из соответствующей ветки.
- **Форматирования источников**: в ответах ассистента ссылки сопровождаются последним элементом groups_path,
  чтобы пользователю было очевидно, в каком разделе находится документ.

Пример метаданных:

`
{
  "group_labels": ["API", "API edna Chat Center", "Треды"],
  "groups_path": ["API", "API edna Chat Center", "Треды"],
  "current_group": "Треды"
}
`

Синонимы и веса для бустинга конфигурируются через переменную окружения GROUP_BOOST_SYNONYMS (JSON),
либо используются значения по умолчанию (АРМ администратора, АРМ агента, АРМ супервайзера, API).
