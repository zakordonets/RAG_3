# Добавление новых источников данных (v4.3.0)

Это руководство объясняет, как добавлять новые источники данных в RAG-систему edna Chat Center с использованием единой DAG архитектуры.

## 🎯 Обзор

Система v4.3.0 использует **единую DAG (Directed Acyclic Graph) архитектуру** для индексации данных из любых источников. Все источники обрабатываются через унифицированный конвейер.

## 🏗️ Архитектура индексации

### Единый Pipeline DAG

```
┌──────────────────────────────────────────────────────────────┐
│                    ЕДИНЫЙ PIPELINE DAG                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  📁 SOURCE ADAPTERS (ingestion/adapters/)                    │
│  ├─ DocusaurusAdapter - файловая система Docusaurus         │
│  ├─ WebsiteAdapter - веб-сайты (HTTP/HTML)                  │
│  └─ YourCustomAdapter - ваш источник                        │
│                                                              │
│  🔄 UNIFIED DAG (ingestion/pipeline/dag.py)                  │
│  Parse → Normalize → Chunk → Embed → Index                  │
│                                                              │
│  📝 NORMALIZERS (ingestion/normalizers/)                     │
│  ├─ DocusaurusNormalizer - очистка Docusaurus контента      │
│  ├─ HtmlNormalizer - очистка HTML                           │
│  └─ BaseNormalizer - базовая нормализация                   │
│                                                              │
│  🗄️ QDRANT WRITER (ingestion/pipeline/indexers/)             │
│  └─ QdrantWriter - запись в векторную БД                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Компоненты системы

1. **Конфигурация источников** (`app/config/sources_config.py`)
   - Реестр всех источников данных
   - Типы источников (SourceType enum)
   - Настройки для каждого источника

2. **Source Adapters** (`ingestion/adapters/`)
   - Извлечение данных из разных источников
   - Унифицированный интерфейс `SourceAdapter`
   - Генерация `RawDoc` объектов

3. **Normalizers** (`ingestion/normalizers/`)
   - Очистка и нормализация контента
   - Плагины для разных типов источников
   - Преобразование в `ParsedDoc`

4. **Pipeline Steps** (`ingestion/pipeline/`)
   - Parser - парсинг исходного контента
   - Chunker - разбиение на чанки
   - Embedder - генерация векторов (dense + sparse)
   - QdrantWriter - запись в Qdrant

5. **Единый entrypoint** (`ingestion/run.py`)
   - Запуск индексации для любых источников
   - CLI интерфейс
   - Управление процессом

6. **Конфигурация** (`ingestion/config.yaml`)
   - YAML конфигурация для источников
   - Настройки чанкинга, embeddings
   - Профили (development, production, testing)

## 📋 Поддерживаемые типы источников

### Реализованные типы

| Тип | Описание | Source Adapter | Пример |
|-----|----------|----------------|--------|
| **DOCS_SITE** | Docusaurus, MkDocs | `DocusaurusAdapter` | Локальная документация |
| **EXTERNAL** | Веб-сайты | `WebsiteAdapter` | https://docs.example.com |

### Поддерживаемые типы (для расширения)

В `app/config/sources_config.py` определены дополнительные типы:

```python
class SourceType(Enum):
    DOCS_SITE = "docs_site"          # Документационный сайт
    API_DOCS = "api_docs"            # API документация (Swagger, OpenAPI)
    BLOG = "blog"                    # Блог или новости
    FAQ = "faq"                      # FAQ страницы
    EXTERNAL = "external"            # Внешний сайт
    LOCAL_FOLDER = "local_folder"    # Локальная папка с документами
    FILE_COLLECTION = "file_collection"  # Коллекция файлов
    GIT_REPOSITORY = "git_repository"    # Git репозиторий
    CONFLUENCE = "confluence"        # Confluence wiki
    NOTION = "notion"               # Notion workspace
```

## 🚀 Быстрый старт: Добавление источника

### Способ 1: Использование существующих адаптеров

#### Для Docusaurus документации

```bash
# Индексация локальной Docusaurus документации
python ingestion/run.py docusaurus \
    --docs-root /path/to/docs \
    --site-base-url "https://docs.example.com" \
    --site-docs-prefix "/docs" \
    --reindex-mode full
```

#### Для веб-сайтов

```bash
# Индексация веб-сайта
python ingestion/run.py website \
    --seed-urls "https://example.com" "https://example.com/docs" \
    --base-url "https://example.com" \
    --max-depth 3 \
    --reindex-mode full
```

### Способ 2: Конфигурация в sources_config.py

Добавьте конфигурацию источника в `app/config/sources_config.py`:

```python
# В методе _load_default_sources()
self.register(SourceConfig(
    name="my_docs",
    base_url="https://docs.example.com/",
    source_type=SourceType.DOCS_SITE,
    strategy="jina",
    use_cache=True,
    sitemap_path="/sitemap.xml",
    seed_urls=[
        "https://docs.example.com/",
        "https://docs.example.com/docs/",
    ],
    crawl_deny_prefixes=[
        "https://docs.example.com/api/",
        "https://docs.example.com/admin/",
    ],
    metadata_patterns={
        r'/docs/': {'section': 'docs', 'user_role': 'all'},
        r'/api/': {'section': 'api', 'user_role': 'developer'},
        r'/blog/': {'section': 'blog', 'user_role': 'all'},
    },
    timeout_s=30,
    crawl_delay_ms=1000,
    user_agent="RAGBot/1.0",
))
```

### Способ 3: YAML конфигурация

Добавьте источник в `ingestion/config.yaml`:

```yaml
sources:
  my_custom_source:
    enabled: true
    type: "website"
    base_url: "https://example.com"
    seed_urls:
      - "https://example.com/"
      - "https://example.com/docs/"

    # Настройки чанкинга
    chunk:
      max_tokens: 300
      min_tokens: 150
      overlap_base: 50

    # Настройки индексации
    indexing:
      upsert: true
      delete_missing: false
```

## 🛠️ Создание нового Source Adapter

Если существующие адаптеры не подходят, создайте свой собственный.

### Шаг 1: Создайте класс адаптера

```python
# ingestion/adapters/my_source.py
from typing import Iterable, Optional
from pathlib import Path
from loguru import logger

from ingestion.adapters.base import SourceAdapter, RawDoc

class MySourceAdapter(SourceAdapter):
    """
    Адаптер для вашего источника данных.

    Пример: API, база данных, внешний сервис и т.д.
    """

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        max_pages: Optional[int] = None
    ):
        """
        Инициализация адаптера.

        Args:
            api_url: URL API
            api_key: API ключ для аутентификации
            max_pages: Максимальное количество страниц
        """
        self.api_url = api_url
        self.api_key = api_key
        self.max_pages = max_pages

    def iter_documents(self) -> Iterable[RawDoc]:
        """
        Генерирует документы из источника.

        Yields:
            RawDoc: Сырой документ для обработки
        """
        logger.info(f"📥 Получение документов из {self.api_url}")

        # Ваша логика получения данных
        documents = self._fetch_documents()

        count = 0
        for doc in documents:
            if self.max_pages and count >= self.max_pages:
                logger.info(f"✋ Достигнут лимит: {self.max_pages} документов")
                break

            # Создаем RawDoc объект
            yield RawDoc(
                url=doc['url'],
                title=doc.get('title', ''),
                content=doc['content'],
                metadata={
                    'source': 'my_source',
                    'author': doc.get('author'),
                    'updated_at': doc.get('updated_at'),
                    # Добавьте свои метаданные
                }
            )

            count += 1

        logger.success(f"✅ Получено {count} документов")

    def _fetch_documents(self):
        """Получает документы из вашего источника"""
        # Ваша логика: HTTP запросы, чтение БД и т.д.
        import requests

        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        response = requests.get(
            f"{self.api_url}/documents",
            headers=headers
        )
        response.raise_for_status()

        return response.json()['documents']
```

### Шаг 2: Создайте Normalizer (опционально)

Если ваш источник требует специфичной очистки контента:

```python
# ingestion/normalizers/my_source.py
import re
from ingestion.normalizers.base import BaseNormalizer
from ingestion.adapters.base import ParsedDoc

class MySourceNormalizer(BaseNormalizer):
    """Нормализатор для вашего источника"""

    def get_step_name(self) -> str:
        return "MySourceNormalizer"

    def process(self, docs):
        """Обрабатывает документы"""
        for doc in docs:
            if not isinstance(doc, ParsedDoc):
                yield doc
                continue

            # Ваша логика очистки
            cleaned_content = self._clean_content(doc.content)

            # Создаем новый документ с очищенным контентом
            yield ParsedDoc(
                url=doc.url,
                title=doc.title,
                content=cleaned_content,
                metadata=doc.metadata
            )

    def _clean_content(self, content: str) -> str:
        """Очищает контент"""
        # Удаляем специфичные маркеры
        content = re.sub(r'\[SPECIAL_MARKER\]', '', content)

        # Удаляем лишние пробелы
        content = re.sub(r'\s+', ' ', content).strip()

        return content
```

### Шаг 3: Создайте функцию DAG

Добавьте функцию для создания DAG в `ingestion/run.py`:

```python
def create_my_source_dag(config: Dict[str, Any]) -> PipelineDAG:
    """Создает DAG для вашего источника."""
    steps = [
        Parser(),
        MySourceNormalizer(),  # Ваш нормализатор (опционально)
        BaseNormalizer(),       # Базовая нормализация
        UnifiedChunkerStep(
            max_tokens=config.get("chunk_max_tokens", 300),
            min_tokens=config.get("chunk_min_tokens", 150),
            overlap_base=config.get("chunk_overlap_base", 50),
        ),
        Embedder(batch_size=config.get("batch_size", 16)),
        QdrantWriter(collection_name=config.get("collection_name", CONFIG.qdrant_collection))
    ]

    return PipelineDAG(steps)
```

### Шаг 4: Интегрируйте в run.py

Добавьте обработку в функцию `run_unified_indexing()`:

```python
def run_unified_indexing(
    source_type: str,
    config: Dict[str, Any],
    reindex_mode: str = "changed",
    clear_collection: bool = False
) -> Dict[str, Any]:
    """Запуск индексации"""

    # ... существующий код ...

    try:
        # Создаем адаптер источника
        if source_type == "docusaurus":
            adapter = DocusaurusAdapter(...)
            dag = create_docusaurus_dag(config)

        elif source_type == "website":
            adapter = WebsiteAdapter(...)
            dag = create_website_dag(config)

        elif source_type == "my_source":  # ВАШ ИСТОЧНИК
            adapter = MySourceAdapter(
                api_url=config["api_url"],
                api_key=config.get("api_key"),
                max_pages=config.get("max_pages")
            )
            dag = create_my_source_dag(config)

        else:
            raise ValueError(f"Неподдерживаемый тип источника: {source_type}")

        # Запускаем обработку
        documents = adapter.iter_documents()
        stats = dag.run(documents)

        return stats
```

### Шаг 5: Добавьте CLI команду (опционально)

Добавьте парсер аргументов в `ingestion/run.py`:

```python
# В функции main()
elif args.source == "my_source":
    config = {
        "api_url": args.api_url,
        "api_key": args.api_key,
        "max_pages": args.max_pages,
        "chunk_max_tokens": args.chunk_max_tokens or CONFIG.chunk_max_tokens,
        "chunk_min_tokens": args.chunk_min_tokens or CONFIG.chunk_min_tokens,
        "collection_name": CONFIG.qdrant_collection,
    }

    stats = run_unified_indexing(
        source_type="my_source",
        config=config,
        reindex_mode=args.reindex_mode,
        clear_collection=args.clear_collection
    )

# Добавьте аргументы парсера
my_source_parser = subparsers.add_parser("my_source", help="Индексация из вашего источника")
my_source_parser.add_argument("--api-url", required=True, help="URL API")
my_source_parser.add_argument("--api-key", help="API ключ")
my_source_parser.add_argument("--max-pages", type=int, help="Максимум страниц")
```

## 📝 Примеры конфигураций

### Документационный сайт (Docusaurus)

```python
SourceConfig(
    name="docusaurus_docs",
    base_url="https://docs.example.com/",
    source_type=SourceType.DOCS_SITE,
    strategy="jina",
    use_cache=True,
    sitemap_path="/sitemap.xml",
    metadata_patterns={
        r'/docs/guide/': {'section': 'guide', 'page_type': 'guide'},
        r'/docs/api/': {'section': 'api', 'page_type': 'api'},
        r'/docs/faq/': {'section': 'faq', 'page_type': 'faq'},
    }
)
```

**Использование:**
```bash
python ingestion/run.py docusaurus \
    --docs-root /path/to/docusaurus/docs \
    --site-base-url "https://docs.example.com" \
    --reindex-mode full
```

### Внешний веб-сайт

```python
SourceConfig(
    name="external_site",
    base_url="https://example.com/",
    source_type=SourceType.EXTERNAL,
    strategy="jina",
    use_cache=True,
    seed_urls=[
        "https://example.com/",
        "https://example.com/blog/",
    ],
    crawl_deny_prefixes=[
        "https://example.com/admin/",
        "https://example.com/api/",
    ],
    metadata_patterns={
        r'/blog/': {'section': 'blog', 'page_type': 'blog'},
    }
)
```

**Использование:**
```bash
python ingestion/run.py website \
    --seed-urls "https://example.com" \
    --base-url "https://example.com" \
    --max-depth 2 \
    --reindex-mode full
```

### API документация

```python
SourceConfig(
    name="swagger_api",
    base_url="https://api.example.com/docs/",
    source_type=SourceType.API_DOCS,
    strategy="http",
    use_cache=True,
    custom_headers={
        "Authorization": "Bearer YOUR_TOKEN",
    },
    metadata_patterns={
        r'/docs/': {'section': 'api', 'user_role': 'developer', 'page_type': 'api'},
    }
)
```

## 🧪 Тестирование

### Unit тесты

```python
# tests/test_my_source_adapter.py
import pytest
from ingestion.adapters.my_source import MySourceAdapter
from ingestion.adapters.base import RawDoc

def test_my_source_adapter_init():
    """Тест инициализации адаптера"""
    adapter = MySourceAdapter(
        api_url="https://api.example.com",
        api_key="test_key",
        max_pages=10
    )

    assert adapter.api_url == "https://api.example.com"
    assert adapter.api_key == "test_key"
    assert adapter.max_pages == 10

def test_my_source_adapter_iter_documents(mocker):
    """Тест генерации документов"""
    # Mock внешний API
    mock_fetch = mocker.patch.object(
        MySourceAdapter,
        '_fetch_documents',
        return_value=[
            {
                'url': 'https://example.com/doc1',
                'title': 'Document 1',
                'content': 'Content 1',
            },
            {
                'url': 'https://example.com/doc2',
                'title': 'Document 2',
                'content': 'Content 2',
            }
        ]
    )

    adapter = MySourceAdapter(api_url="https://api.example.com")
    documents = list(adapter.iter_documents())

    assert len(documents) == 2
    assert all(isinstance(doc, RawDoc) for doc in documents)
    assert documents[0].url == 'https://example.com/doc1'
    assert documents[0].title == 'Document 1'
```

### Интеграционные тесты

```python
# tests/test_my_source_integration.py
import pytest
from ingestion.adapters.my_source import MySourceAdapter
from ingestion.pipeline.dag import PipelineDAG
from ingestion.run import create_my_source_dag

@pytest.mark.integration
def test_full_pipeline_my_source():
    """Тест полного пайплайна индексации"""
    # Конфигурация
    config = {
        "api_url": "https://api.example.com",
        "chunk_max_tokens": 200,
        "chunk_min_tokens": 100,
        "collection_name": "test_collection",
    }

    # Создаем адаптер и DAG
    adapter = MySourceAdapter(
        api_url=config["api_url"],
        max_pages=5  # Ограничиваем для теста
    )
    dag = create_my_source_dag(config)

    # Запускаем обработку
    documents = adapter.iter_documents()
    stats = dag.run(documents)

    # Проверяем результаты
    assert stats["total_docs"] > 0
    assert stats["processed_docs"] > 0
    assert stats["failed_docs"] == 0
```

### Тестовый скрипт

```python
#!/usr/bin/env python3
"""Тест нового источника данных"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.adapters.my_source import MySourceAdapter
from loguru import logger

def test_adapter():
    """Тестирует адаптер"""
    logger.info("🧪 Тестирование MySourceAdapter...")

    # Создаем адаптер
    adapter = MySourceAdapter(
        api_url="https://api.example.com",
        api_key="your_api_key",
        max_pages=5
    )

    # Получаем документы
    documents = list(adapter.iter_documents())

    logger.info(f"📊 Получено документов: {len(documents)}")

    # Выводим первые 3 документа
    for i, doc in enumerate(documents[:3], 1):
        logger.info(f"\n📄 Документ {i}:")
        logger.info(f"  URL: {doc.url}")
        logger.info(f"  Title: {doc.title}")
        logger.info(f"  Content length: {len(doc.content)} chars")
        logger.info(f"  Metadata: {doc.metadata}")

if __name__ == "__main__":
    test_adapter()
```

## 📊 Мониторинг и отладка

### Логирование

Система автоматически логирует процесс индексации:

```python
# Включите детальное логирование
import logging
from loguru import logger

# Установите уровень DEBUG
logger.add("debug.log", level="DEBUG")
```

### Проверка прогресса

```bash
# Запуск с детальным логированием
python ingestion/run.py my_source \
    --api-url "https://api.example.com" \
    --max-pages 10 \
    --reindex-mode full

# Вывод:
# 📊 Подготовка документов...
# 📄 Найдено 10 документов для обработки
# 📄 Обработано 5/10 документов (50.0%)
# 📄 Обработано 10/10 документов (100.0%)
# ✅ Индексация завершена успешно
```

### Метрики

После индексации доступны метрики:

```python
stats = run_unified_indexing(...)

print(f"Всего документов: {stats['total_docs']}")
print(f"Обработано: {stats['processed_docs']}")
print(f"Ошибок: {stats['failed_docs']}")
print(f"Время: {stats.get('duration', 'N/A')}s")
```

### Проверка в Qdrant

```bash
# Проверить количество точек в коллекции
curl http://localhost:6333/collections/chatcenter_docs

# Поиск по коллекции
curl -X POST http://localhost:6333/collections/chatcenter_docs/points/search \
  -H "Content-Type: application/json" \
  -d '{"vector": [...], "limit": 5}'
```

## 🎯 Лучшие практики

### 1. Обработка ошибок

```python
def iter_documents(self) -> Iterable[RawDoc]:
    """Генерирует документы с обработкой ошибок"""
    try:
        documents = self._fetch_documents()
    except Exception as e:
        logger.error(f"❌ Ошибка получения документов: {e}")
        return

    for doc in documents:
        try:
            yield RawDoc(
                url=doc['url'],
                title=doc.get('title', ''),
                content=doc['content'],
                metadata=doc.get('metadata', {})
            )
        except KeyError as e:
            logger.warning(f"⚠️ Пропущен документ из-за отсутствия поля: {e}")
            continue
        except Exception as e:
            logger.error(f"❌ Ошибка обработки документа {doc.get('url')}: {e}")
            continue
```

### 2. Кеширование

```python
import hashlib
import json
from pathlib import Path

class MySourceAdapter(SourceAdapter):
    def __init__(self, api_url: str, use_cache: bool = True):
        self.api_url = api_url
        self.use_cache = use_cache
        self.cache_dir = Path("cache/my_source")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, doc_id: str) -> Path:
        """Путь к кешу документа"""
        cache_key = hashlib.md5(doc_id.encode()).hexdigest()
        return self.cache_dir / f"{cache_key}.json"

    def _fetch_documents(self):
        """Получает документы с кешированием"""
        cache_path = self.cache_dir / "documents.json"

        # Проверяем кеш
        if self.use_cache and cache_path.exists():
            logger.info("📦 Загрузка из кеша")
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Получаем данные
        documents = self._fetch_from_api()

        # Сохраняем в кеш
        if self.use_cache:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, ensure_ascii=False, indent=2)

        return documents
```

### 3. Инкрементальная индексация

```python
def iter_documents(self) -> Iterable[RawDoc]:
    """Генерирует только измененные документы"""
    from ingestion.state.state_manager import get_state_manager

    state_manager = get_state_manager()

    for doc in self._fetch_documents():
        doc_id = doc['url']
        current_hash = hashlib.md5(doc['content'].encode()).hexdigest()

        # Проверяем, изменился ли документ
        if state_manager.is_document_changed(doc_id, current_hash):
            logger.info(f"📄 Документ изменен: {doc_id}")
            yield RawDoc(...)
        else:
            logger.debug(f"⏭️  Документ не изменен: {doc_id}")
```

### 4. Батчевая обработка

```python
def iter_documents(self) -> Iterable[RawDoc]:
    """Генерирует документы батчами"""
    batch_size = 10

    documents = self._fetch_documents()
    batch = []

    for doc in documents:
        batch.append(doc)

        if len(batch) >= batch_size:
            # Обрабатываем батч
            for processed_doc in self._process_batch(batch):
                yield processed_doc
            batch = []

    # Обрабатываем оставшиеся
    if batch:
        for processed_doc in self._process_batch(batch):
            yield processed_doc
```

### 5. Rate Limiting

```python
import time

class MySourceAdapter(SourceAdapter):
    def __init__(self, api_url: str, rate_limit_delay: float = 1.0):
        self.api_url = api_url
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

    def _fetch_documents(self):
        """Получает документы с rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        # Делаем запрос
        response = requests.get(self.api_url)
        self.last_request_time = time.time()

        return response.json()
```

## ❓ Устранение неполадок

### Частые проблемы

#### 1. "No documents found"

**Причина**: Адаптер не возвращает документы

**Решение**:
```python
# Добавьте отладочное логирование
def iter_documents(self):
    documents = self._fetch_documents()
    logger.info(f"📊 Получено {len(documents)} документов")

    for doc in documents:
        logger.debug(f"📄 Обрабатывается: {doc.get('url')}")
        yield RawDoc(...)
```

#### 2. "ImportError: cannot import name 'MySourceAdapter'"

**Причина**: Неправильный путь импорта

**Решение**:
```python
# В ingestion/run.py
from ingestion.adapters.my_source import MySourceAdapter

# Убедитесь, что __init__.py существует в ingestion/adapters/
```

#### 3. "Qdrant connection error"

**Причина**: Qdrant не запущен или неправильный URL

**Решение**:
```bash
# Проверьте Qdrant
curl http://localhost:6333/collections

# Запустите Qdrant
docker-compose up -d qdrant
```

#### 4. "Memory error during indexing"

**Причина**: Слишком большие батчи или документы

**Решение**:
```bash
# Уменьшите размер батча
python ingestion/run.py my_source \
    --chunk-max-tokens 200 \  # Вместо 600
    --batch-size 8 \          # Вместо 16
    --max-pages 100           # Ограничьте количество
```

## 📚 Дополнительные ресурсы

### Документация

- [Architecture](architecture.md) - Общая архитектура системы
- [Development Guide](development_guide.md) - Руководство разработчика
- [Quickstart](quickstart.md) - Быстрый старт

### Примеры кода

- `ingestion/adapters/docusaurus.py` - Пример адаптера для Docusaurus
- `ingestion/adapters/website.py` - Пример адаптера для веб-сайтов
- `ingestion/normalizers/docusaurus.py` - Пример нормализатора
- `tests/test_unified_dag.py` - Примеры тестов

### Полезные команды

```bash
# Просмотр всех доступных источников
python -c "from app.config.sources_config import sources_registry; print(sources_registry.list_all())"

# Информация о конкретном источнике
python -c "from app.config.sources_config import get_source_config; print(get_source_config('edna_docs'))"

# Тестирование адаптера
python -m pytest tests/test_my_source_adapter.py -v

# Запуск с отладкой
python -m pdb ingestion/run.py my_source --api-url "..."
```

## 🎓 Заключение

Единая DAG архитектура v4.3.0 упрощает добавление новых источников данных. Основные шаги:

1. **Создайте Source Adapter** - наследуйте от `SourceAdapter`
2. **Реализуйте iter_documents()** - генерируйте `RawDoc` объекты
3. **Создайте DAG функцию** - определите шаги обработки
4. **Интегрируйте в run.py** - добавьте обработку в `run_unified_indexing()`
5. **Протестируйте** - напишите unit и integration тесты

Следуя этому руководству, вы сможете индексировать данные из любых источников!

---

**Последнее обновление**: Октябрь 2025
**Версия**: v4.3.0
**Статус**: ✅ Актуально
