# Добавление новых источников данных

Это руководство объясняет, как добавлять новые источники данных в систему RAG.

## Обзор архитектуры

Система использует модульную архитектуру с разделением на:
- **Конфигурацию источников** (`app/sources_registry.py`) - описание источников
- **Краулеры** (`ingestion/crawlers/`) - логика извлечения данных
- **Парсеры** (`ingestion/processors/`) - обработка контента
- **Индексацию** (`ingestion/indexer.py`) - сохранение в векторную БД

## Поддерживаемые типы источников

### 1. Веб-сайты (DOCS_SITE, API_DOCS, BLOG, FAQ, EXTERNAL)
- Документационные сайты (Docusaurus, MkDocs)
- API документация (Swagger, OpenAPI)
- Блоги и новости
- FAQ страницы
- Внешние сайты

### 2. Локальные файлы (LOCAL_FOLDER, FILE_COLLECTION)
- Папки с Markdown файлами
- HTML документы
- Текстовые файлы
- RST файлы

### 3. Планируемые типы
- Git репозитории
- Confluence wiki
- Notion workspace

## Как добавить новый источник данных

### Шаг 1: Определите тип источника

Выберите подходящий тип из `SourceType` enum:

```python
from app.sources_registry import SourceType

# Для веб-сайта
source_type = SourceType.DOCS_SITE

# Для локальной папки
source_type = SourceType.LOCAL_FOLDER
```

### Шаг 2: Создайте конфигурацию

Добавьте конфигурацию в `app/sources_registry.py`:

```python
# В методе _load_default_sources()
self.register(SourceConfig(
    name="my_new_source",
    base_url="https://example.com/",
    source_type=SourceType.DOCS_SITE,
    strategy="jina",  # или "http", "auto"
    use_cache=True,
    sitemap_path="/sitemap.xml",
    seed_urls=[
        "https://example.com/",
        "https://example.com/docs/",
    ],
    crawl_deny_prefixes=[
        "https://example.com/api/",
        "https://example.com/admin/",
    ],
    metadata_patterns={
        r'/docs/': {'section': 'docs', 'user_role': 'all'},
        r'/api/': {'section': 'api', 'user_role': 'developer'},
    },
    # Дополнительные параметры
    timeout_s=30,
    crawl_delay_ms=1000,
    user_agent="MyBot/1.0",
))
```

### Шаг 3: Настройте метаданные (опционально)

Добавьте паттерны для извлечения метаданных:

```python
metadata_patterns={
    # URL паттерн -> метаданные
    r'/docs/start/': {
        'section': 'start',
        'user_role': 'all',
        'page_type': 'guide'
    },
    r'/docs/api/': {
        'section': 'api',
        'user_role': 'developer',
        'page_type': 'api'
    },
    r'/blog/': {
        'section': 'news',
        'user_role': 'all',
        'page_type': 'blog'
    }
}
```

### Шаг 4: Протестируйте источник

Создайте тестовый скрипт:

```python
#!/usr/bin/env python3
"""Тест нового источника данных"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.sources_registry import get_source_config
from ingestion.crawlers import CrawlerFactory

def test_new_source():
    # Получаем конфигурацию
    config = get_source_config("my_new_source")

    # Создаем краулер
    crawler = CrawlerFactory.create_crawler(config)

    # Тестируем получение URL
    urls = crawler.get_available_urls()
    print(f"Found {len(urls)} URLs")

    # Тестируем краулинг (ограничиваем 5 страницами)
    results = crawler.crawl(max_pages=5)

    print(f"Crawled {len(results)} pages")
    for result in results:
        if result.error:
            print(f"❌ {result.url}: {result.error}")
        else:
            print(f"✅ {result.url}: {result.title} ({len(result.text)} chars)")

if __name__ == "__main__":
    test_new_source()
```

## Примеры конфигураций

### Документационный сайт (Docusaurus)

```python
SourceConfig(
    name="docusaurus_docs",
    base_url="https://docs.example.com/",
    source_type=SourceType.DOCS_SITE,
    strategy="jina",
    use_cache=True,
    sitemap_path="/sitemap.xml",
    crawl_deny_prefixes=[
        "https://docs.example.com/api/",
        "https://docs.example.com/admin/",
    ],
    metadata_patterns={
        r'/docs/': {'section': 'docs', 'user_role': 'all'},
        r'/api/': {'section': 'api', 'user_role': 'developer'},
    }
)
```

### Локальная папка с документами

```python
SourceConfig(
    name="local_docs",
    base_url="file:///path/to/docs/",
    source_type=SourceType.LOCAL_FOLDER,
    local_path="/path/to/docs/",
    file_extensions=['.md', '.rst', '.txt'],
    strategy="auto",
    use_cache=True
)
```

### API документация (Swagger)

```python
SourceConfig(
    name="swagger_api",
    base_url="https://api.example.com/docs/",
    source_type=SourceType.API_DOCS,
    strategy="http",
    use_cache=True,
    custom_headers={
        "Authorization": "Bearer your-token",
    },
    metadata_patterns={
        r'/docs/': {'section': 'api', 'user_role': 'developer'},
    }
)
```

### Внешний блог

```python
SourceConfig(
    name="external_blog",
    base_url="https://blog.example.com/",
    source_type=SourceType.BLOG,
    strategy="jina",
    use_cache=True,
    crawl_delay_ms=2000,  # Более медленный краулинг
    user_agent="MyBot/1.0 (+https://mycompany.com/bot)",
    metadata_patterns={
        r'/': {'section': 'blog', 'user_role': 'all'},
    }
)
```

## Создание кастомного краулера

Если стандартные краулеры не подходят, создайте свой:

### 1. Создайте класс краулера

```python
# ingestion/crawlers/custom_crawler.py
from .base_crawler import BaseCrawler, CrawlResult
from app.sources_registry import SourceConfig

class CustomCrawler(BaseCrawler):
    def get_available_urls(self) -> List[str]:
        # Ваша логика получения URL
        pass

    def crawl(self, max_pages: Optional[int] = None) -> List[CrawlResult]:
        # Ваша логика краулинга
        pass
```

### 2. Зарегистрируйте краулер

```python
# В app/sources_registry.py или в инициализации
from ingestion.crawlers import CrawlerFactory
from ingestion.crawlers.custom_crawler import CustomCrawler
from app.sources_registry import SourceType

CrawlerFactory.register_crawler(SourceType.CUSTOM, CustomCrawler)
```

## Тестирование

### Создайте unit тесты

```python
# tests/test_crawlers.py
import pytest
from app.sources_registry import SourceConfig, SourceType
from ingestion.crawlers import CrawlerFactory

def test_website_crawler():
    config = SourceConfig(
        name="test_site",
        base_url="https://example.com/",
        source_type=SourceType.DOCS_SITE,
    )

    crawler = CrawlerFactory.create_crawler(config)
    assert isinstance(crawler, WebsiteCrawler)

    # Тестируем получение URL
    urls = crawler.get_available_urls()
    assert isinstance(urls, list)

def test_local_folder_crawler():
    config = SourceConfig(
        name="test_folder",
        base_url="file:///test/",
        source_type=SourceType.LOCAL_FOLDER,
        local_path="/test/path",
    )

    crawler = CrawlerFactory.create_crawler(config)
    assert isinstance(crawler, LocalFolderCrawler)
```

### Создайте интеграционные тесты

```python
# tests/test_integration.py
def test_full_crawl_pipeline():
    # Тест полного пайплайна: краулинг -> парсинг -> индексация
    pass
```

## Мониторинг и отладка

### Логирование

Краулеры автоматически логируют свою работу:

```python
# Включите детальное логирование
import logging
logging.getLogger("ingestion.crawlers").setLevel(logging.DEBUG)
```

### Метрики

Система собирает метрики:
- Количество обработанных страниц
- Время выполнения
- Ошибки краулинга
- Размер кеша

### Отладка проблем

1. **Проверьте конфигурацию**:
   ```python
   config = get_source_config("your_source")
   print(config)
   ```

2. **Тестируйте получение URL**:
   ```python
   crawler = CrawlerFactory.create_crawler(config)
   urls = crawler.get_available_urls()
   print(f"Found {len(urls)} URLs")
   ```

3. **Тестируйте краулинг одной страницы**:
   ```python
   results = crawler.crawl(max_pages=1)
   print(results[0])
   ```

## Лучшие практики

1. **Используйте кеширование** для больших источников
2. **Настройте разумные задержки** между запросами
3. **Добавляйте deny_prefixes** для исключения ненужных страниц
4. **Тестируйте на небольшом количестве страниц** перед полным краулингом
5. **Мониторьте логи** на предмет ошибок
6. **Используйте подходящую стратегию** (jina для сложных сайтов, http для простых)

## Устранение неполадок

### Частые проблемы

1. **"No URLs found"** - проверьте sitemap_path и seed_urls
2. **"HTTP 403/429"** - увеличьте crawl_delay_ms, проверьте User-Agent
3. **"Timeout errors"** - увеличьте timeout_s
4. **"Empty content"** - проверьте селекторы в WebsiteCrawler

### Получение помощи

1. Проверьте логи системы
2. Создайте минимальный тестовый случай
3. Обратитесь к документации конкретного типа источника
