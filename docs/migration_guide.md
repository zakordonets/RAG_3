# Руководство по миграции на новую архитектуру (v3.0.0)

## 📋 Обзор

Данное руководство поможет разработчикам адаптировать свой код к новой архитектуре RAG-системы после крупного рефакторинга v3.0.0.

## 🎯 Основные изменения

### 1. Модульная структура services/ (Этапы 1-5)

**До:**
```python
from app.services.embeddings import embed_dense
from app.services.bge_embeddings import embed_batch_optimized
from app.services.orchestrator import RAGOrchestrator
```

**После:**
```python
from app.services.core.embeddings import embed_dense, embed_batch_optimized
from app.services.infrastructure.orchestrator import RAGOrchestrator
```

### 2. UnifiedChunker (Этап 2)

**До:**
```python
from ingestion.chunkers.simple_chunker import chunk_text
from ingestion.chunkers.adaptive_chunker import adaptive_chunk_text
from ingestion.chunkers.semantic_chunker import SemanticChunker
```

**После:**
```python
from ingestion.chunkers import chunk_text, UnifiedChunker, ChunkingStrategy

# Использование
chunker = UnifiedChunker()
chunks = chunker.chunk_text(text, ChunkingStrategy.AUTO)
```

### 3. GPU Manager (Этап 3)

**До:**
```python
from app.gpu_utils import get_device, optimize_for_gpu
from app.gpu_utils_windows import get_gpu_info
```

**После:**
```python
from app.hardware import get_device, optimize_for_gpu, get_gpu_info
```

### 4. Объектно-ориентированные crawlers (Этап 5)

**До:**
```python
from ingestion.crawler import crawl_website
```

**После:**
```python
from ingestion.crawlers import CrawlerFactory, SourceConfig, SourceType

# Использование
source_config = SourceConfig(
    name="edna_docs",
    source_type=SourceType.DOCS_SITE,
    base_url="https://docs-chatcenter.edna.ru/"
)
crawler = CrawlerFactory.create_crawler(source_config)
pages = crawler.crawl(max_pages=100)
```

### 5. TextProcessor (Этап 6)

**До:**
```python
from app.text_utils import clean_text_for_processing
from app.logging_config import clean_text_for_logging
```

**После:**
```python
from app.utils import clean_text_for_processing, clean_text_for_logging

# Или через класс
from app.utils import TextProcessor
processor = TextProcessor()
cleaned_text = processor.clean_text_for_processing(text)
```

### 6. MetadataExtractor (Этап 7)

**До:**
```python
from app.sources_registry import extract_url_metadata
# Разбросанные функции в разных файлах
```

**После:**
```python
from app.utils import extract_url_metadata, MetadataExtractor

# Или через класс
extractor = MetadataExtractor()
metadata = extractor.extract_comprehensive_metadata(content, url)
```

### 7. Telegram Adapters (Этап 8)

**До:**
```python
from adapters.rate_limiter import RateLimiter
from adapters.telegram_enhanced import TelegramBot
from adapters.telegram_polling import run_polling_loop
```

**После:**
```python
from adapters.telegram import RateLimiter, TelegramBot, run_polling_loop

# Или отдельно
from adapters.telegram.bot import TelegramBot
from adapters.telegram.rate_limiter import RateLimiter
from adapters.telegram.polling import run_polling_loop
```

### 8. ContentLoader (Этап 9)

**До:**
```python
from ingestion.universal_loader import load_content_universal
```

**После:**
```python
from ingestion.content_loader import load_content_universal

# Или через класс
from ingestion.content_loader import ContentLoader
loader = ContentLoader()
result = loader.load_content(url, content)
```

### 9. Реорганизованная структура app/ (Этап 10)

**До:**
```python
from app.caching import get_cache_stats
from app.metrics import get_metrics_collector
from app.security import security_monitor
from app.tokenizer import count_tokens
from app.validation import validate_query_data
```

**После:**
```python
# Инфраструктурные компоненты
from app.infrastructure import get_cache_stats, get_metrics_collector, security_monitor

# Утилиты
from app.utils import count_tokens, validate_query_data

# Или отдельно
from app.infrastructure.caching import get_cache_stats
from app.infrastructure.metrics import get_metrics_collector
from app.utils.tokenizer import count_tokens
from app.utils.validation import validate_query_data
```

## 🔄 Дополнительные изменения (Этапы 6-10)

**До:**
```python
from ingestion.crawler import crawl, crawl_with_sitemap_progress
```

**После:**
```python
from ingestion.crawlers import CrawlerFactory
from app.sources_registry import SourceConfig, SourceType

# Создание crawler
config = SourceConfig(
    name="edna_docs",
    source_type=SourceType.DOCS_SITE,
    base_url="https://docs-chatcenter.edna.ru/"
)
crawler = CrawlerFactory.create_crawler(config)
results = crawler.crawl(max_pages=10)
```

## 🔄 Автоматическая миграция

### Проверка совместимости

Запустите скрипт проверки совместимости:

```bash
python scripts/check_compatibility.py
```

### Автоматическое обновление импортов

Для автоматического обновления импортов используйте:

```bash
python scripts/migrate_imports.py
```

## 📝 Ручная миграция

### 1. Обновление импортов services/

Найдите и замените все импорты:

```python
# Старые импорты
from app.services.embeddings import *
from app.services.bge_embeddings import *
from app.services.orchestrator import *
from app.services.retrieval import *
from app.services.rerank import *
from app.services.core.llm_router import *
from app.services.query_processing import *

# Новые импорты
from app.services.core.embeddings import *
from app.services.infrastructure.orchestrator import *
from app.services.search.retrieval import *
from app.services.search.rerank import *
from app.services.core.llm_router import *
from app.services.core.query_processing import *
```

### 2. Обновление chunkers

```python
# Старые импорты
from ingestion.chunkers.simple_chunker import chunk_text, text_hash
from ingestion.chunkers.adaptive_chunker import adaptive_chunk_text
from ingestion.chunkers.semantic_chunker import SemanticChunker

# Новые импорты
from ingestion.chunkers import chunk_text, text_hash, UnifiedChunker, ChunkingStrategy
```

### 3. Обновление GPU утилит

```python
# Старые импорты
from app.gpu_utils import get_device, optimize_for_gpu
from app.gpu_utils_windows import get_gpu_info
from app.gpu_utils_windows_fallback import clear_gpu_cache

# Новые импорты
from app.hardware import get_device, optimize_for_gpu, get_gpu_info, clear_gpu_cache
```

### 4. Обновление crawlers

```python
# Старые импорты
from ingestion.crawler import crawl, crawl_with_sitemap_progress, crawl_mkdocs_index

# Новые импорты
from ingestion.crawlers import CrawlerFactory
from app.sources_registry import SourceConfig, SourceType

# Создание crawler
config = SourceConfig(
    name="source_name",
    source_type=SourceType.DOCS_SITE,  # или другой тип
    base_url="https://example.com/"
)
crawler = CrawlerFactory.create_crawler(config)
results = crawler.crawl(max_pages=10, strategy="jina")
```

## 🧪 Тестирование после миграции

### Запуск тестов

```bash
# Все тесты
python -m pytest tests/ -v

# Конкретные тесты
python -m pytest tests/test_adaptive_chunker.py -v
python -m pytest tests/test_crawlers.py -v
python -m pytest tests/test_end_to_end_pipeline.py -v
```

### Проверка функциональности

```python
# Тест UnifiedChunker
from ingestion.chunkers import UnifiedChunker, ChunkingStrategy
chunker = UnifiedChunker()
chunks = chunker.chunk_text("Тестовый текст", ChunkingStrategy.AUTO)
print(f"Создано {len(chunks)} чанков")

# Тест GPU Manager
from app.hardware import get_device, get_gpu_info
device = get_device()
info = get_gpu_info()
print(f"Устройство: {device}, Информация: {info}")

# Тест Crawler Factory
from ingestion.crawlers import CrawlerFactory
from app.sources_registry import SourceConfig, SourceType
config = SourceConfig(name="test", source_type=SourceType.DOCS_SITE, base_url="https://example.com/")
crawler = CrawlerFactory.create_crawler(config)
print(f"Создан crawler: {type(crawler).__name__}")
```

## ⚠️ Потенциальные проблемы

### 1. Отсутствующие импорты

Если получаете ошибки импорта, проверьте:

```python
# Убедитесь, что используете правильные пути
from app.services.core.embeddings import embed_dense  # ✅
from app.services.embeddings import embed_dense       # ❌
```

### 2. Изменения в API

Некоторые функции могут иметь измененные сигнатуры:

```python
# Старый API
chunks = chunk_text(text, min_tokens=100, max_tokens=500)

# Новый API
from ingestion.chunkers import UnifiedChunker, ChunkingStrategy
chunker = UnifiedChunker()
chunks = chunker.chunk_text(text, ChunkingStrategy.SIMPLE, min_tokens=100, max_tokens=500)
```

### 3. Изменения в возвращаемых типах

```python
# Старый API - возвращал dict
page_data = {"url": url, "html": html, "text": text}

# Новый API - возвращает CrawlResult
from ingestion.crawlers import CrawlResult
result = CrawlResult(url=url, html=html, text=text, title="", metadata={})
```

## 🔧 Отладка

### Включение детального логирования

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Проверка импортов

```python
# Проверьте, что все импорты работают
try:
    from app.services.core.embeddings import embed_dense
    print("✅ embeddings импортируется")
except ImportError as e:
    print(f"❌ Ошибка импорта embeddings: {e}")
```

### Проверка функциональности

```python
# Тест основных функций
from ingestion.chunkers import chunk_text
from app.hardware import get_device
from ingestion.crawlers import CrawlerFactory

# Проверьте, что функции работают
chunks = chunk_text("Тест")
device = get_device()
print(f"Chunks: {len(chunks)}, Device: {device}")
```

## 📚 Дополнительные ресурсы

- **Полный отчет по рефакторингу**: [docs/refactoring_complete_report.md](refactoring_complete_report.md)
- **Архитектурная документация**: [docs/architecture.md](architecture.md)
- **Руководство разработчика**: [docs/development_guide.md](development_guide.md)
- **CHANGELOG**: [CHANGELOG.md](../CHANGELOG.md)

## 🆘 Получение помощи

Если у вас возникли проблемы с миграцией:

1. Проверьте [документацию по рефакторингу](refactoring_complete_report.md)
2. Запустите тесты для проверки совместимости
3. Проверьте примеры в [development_guide.md](development_guide.md)
4. Обратитесь к команде разработки

---

**Дата создания:** 2025-01-06
**Версия:** 1.0
**Статус:** Актуально ✅
