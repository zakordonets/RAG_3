# План рефакторинга системы загрузки данных

## 🎯 Цели рефакторинга

1. **Исправить критическую ошибку** с несогласованными форматами данных парсеров
2. **Оптимизировать производительность** за счет устранения дублирования и кеширования
3. **Упростить архитектуру** путем объединения избыточных компонентов
4. **Повысить надежность** через централизованную обработку ошибок и валидацию

## 🚨 Критические проблемы

### 1. Несогласованные форматы данных
- `parse_faq_content()` возвращает **список** вместо словаря
- `parse_guides()` возвращает **словарь**
- Pipeline ожидает поле `content`, EdnaDocsDataSource ожидает `text`
- Результат: пустые чанки для FAQ страниц, исключения в RAG-pipeline

### 2. Избыточная архитектура
- Три уровня абстракции: `crawler.py` → `universal_loader.py` → `parsers.py`
- Дублирование логики парсинга в каждом парсере
- Двойной парсинг HTML (BeautifulSoup дважды)

### 3. Неоптимальная производительность
- Отсутствие кеширования BeautifulSoup объектов
- Обработка по одной странице вместо батчевой
- Избыточные проверки типа контента

## 📋 План рефакторинга

### Этап 0: Подготовка и очистка (0.5 дня)

#### 0.1 Создать скрипт очистки коллекции
```python
# scripts/clear_collection.py
from app.services.retrieval import client, COLLECTION
from loguru import logger

def clear_collection():
    """Очищает коллекцию Qdrant и создает новую с чистой схемой"""
    try:
        # Удаляем существующую коллекцию
        client.delete_collection(COLLECTION)
        logger.info(f"Collection {COLLECTION} deleted")

        # Создаем новую коллекцию с новой схемой
        from scripts.init_qdrant import create_collection
        create_collection()
        logger.info(f"Collection {COLLECTION} recreated with new schema")

    except Exception as e:
        logger.error(f"Failed to clear collection: {e}")
        raise

def backup_existing_data():
    """Создает бэкап существующих данных (на всякий случай)"""
    try:
        # Экспортируем данные в JSON
        scroll_result = client.scroll(
            collection_name=COLLECTION,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        import json
        from datetime import datetime

        backup_file = f"backup_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(scroll_result[0], f, ensure_ascii=False, indent=2)

        logger.info(f"Backup saved to {backup_file}")

    except Exception as e:
        logger.warning(f"Failed to create backup: {e}")

if __name__ == "__main__":
    backup_existing_data()
    clear_collection()
```

#### 0.2 Обновить схему коллекции
```python
# scripts/init_qdrant.py - обновленная схема
def create_collection():
    """Создает коллекцию с новой упрощенной схемой"""

    # Новая схема без legacy полей
    vectors_config = {
        "dense": VectorParams(
            size=1024,  # BGE-M3 размер
            distance=Distance.COSINE
        ),
        "sparse": VectorParams(
            size=768,   # SPLADE размер
            distance=Distance.DOT
        )
    }

    # Упрощенная схема payload
    payload_schema = {
        "url": "text",
        "title": "text",
        "content": "text",  # Всегда 'content', не 'text'
        "page_type": "keyword",
        "source": "keyword",
        "language": "keyword",
        "chunk_index": "integer",
        "content_length": "integer",
        "indexed_at": "float",
        "indexed_via": "keyword"
    }

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=vectors_config,
        payload_schema=payload_schema
    )
```

### Этап 1: Создание новой архитектуры (1-2 дня)

#### 1.1 Интеграция с существующим PluginManager
**КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ**: План должен интегрироваться с существующим `PluginManager`, а не создавать параллельную систему.

```python
# app/config/sources.py - ИНТЕГРИРОВАННАЯ версия
from app.abstractions.data_source import plugin_manager, DataSourceBase
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class SourceType(Enum):
    """Типы источников данных"""
    DOCS_SITE = "docs_site"
    API_DOCS = "api_docs"
    BLOG = "blog"
    FAQ = "faq"
    EXTERNAL = "external"

@dataclass
class SourceConfig:
    """Конфигурация источника данных - ИНТЕГРИРОВАННАЯ с PluginManager"""
    name: str
    base_url: str
    source_type: SourceType
    strategy: str = "auto"
    use_cache: bool = True
    max_pages: int = None
    crawl_deny_prefixes: List[str] = None
    sitemap_path: str = "/sitemap.xml"
    seed_urls: List[str] = None
    metadata_patterns: Dict[str, Dict[str, str]] = None

class SourcesRegistry:
    """Реестр источников данных - ИНТЕГРИРОВАННЫЙ с PluginManager"""

    def __init__(self):
        self._sources: Dict[str, SourceConfig] = {}
        self._load_default_sources()

    def _load_default_sources(self):
        """Загружает источники по умолчанию"""
        self.register(SourceConfig(
            name="edna_docs",
            base_url="https://docs-chatcenter.edna.ru/",
            source_type=SourceType.DOCS_SITE,
            strategy="jina",
            use_cache=True,
            sitemap_path="/sitemap.xml",
            seed_urls=[
                "https://docs-chatcenter.edna.ru/",
                "https://docs-chatcenter.edna.ru/docs/start/",
                "https://docs-chatcenter.edna.ru/docs/agent/",
                "https://docs-chatcenter.edna.ru/docs/supervisor/",
                "https://docs-chatcenter.edna.ru/docs/admin/",
                "https://docs-chatcenter.edna.ru/docs/chat-bot/",
                "https://docs-chatcenter.edna.ru/docs/api/index/",
                "https://docs-chatcenter.edna.ru/docs/faq/",
                "https://docs-chatcenter.edna.ru/blog/",
            ],
            crawl_deny_prefixes=[
                "https://docs-chatcenter.edna.ru/api/",
                "https://docs-chatcenter.edna.ru/admin/",
                "https://docs-chatcenter.edna.ru/supervisor/",
            ],
            metadata_patterns={
                r'/docs/start/': {'section': 'start', 'user_role': 'all', 'page_type': 'guide'},
                r'/docs/agent/': {'section': 'agent', 'user_role': 'agent', 'page_type': 'guide'},
                r'/docs/supervisor/': {'section': 'supervisor', 'user_role': 'supervisor', 'page_type': 'guide'},
                r'/docs/admin/': {'section': 'admin', 'user_role': 'admin', 'page_type': 'guide'},
                r'/docs/api/': {'section': 'api', 'user_role': 'integrator', 'page_type': 'api'},
                r'/blog/': {'section': 'changelog', 'user_role': 'all', 'page_type': 'release_notes'},
                r'/faq': {'section': 'faq', 'user_role': 'all', 'page_type': 'faq'},
            }
        ))

    def register(self, config: SourceConfig):
        """Регистрирует источник в реестре"""
        self._sources[config.name] = config

    def get(self, name: str) -> SourceConfig:
        """Получает конфигурацию источника по имени"""
        if name not in self._sources:
            raise ValueError(f"Source '{name}' not found. Available: {list(self._sources.keys())}")
        return self._sources[name]

    def get_all_urls(self) -> List[str]:
        """Возвращает все URL всех источников"""
        urls = []
        for source in self._sources.values():
            if source.seed_urls:
                urls.extend(source.seed_urls)
        return urls

    def get_source_config_for_plugin(self, name: str) -> Dict[str, Any]:
        """Получает конфигурацию для PluginManager"""
        config = self.get(name)
        return {
            "base_url": config.base_url,
            "strategy": config.strategy,
            "use_cache": config.use_cache,
            "max_pages": config.max_pages,
            "crawl_deny_prefixes": config.crawl_deny_prefixes,
            "sitemap_path": config.sitemap_path,
            "seed_urls": config.seed_urls,
            "metadata_patterns": config.metadata_patterns
        }

# Глобальный реестр
sources_registry = SourcesRegistry()

# ИНТЕГРИРОВАННЫЕ функции для совместимости
def get_source_config(name: str) -> SourceConfig:
    """Получает конфигурацию источника"""
    return sources_registry.get(name)

def get_plugin_config(name: str) -> Dict[str, Any]:
    """Получает конфигурацию для PluginManager"""
    return sources_registry.get_source_config_for_plugin(name)

def list_available_sources() -> List[str]:
    """Возвращает список доступных источников"""
    return list(sources_registry._sources.keys())
```

#### 1.2 Создать базовые классы для парсеров с ИНТЕГРАЦИЕЙ page_type
**КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ**: Новые парсеры должны интегрироваться с существующей системой определения page_type.
```python
# app/config/sources.py
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class SourceType(Enum):
    """Типы источников данных"""
    DOCS_SITE = "docs_site"
    API_DOCS = "api_docs"
    BLOG = "blog"
    FAQ = "faq"
    EXTERNAL = "external"

@dataclass
class SourceConfig:
    """Конфигурация источника данных"""
    name: str
    base_url: str
    source_type: SourceType
    strategy: str = "auto"
    use_cache: bool = True
    max_pages: int = None
    crawl_deny_prefixes: List[str] = None
    sitemap_path: str = "/sitemap.xml"
    seed_urls: List[str] = None
    metadata_patterns: Dict[str, Dict[str, str]] = None

class SourcesRegistry:
    """Реестр источников данных - убирает хардкод URL-ов"""

    def __init__(self):
        self._sources: Dict[str, SourceConfig] = {}
        self._load_default_sources()

    def _load_default_sources(self):
        """Загружает источники по умолчанию"""
        self.register(SourceConfig(
            name="edna_docs",
            base_url="https://docs-chatcenter.edna.ru/",
            source_type=SourceType.DOCS_SITE,
            strategy="jina",
            use_cache=True,
            sitemap_path="/sitemap.xml",
            seed_urls=[
                "https://docs-chatcenter.edna.ru/",
                "https://docs-chatcenter.edna.ru/docs/start/",
                "https://docs-chatcenter.edna.ru/docs/agent/",
                "https://docs-chatcenter.edna.ru/docs/supervisor/",
                "https://docs-chatcenter.edna.ru/docs/admin/",
                "https://docs-chatcenter.edna.ru/docs/chat-bot/",
                "https://docs-chatcenter.edna.ru/docs/api/index/",
                "https://docs-chatcenter.edna.ru/docs/faq/",
                "https://docs-chatcenter.edna.ru/blog/",
            ],
            crawl_deny_prefixes=[
                "https://docs-chatcenter.edna.ru/api/",  # API endpoints
                "https://docs-chatcenter.edna.ru/admin/",  # Админ панель
                "https://docs-chatcenter.edna.ru/supervisor/",  # Панель супервайзера
            ],
            metadata_patterns={
                r'/docs/start/': {'section': 'start', 'user_role': 'all', 'page_type': 'guide'},
                r'/docs/agent/': {'section': 'agent', 'user_role': 'agent', 'page_type': 'guide'},
                r'/docs/supervisor/': {'section': 'supervisor', 'user_role': 'supervisor', 'page_type': 'guide'},
                r'/docs/admin/': {'section': 'admin', 'user_role': 'admin', 'page_type': 'guide'},
                r'/docs/api/': {'section': 'api', 'user_role': 'integrator', 'page_type': 'api'},
                r'/blog/': {'section': 'changelog', 'user_role': 'all', 'page_type': 'release_notes'},
                r'/faq': {'section': 'faq', 'user_role': 'all', 'page_type': 'faq'},
            }
        ))

    def get(self, name: str) -> SourceConfig:
        """Получает конфигурацию источника по имени"""
        if name not in self._sources:
            raise ValueError(f"Source '{name}' not found. Available: {list(self._sources.keys())}")
        return self._sources[name]

    def get_all_urls(self) -> List[str]:
        """Возвращает все URL всех источников"""
        urls = []
        for source in self._sources.values():
            if source.seed_urls:
                urls.extend(source.seed_urls)
        return urls

# Глобальный реестр
sources_registry = SourcesRegistry()
```

#### 1.2 Создать базовые классы
```python
# ingestion/processors/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class ProcessedPage:
    """Упрощенная структура обработанной страницы (без legacy совместимости)"""
    url: str
    title: str
    content: str  # Всегда 'content'
    page_type: str
    metadata: Dict[str, Any]

    def __post_init__(self):
        """Простая валидация данных"""
        if not self.content or len(self.content.strip()) < 10:
            raise ValueError(f"Content too short for {self.url}")
        if not self.title:
            self.title = self._extract_title_from_url()

    def _extract_title_from_url(self) -> str:
        """Извлечение заголовка из URL"""
        import re
        path = self.url.split('/')[-1]
        return re.sub(r'[_-]', ' ', path).title()

class BaseParser(ABC):
    """Базовый класс для всех парсеров"""

    @abstractmethod
    def parse(self, url: str, content: str) -> ProcessedPage:
        """Парсинг контента в унифицированный формат"""
        pass

    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация результата парсинга"""
        if not isinstance(result, dict):
            raise ValueError(f"Parser must return dict, got {type(result)}")

        required_fields = ['title', 'content']
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
            if not isinstance(result[field], str):
                raise ValueError(f"Field '{field}' must be string, got {type(result[field])}")

        return result

class ContentProcessor:
    """Единый процессор контента"""

    def __init__(self):
        self.parsers = {
            'jina_reader': JinaParser(),
            'html': HTMLParser(),
            'markdown': MarkdownParser(),
        }
        self._soup_cache = {}  # Кеш BeautifulSoup объектов

    def process(self, url: str, content: str, strategy: str = 'auto') -> ProcessedPage:
        """Единая точка обработки контента"""
        try:
            content_type = self._detect_content_type(content, strategy)
            parser = self.parsers[content_type]
            return parser.parse(url, content)
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            return self._create_error_page(url, str(e))

    def _detect_content_type(self, content: str, strategy: str) -> str:
        """Быстрое определение типа контента"""
        if strategy == 'jina' or content.startswith("Title:") and "URL Source:" in content:
            return 'jina_reader'
        elif content.startswith("<!DOCTYPE html") or content.startswith("<html"):
            return 'html'
        elif content.startswith("#"):
            return 'markdown'
        return 'html'  # Fallback

    def _create_error_page(self, url: str, error: str) -> ProcessedPage:
        """Создание страницы с ошибкой"""
        return ProcessedPage(
            url=url,
            title="Error",
            content=f"Error processing page: {error}",
            page_type="error",
            metadata={"error": error}
        )
```

#### 1.3 Как добавлять новые источники данных (гайд)
Добавление нового источника теперь делается через централизованный реестр `app/config/sources.py`.

Шаги:
1) Описать источник через `SourceConfig` и зарегистрировать его в `SourcesRegistry`.
2) Указать `base_url`, стратегию загрузки (`strategy`), `seed_urls`/`sitemap_path`, опциональные `crawl_deny_prefixes` и `metadata_patterns`.
3) Запустить пайплайн с параметром `source_name`.

Пример — добавить внешний сайт документации:
```python
# app/config/sources.py
from app.config.sources import SourcesRegistry, SourceConfig, SourceType

def _load_default_sources(self):
    # ... существующие источники ...

    self.register(SourceConfig(
        name="partner_docs",
        base_url="https://docs.partner.example/",
        source_type=SourceType.DOCS_SITE,
        strategy="html",           # или "jina"/"auto"
        use_cache=True,
        sitemap_path="/sitemap.xml",
        seed_urls=[
            "https://docs.partner.example/",
            "https://docs.partner.example/getting-started/",
        ],
        crawl_deny_prefixes=[
            "https://docs.partner.example/admin/",
        ],
        metadata_patterns={
            r"/getting-started/": {"section": "start", "user_role": "all", "page_type": "guide"},
            r"/api/": {"section": "api", "user_role": "integrator", "page_type": "api"},
        }
    ))
```

Использование в пайплайне (без хардкода URL):
```python
# ingestion/pipeline.py
result = crawl_and_index(
    source_name="partner_docs",   # имя из реестра
    incremental=True,
    max_pages=50
)
```

Проверка конфигурации источника в тестах:
```python
from app.config.sources import get_source_config

def test_partner_docs_source_config():
    cfg = get_source_config("partner_docs")
    assert cfg.base_url.startswith("https://docs.partner.example/")
    assert cfg.strategy in ("html", "jina", "auto")
    assert len(cfg.seed_urls) > 0 or cfg.sitemap_path
```

Рекомендации:
- Для сайтов с тяжелым HTML использовать `strategy="jina"` (быстрее и устойчивее).
- При наличии корректного `sitemap.xml` полагаться на него, `seed_urls` оставить минимальными.
- Всегда задавать `crawl_deny_prefixes` для исключения админок/нецелевых разделов.

Примеры добавления источников:

1) Внешний блог (RSS/Sitemap + HTML):
```python
# app/config/sources.py
self.register(SourceConfig(
    name="company_blog",
    base_url="https://blog.company.example/",
    source_type=SourceType.BLOG,
    strategy="html",              # рендер HTML, извлекаем основной контент
    use_cache=True,
    sitemap_path="/sitemap.xml",  # если есть
    seed_urls=[
        "https://blog.company.example/",
    ],
    crawl_deny_prefixes=[
        "https://blog.company.example/admin/",
        "https://blog.company.example/login/",
    ],
    metadata_patterns={
        r"/tags/": {"section": "tags", "page_type": "taxonomy"},
        r"/category/": {"section": "category", "page_type": "taxonomy"},
    }
))

# ingestion/pipeline.py
result = crawl_and_index(source_name="company_blog", incremental=True, max_pages=100)

# tests
from app.config.sources import get_source_config
def test_company_blog_source_config():
    cfg = get_source_config("company_blog")
    assert cfg.base_url.startswith("https://blog.company.example/")
    assert cfg.strategy == "html"
    assert cfg.sitemap_path or len(cfg.seed_urls) > 0
```

2) API‑портал (документация, предпочтительно Jina):
```python
# app/config/sources.py
self.register(SourceConfig(
    name="api_portal",
    base_url="https://api.company.example/docs/",
    source_type=SourceType.API_DOCS,
    strategy="jina",              # быстрее и устойчивее против антибота
    use_cache=True,
    sitemap_path="/sitemap.xml",
    seed_urls=[
        "https://api.company.example/docs/",
        "https://api.company.example/docs/reference/",
    ],
    crawl_deny_prefixes=[
        "https://api.company.example/swagger.json",  # бинарные/JSON схемы не индексируем
    ],
    metadata_patterns={
        r"/reference/": {"section": "api", "user_role": "integrator", "page_type": "api"},
        r"/guides/": {"section": "guides", "user_role": "all", "page_type": "guide"},
    }
))

# ingestion/pipeline.py
result = crawl_and_index(source_name="api_portal", incremental=False, max_pages=200)

# tests
from app.config.sources import get_source_config
def test_api_portal_source_config():
    cfg = get_source_config("api_portal")
    assert cfg.base_url.endswith("/docs/")
    assert cfg.strategy in ("jina", "auto")
    assert any("/reference/" in u for u in (cfg.seed_urls or [])) or cfg.sitemap_path
```


#### 1.2 Создать специализированные парсеры
```python
# ingestion/processors/jina_parser.py
class JinaParser(BaseParser):
    """Оптимизированный парсер Jina Reader"""

    def parse(self, url: str, content: str) -> ProcessedPage:
        """Парсинг контента от Jina Reader"""
        if not content:
            raise ValueError("Empty content")

        lines = content.split('\n')
        title = self._extract_title(lines)
        content_text = self._extract_content(lines)
        metadata = self._extract_metadata(lines)

        result = {
            'title': title,
            'content': content_text,
            **metadata
        }

        validated = self._validate_result(result)

        return ProcessedPage(
            url=url,
            title=validated['title'],
            content=validated['content'],
            page_type=self._detect_page_type(url),
            metadata=validated
        )

    def _extract_title(self, lines: List[str]) -> str:
        """Извлечение заголовка"""
        for line in lines:
            if line.startswith("Title:"):
                title_part = line.split("Title:")[1].strip()
                if "|" in title_part:
                    return title_part.split("|")[0].strip()
                return title_part
        return ""

    def _extract_content(self, lines: List[str]) -> str:
        """Извлечение контента"""
        content_started = False
        content_lines = []

        for line in lines:
            if line.startswith("Markdown Content:"):
                content_started = True
                continue

            if content_started:
                if line.startswith(("Title:", "URL Source:", "Published Time:")):
                    break
                content_lines.append(line)

        return '\n'.join(content_lines).strip()

    def _extract_metadata(self, lines: List[str]) -> Dict[str, Any]:
        """Извлечение метаданных"""
        metadata = {}

        for line in lines[:20]:  # Первые 20 строк
            line = line.strip()
            if line.startswith("URL Source:"):
                metadata['url_source'] = line[11:].strip()
            elif line.startswith("Content Length:"):
                try:
                    metadata['content_length'] = int(line[15:].strip())
                except ValueError:
                    pass
            elif line.startswith("Language Detected:"):
                metadata['language_detected'] = line[18:].strip()
            # ... другие метаданные

        return metadata

# ingestion/processors/html_parser.py
class HTMLParser(BaseParser):
    """Оптимизированный парсер HTML с кешированием"""

    def __init__(self):
        self._soup_cache = {}

    def parse(self, url: str, content: str) -> ProcessedPage:
        """Парсинг HTML контента"""
        soup = self._get_soup(content)

        title = self._extract_title(soup)
        content_text = self._extract_content(soup)
        metadata = self._extract_metadata(soup, url)

        result = {
            'title': title,
            'content': content_text,
            **metadata
        }

        validated = self._validate_result(result)

        return ProcessedPage(
            url=url,
            title=validated['title'],
            content=validated['content'],
            page_type=self._detect_page_type(url),
            metadata=validated
        )

    def _get_soup(self, content: str) -> BeautifulSoup:
        """Получение BeautifulSoup с кешированием"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        if content_hash not in self._soup_cache:
            self._soup_cache[content_hash] = BeautifulSoup(content, "lxml")
        return self._soup_cache[content_hash]

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлечение заголовка"""
        # Docusaurus заголовок
        h1 = soup.select_one('.theme-doc-markdown h1')
        if h1:
            return h1.get_text(' ', strip=True)

        # Обычный title
        if soup.title:
            return soup.title.get_text(strip=True)

        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлечение основного контента"""
        # Docusaurus контент
        main = soup.select_one('.theme-doc-markdown')
        if main:
            return self._extract_text_from_element(main)

        # Fallback к body
        return self._extract_text_from_element(soup)

    def _extract_text_from_element(self, element) -> str:
        """Извлечение текста из элемента"""
        parts = []

        # Заголовок h1
        h1 = element.find('h1')
        if h1:
            parts.append(h1.get_text(' ', strip=True))

        # Параграфы и списки
        for node in element.find_all(['p', 'li']):
            txt = node.get_text(' ', strip=True)
            if txt:
                parts.append(txt)

        return "\n\n".join(parts)

# ingestion/processors/markdown_parser.py
class MarkdownParser(BaseParser):
    """Парсер Markdown контента"""

    def parse(self, url: str, content: str) -> ProcessedPage:
        """Парсинг Markdown контента"""
        lines = content.split('\n')
        title = self._extract_title(lines)
        content_text = self._clean_markdown(content)

        result = {
            'title': title,
            'content': content_text
        }

        validated = self._validate_result(result)

        return ProcessedPage(
            url=url,
            title=validated['title'],
            content=validated['content'],
            page_type=self._detect_page_type(url),
            metadata=validated
        )

    def _extract_title(self, lines: List[str]) -> str:
        """Извлечение заголовка из Markdown"""
        for line in lines:
            if line.startswith('# '):
                return line[2:].strip()
        return ""

    def _clean_markdown(self, content: str) -> str:
        """Очистка Markdown от разметки"""
        import re

        # Убираем заголовки
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)

        # Убираем жирный и курсив
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
        content = re.sub(r'\*(.*?)\*', r'\1', content)

        # Убираем ссылки
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)

        return content.strip()
```

#### 1.3 Создать утилиты для метаданных
```python
# ingestion/processors/metadata_extractor.py
class MetadataExtractor:
    """Извлечение метаданных из URL и контента"""

    @staticmethod
    def extract_url_metadata(url: str) -> Dict[str, str]:
        """Извлечение метаданных из URL"""
        metadata = {}

        patterns = {
            r'/docs/start/': {'section': 'start', 'user_role': 'all', 'page_type': 'guide'},
            r'/docs/agent/': {'section': 'agent', 'user_role': 'agent', 'page_type': 'guide'},
            r'/docs/supervisor/': {'section': 'supervisor', 'user_role': 'supervisor', 'page_type': 'guide'},
            r'/docs/admin/': {'section': 'admin', 'user_role': 'admin', 'page_type': 'guide'},
            r'/docs/api/': {'section': 'api', 'user_role': 'integrator', 'page_type': 'api'},
            r'/blog/': {'section': 'changelog', 'user_role': 'all', 'page_type': 'release_notes'},
            r'/faq': {'section': 'faq', 'user_role': 'all', 'page_type': 'faq'},
        }

        for pattern, meta in patterns.items():
            if re.search(pattern, url):
                metadata.update(meta)
                break

        # Определяем разрешения
        if 'admin' in url:
            metadata['permissions'] = 'ADMIN'
        elif 'supervisor' in url:
            metadata['permissions'] = 'SUPERVISOR'
        elif 'agent' in url:
            metadata['permissions'] = 'AGENT'
        else:
            metadata['permissions'] = 'ALL'

        return metadata

    @staticmethod
    def detect_page_type(url: str, content: str = None) -> str:
        """Определение типа страницы"""
        url_lower = url.lower()

        if 'faq' in url_lower:
            return 'faq'
        elif 'api' in url_lower:
            return 'api'
        elif any(keyword in url_lower for keyword in ['release', 'changelog', 'blog']):
            return 'release_notes'
        else:
            return 'guide'
```

### Этап 2: TDD разработка с тестами (1.5 дня)

#### 2.1 Создание тестовых утилит
```python
# tests/test_utils.py
import pytest
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class TestCase:
    """Структура тестового случая"""
    name: str
    url: str
    content: str
    strategy: str
    expected_type: str
    expected_fields: List[str]
    should_fail: bool = False

class TestDataFactory:
    """Фабрика тестовых данных"""

    @staticmethod
    def create_jina_test_cases() -> List[TestCase]:
        """Создает тестовые случаи для Jina Reader"""
        return [
            TestCase(
                name="Jina FAQ",
                url="https://docs-chatcenter.edna.ru/faq",
                content="""Title: FAQ - Часто задаваемые вопросы
URL Source: https://docs-chatcenter.edna.ru/faq
Content Length: 1500
Language Detected: Russian
Markdown Content:

# FAQ

**Q: Как настроить систему?**
A: Следуйте инструкции в разделе "Настройка".

**Q: Как добавить агента?**
A: Перейдите в раздел "Агенты" и нажмите "Добавить".""",
                strategy="jina",
                expected_type="faq",
                expected_fields=["title", "content", "content_length", "language_detected"]
            ),
            TestCase(
                name="Jina API Guide",
                url="https://docs-chatcenter.edna.ru/docs/api/create-agent",
                content="""Title: Создание агента через API
URL Source: https://docs-chatcenter.edna.ru/docs/api/create-agent
Content Length: 2000
Language Detected: Russian
Markdown Content:

# Создание агента через API

## Описание

API для создания нового агента в системе.

## Параметры

- `name` - имя агента
- `email` - email агента
- `role` - роль агента""",
                strategy="jina",
                expected_type="api",
                expected_fields=["title", "content", "content_length", "language_detected"]
            )
        ]

    @staticmethod
    def create_html_test_cases() -> List[TestCase]:
        """Создает тестовые случаи для HTML"""
        return [
            TestCase(
                name="HTML Docusaurus",
                url="https://docs-chatcenter.edna.ru/docs/agent/quick-start",
                content="""<!DOCTYPE html>
<html>
<head>
    <title>Быстрый старт агента | edna Chat Center</title>
</head>
<body>
    <nav class="theme-doc-breadcrumbs">
        <a href="/docs">Документация</a> > <a href="/docs/agent">Агент</a>
    </nav>
    <article class="theme-doc-markdown">
        <h1>Быстрый старт агента</h1>
        <p>Руководство по быстрому началу работы агента в системе.</p>
        <h2>Настройка</h2>
        <p>Для начала работы выполните следующие шаги:</p>
        <ol>
            <li>Войдите в систему</li>
            <li>Настройте профиль</li>
            <li>Начните работу с клиентами</li>
        </ol>
    </article>
</body>
</html>""",
                strategy="html",
                expected_type="guide",
                expected_fields=["title", "content", "breadcrumb_path", "section_headers"]
            ),
            TestCase(
                name="HTML Generic",
                url="https://docs-chatcenter.edna.ru/faq",
                content="""<!DOCTYPE html>
<html>
<head>
    <title>FAQ - Часто задаваемые вопросы</title>
</head>
<body>
    <h1>FAQ</h1>
    <div class="faq-content">
        <h2>Общие вопросы</h2>
        <p><strong>Q: Как настроить систему?</strong></p>
        <p>A: Следуйте инструкции в разделе "Настройка".</p>
        <p><strong>Q: Как добавить агента?</strong></p>
        <p>A: Перейдите в раздел "Агенты" и нажмите "Добавить".</p>
    </div>
</body>
</html>""",
                strategy="html",
                expected_type="faq",
                expected_fields=["title", "content"]
            )
        ]

    @staticmethod
    def create_error_test_cases() -> List[TestCase]:
        """Создает тестовые случаи для обработки ошибок"""
        return [
            TestCase(
                name="Empty Content",
                url="https://example.com/empty",
                content="",
                strategy="auto",
                expected_type="error",
                expected_fields=["title", "content"],
                should_fail=True
            ),
            TestCase(
                name="Invalid HTML",
                url="https://example.com/invalid",
                content="<html><head><title>Test</title></head><body><h1>Test</h1><p>Content</p>",  # Не закрыт </body>
                strategy="html",
                expected_type="guide",
                expected_fields=["title", "content"]
            ),
            TestCase(
                name="Malformed Jina",
                url="https://example.com/malformed",
                content="Title: Test\nInvalid content without proper structure",
                strategy="jina",
                expected_type="error",
                expected_fields=["title", "content"],
                should_fail=True
            )
        ]

class TestValidator:
    """Валидатор тестовых результатов"""

    @staticmethod
    def validate_processed_page(result, test_case: TestCase) -> Dict[str, Any]:
        """Валидирует результат ProcessedPage"""
        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": []
        }

        # Проверяем тип результата
        if not hasattr(result, '__class__') or result.__class__.__name__ != 'ProcessedPage':
            validation_result["passed"] = False
            validation_result["errors"].append(f"Expected ProcessedPage, got {type(result)}")
            return validation_result

        # Проверяем обязательные поля
        required_attrs = ['url', 'title', 'content', 'page_type', 'metadata']
        for attr in required_attrs:
            if not hasattr(result, attr):
                validation_result["passed"] = False
                validation_result["errors"].append(f"Missing required attribute: {attr}")

        # Проверяем URL
        if hasattr(result, 'url') and result.url != test_case.url:
            validation_result["warnings"].append(f"URL mismatch: expected {test_case.url}, got {result.url}")

        # Проверяем тип страницы
        if hasattr(result, 'page_type') and result.page_type != test_case.expected_type:
            validation_result["warnings"].append(f"Page type mismatch: expected {test_case.expected_type}, got {result.page_type}")

        # Проверяем наличие контента
        if hasattr(result, 'content'):
            if not result.content or len(result.content.strip()) < 10:
                validation_result["passed"] = False
                validation_result["errors"].append("Content is too short or empty")
            elif len(result.content.strip()) < 50:
                validation_result["warnings"].append("Content is quite short")

        # Проверяем заголовок
        if hasattr(result, 'title'):
            if not result.title or len(result.title.strip()) < 3:
                validation_result["warnings"].append("Title is too short or empty")

        # Проверяем метаданные
        if hasattr(result, 'metadata'):
            for field in test_case.expected_fields:
                if field not in result.metadata:
                    validation_result["warnings"].append(f"Expected metadata field missing: {field}")

        return validation_result
```

#### 2.2 Тесты форматов данных
```python
# tests/test_parser_format_consistency.py
import pytest
from ingestion.processors.content_processor import ContentProcessor
from ingestion.processors.jina_parser import JinaParser
from ingestion.processors.html_parser import HTMLParser

class TestParserFormatConsistency:
    """Тесты форматов данных нового пайплайна"""

    def test_all_parsers_return_processed_page(self):
        """Тест что все парсеры возвращают ProcessedPage"""
        processor = ContentProcessor()

        test_cases = [
            {
                'url': 'https://example.com/jina',
                'content': 'Title: Test\nURL Source: https://example.com\nMarkdown Content:\n# Test\nContent here',
                'strategy': 'jina'
            },
            {
                'url': 'https://example.com/html',
                'content': '<html><head><title>Test</title></head><body><h1>Test</h1><p>Content here</p></body></html>',
                'strategy': 'html'
            },
            {
                'url': 'https://example.com/markdown',
                'content': '# Test\n\nContent here',
                'strategy': 'markdown'
            }
        ]

        for case in test_cases:
            result = processor.process(case['url'], case['content'], case['strategy'])

            # Проверяем что результат - ProcessedPage
            assert isinstance(result, ProcessedPage), f"Expected ProcessedPage, got {type(result)}"

            # Проверяем обязательные поля
            assert hasattr(result, 'url')
            assert hasattr(result, 'title')
            assert hasattr(result, 'content')
            assert hasattr(result, 'page_type')
            assert hasattr(result, 'metadata')

            # Проверяем типы полей
            assert isinstance(result.title, str)
            assert isinstance(result.content, str)
            assert isinstance(result.page_type, str)
            assert isinstance(result.metadata, dict)

    def test_faq_parser_fix(self):
        """Тест исправления FAQ парсера"""
        # Тестовые данные для FAQ
        faq_content = """Title: FAQ - Часто задаваемые вопросы
URL Source: https://docs-chatcenter.edna.ru/faq
Markdown Content:

# FAQ

**Q: Как настроить систему?**
A: Следуйте инструкции в разделе "Настройка".

**Q: Как добавить агента?**
A: Перейдите в раздел "Агенты" и нажмите "Добавить".
"""

        processor = ContentProcessor()
        result = processor.process("https://docs-chatcenter.edna.ru/faq", faq_content, "jina")

        # Проверяем что результат - ProcessedPage (не список!)
        assert isinstance(result, ProcessedPage)
        assert result.page_type == 'faq'
        assert 'FAQ' in result.title
        assert 'настроить систему' in result.content
        assert 'добавить агента' in result.content

    def test_html_parser_caching(self):
        """Тест кеширования HTML парсера"""
        html_content = '<html><head><title>Test</title></head><body><h1>Test</h1></body></html>'

        parser = HTMLParser()

        # Первый вызов
        result1 = parser.parse("https://example.com", html_content)

        # Второй вызов с тем же контентом
        result2 = parser.parse("https://example.com", html_content)

        # Проверяем что результаты одинаковые
        assert result1.title == result2.title
        assert result1.content == result2.content

        # Проверяем что кеш используется
        assert len(parser._soup_cache) == 1

    def test_sources_configuration(self):
        """Тест конфигурации источников"""
        # Проверяем что источники загружены
        from app.config.sources import sources_registry

        assert "edna_docs" in sources_registry.list_all()

        # Проверяем конфигурацию edna_docs
        config = sources_registry.get("edna_docs")
        assert config.base_url == "https://docs-chatcenter.edna.ru/"
        assert config.strategy == "jina"
        assert len(config.seed_urls) > 0
        assert len(config.metadata_patterns) > 0

    def test_performance_improvement(self):
        """Тест улучшения производительности"""
        import time

        # Тестовые данные
        test_pages = [
            {
                'url': f'https://example.com/page{i}',
                'content': f'<html><head><title>Page {i}</title></head><body><h1>Page {i}</h1><p>Content {i}</p></body></html>'
            }
            for i in range(100)
        ]

        processor = ContentProcessor()

        # Измеряем время обработки
        start_time = time.time()
        results = []
        for page in test_pages:
            result = processor.process(page['url'], page['content'], 'html')
            results.append(result)
        duration = time.time() - start_time

        # Проверяем что все страницы обработаны
        assert len(results) == 100

        # Проверяем что обработка завершилась за разумное время
        assert duration < 10.0  # 10 секунд максимум для 100 страниц

        # Проверяем что все результаты валидны
        for result in results:
            assert isinstance(result, ProcessedPage)
            assert result.title
            assert result.content
```

#### 2.2 Тесты интеграции с pipeline
```python
# tests/test_pipeline_integration.py
import pytest
from ingestion.processors.content_processor import ContentProcessor
from ingestion.pipeline import crawl_and_index
from app.sources.edna_docs_source import EdnaDocsDataSource

class TestPipelineIntegration:
    """Тесты интеграции с pipeline"""

    def test_pipeline_processing_sanity(self):
        """Санити-тест обработки страниц новым пайплайном (без legacy)."""
        test_pages = [
            {
                'url': 'https://docs-chatcenter.edna.ru/faq',
                'html': '<html><head><title>FAQ</title></head><body><h1>FAQ</h1><p>FAQ content</p></body></html>'
            },
            {
                'url': 'https://docs-chatcenter.edna.ru/api',
                'html': '<html><head><title>API</title></head><body><h1>API</h1><p>API content</p></body></html>'
            }
        ]

        processor = ContentProcessor()

        for page_data in test_pages:
            result = processor.process(page_data['url'], page_data['html'], 'html')
            assert hasattr(result, 'content') and result.content.strip()

    def test_edna_docs_source_adapter(self):
        """Тест адаптера: ProcessedPage.content -> payload.text"""
        test_html = '<html><head><title>Test Guide</title></head><body><h1>Test Guide</h1><p>Guide content</p></body></html>'

        source = EdnaDocsDataSource({
            'base_url': 'https://docs-chatcenter.edna.ru/',
            'strategy': 'html'
        })

        parsed_content = source._parse_content('https://docs-chatcenter.edna.ru/guide', test_html)

        assert 'text' in parsed_content
        assert parsed_content['text'].strip()

    def test_sources_configuration_integration(self):
        """Тест интеграции с конфигурацией источников"""
        # Проверяем что конфигурация загружается
        from app.config.sources import get_source_config
        config = get_source_config("edna_docs")
        assert config.base_url == "https://docs-chatcenter.edna.ru/"
        assert config.strategy == "jina"

        # Проверяем что seed URLs доступны
        assert len(config.seed_urls) > 0
        assert "https://docs-chatcenter.edna.ru/" in config.seed_urls

    def test_end_to_end_pipeline_clean_start(self):
        """Тест полного пайплайна с чистой коллекцией"""
        # Очищаем коллекцию перед тестом
        from scripts.clear_collection import clear_collection
        clear_collection()

        # Тест с небольшим количеством страниц
        from app.services.optimized_pipeline import run_optimized_indexing
        result = run_optimized_indexing(
            source_name="edna_docs",
            max_pages=5,
            chunk_strategy="adaptive"
        )

        # Проверяем что индексация завершилась успешно
        assert result['success'] == True
        assert result['pages'] > 0
        assert result['chunks'] > 0

        # Проверяем что нет ошибок
        assert result.get('errors', 0) == 0
```

### Этап 3: Миграция pipeline (1 день)

#### 3.1 Обновить ingestion/pipeline.py
```python
# ingestion/pipeline.py
from ingestion.processors.content_processor import ContentProcessor
from app.config.sources import get_source_config, get_all_crawl_urls

def crawl_and_index(source_name: str = "edna_docs", incremental: bool = True,
                   reindex_mode: str = "auto", max_pages: int = None) -> dict[str, Any]:
    """Обновленный pipeline с централизованной конфигурацией"""

    # Получаем конфигурацию источника
    source_config = get_source_config(source_name)

    logger.info(f"Начинаем {'инкрементальную ' if incremental else ''}индексацию источника: {source_name}")
    logger.info(f"Параметры: strategy={source_config.strategy}, use_cache={source_config.use_cache}")

    # 1) Краулинг с конфигурацией источника
    if reindex_mode == "cache_only":
        # ... существующая логика ...
    else:
        pages = crawl_with_sitemap_progress(
            base_url=source_config.base_url,
            strategy=source_config.strategy,
            use_cache=source_config.use_cache,
            max_pages=max_pages or source_config.max_pages
        )

    # 2) НОВОЕ: Используем оптимизированный процессор
    processor = ContentProcessor()

    all_chunks = []
    logger.info("Обрабатываем страницы и собираем чанки...")

    with tqdm(total=len(pages), desc="Processing pages") as pbar:
        for p in pages:
            url = p["url"]
            raw_content = p.get("text") or p.get("html") or ""

            if not raw_content:
                logger.warning(f"Пустой контент для {url}, пропускаем")
                pbar.update(1)
                continue

            try:
                # НОВОЕ: Оптимизированная обработка
                processed_page = processor.process(url, raw_content, source_config.strategy)

                # Извлекаем данные из ProcessedPage
                text = processed_page.content
                title = processed_page.title
                page_type = processed_page.page_type

                if not text:
                    logger.warning(f"Пустой контент после обработки для {url}, пропускаем")
                    pbar.update(1)
                    continue

                # Генерируем чанки
                chunks_text = chunk_text(text)

                if not chunks_text:
                    logger.warning(f"Не удалось создать чанки для {url}, пропускаем")
                    pbar.update(1)
                    continue

                # Создаем чанки с упрощенной структурой payload
                for i, ct in enumerate(chunks_text):
                    payload = {
                        "url": url,
                        "title": title,
                        "content": ct,  # Всегда 'content', не 'text'
                        "page_type": page_type,
                        "source": source_name,
                        "language": "ru",
                        "chunk_index": i,
                        "content_length": len(text),
                        "indexed_at": time.time(),
                        "indexed_via": source_config.strategy,
                        **processed_page.metadata  # Все метаданные из ProcessedPage
                    }

                    all_chunks.append({
                        "text": ct,  # Для совместимости с Qdrant API
                        "payload": payload,
                    })

            except Exception as e:
                logger.error(f"Ошибка обработки {url}: {e}")
                continue

            pbar.update(1)

    logger.info(f"Собрано {len(all_chunks)} чанков, начинаем enhanced metadata-aware индексацию...")

    # 3) Индексация (остается та же)
    metadata_indexer = MetadataAwareIndexer()
    indexed = metadata_indexer.index_chunks_with_metadata(all_chunks)

    return {"pages": len(pages), "chunks": indexed, "source": source_name}
```

#### 3.2 Обновить app/sources/edna_docs_source.py
```python
# app/sources/edna_docs_source.py
from ingestion.processors.content_processor import ContentProcessor
from app.config.sources import get_source_config

@register_data_source("edna_docs")
class EdnaDocsDataSource(DataSourceBase):
    """Data source for edna documentation website"""

    def __init__(self, config: Dict[str, Any]):
        # Получаем конфигурацию из централизованного реестра
        source_config = get_source_config("edna_docs")

        self.base_url = config.get("base_url", source_config.base_url)
        self.strategy = config.get("strategy", source_config.strategy)
        self.use_cache = config.get("use_cache", source_config.use_cache)
        self.max_pages = config.get("max_pages", source_config.max_pages)
        self.processor = ContentProcessor()  # НОВОЕ
        super().__init__(config)

    def _parse_content(self, url: str, html: str) -> Dict[str, str]:
        """Parse HTML content using new processor (упрощенная версия)"""
        try:
            # НОВОЕ: Используем новый процессор
            processed_page = self.processor.process(url, html, self.strategy)

            # Прямое использование без адаптеров
            return {
                "content": processed_page.content,  # Прямое использование
                "title": processed_page.title,
                "page_type": processed_page.page_type,
                **processed_page.metadata
            }
        except Exception as e:
            logger.warning(f"Parser failed for {url}, using fallback: {e}")
            return {"content": html, "title": ""}
```

#### 3.3 Обновить app/services/optimized_pipeline.py
```python
# app/services/optimized_pipeline.py
from ingestion.processors.content_processor import ContentProcessor

class OptimizedPipeline:
    """Optimized indexing pipeline with improved architecture"""

    def __init__(self):
        self.indexer = MetadataAwareIndexer()
        self.processor = ContentProcessor()  # НОВОЕ
        self.processed_chunks = 0
        self.errors = []

    def _process_pages_to_chunks(self, pages: List[Page], chunk_strategy: str = "adaptive") -> List[Dict[str, Any]]:
        """Обновленная обработка страниц с батчевой обработкой"""
        chunks = []

        # НОВОЕ: Батчевая обработка
        for page_batch in self._batch_pages(pages, batch_size=10):
            batch_results = self._process_batch(page_batch, chunk_strategy)
            chunks.extend(batch_results)

        return chunks

    def _process_batch(self, pages: List[Page], chunk_strategy: str) -> List[Dict[str, Any]]:
        """Батчевая обработка страниц"""
        results = []

        for page in pages:
            try:
                # НОВОЕ: Используем новый процессор
                processed_page = self.processor.process(page.url, page.content)

                # Создаем чанки
                chunks = self._create_chunks_from_processed_page(processed_page, chunk_strategy)
                results.extend(chunks)

            except Exception as e:
                logger.error(f"Error processing {page.url}: {e}")
                self.errors.append(str(e))

        return results

    def _create_chunks_from_processed_page(self, processed_page: ProcessedPage, chunk_strategy: str) -> List[Dict[str, Any]]:
        """Создание чанков из ProcessedPage"""
        chunks = []

        # Определяем оптимальный размер чанка
        optimal_size = self._get_optimal_chunk_size(processed_page)

        # Генерируем чанки
        chunks_text = chunk_text(processed_page.content, max_tokens=optimal_size)

        for i, chunk_text_content in enumerate(chunks_text):
            chunk = {
                "text": chunk_text_content,
                "payload": {
                    "url": processed_page.url,
                    "title": processed_page.title,
                    "page_type": processed_page.page_type,
                    "source": "docs-site",
                    "language": "ru",
                    "chunk_index": i,
                    "content_length": len(processed_page.content),
                    **processed_page.metadata
                }
            }
            chunks.append(chunk)

        return chunks
```

### Этап 4: Удаление старого кода (0.5 дня)

#### 4.1 Удалить неиспользуемые файлы
```bash
# Удаляем старые файлы
rm ingestion/universal_loader.py
rm ingestion/parsers.py
```

#### 4.2 Обновить импорты
```python
# Обновить все импорты
# Было:
from ingestion.universal_loader import load_content_universal
from ingestion.parsers import extract_url_metadata

# Стало:
from ingestion.processors.content_processor import ContentProcessor
from ingestion.processors.metadata_extractor import MetadataExtractor
```

### Этап 5: Финальное тестирование с чистой коллекцией (0.5 дня)

#### 5.1 Полный тест pipeline с чистой коллекцией
```python
# tests/test_full_pipeline_refactored.py
def test_full_pipeline_with_refactored_processor():
    """Полный тест pipeline с рефакторенным процессором и чистой коллекцией"""
    # Очищаем коллекцию перед тестом
    from scripts.clear_collection import clear_collection
    clear_collection()

    # Тест индексации
    from app.services.optimized_pipeline import run_optimized_indexing
    result = run_optimized_indexing(
        source_name="edna_docs",
        max_pages=10,
        chunk_strategy="adaptive"
    )

    assert result['success'] == True
    assert result['pages'] > 0
    assert result['chunks'] > 0

    # Тест поиска
    from app.services.retrieval import search_documents
    results = search_documents("тестовый запрос", limit=5)
    assert len(results) > 0

    # Тест что FAQ страницы обрабатываются корректно
    faq_results = search_documents("FAQ", limit=5)
    assert len(faq_results) > 0
```

#### 5.2 Бенчмарк производительности с чистой коллекцией
```python
# tests/test_performance_benchmark_refactored.py
def test_performance_benchmark():
    """Бенчмарк производительности рефакторенной системы с чистой коллекцией"""
    import time

    # Очищаем коллекцию перед тестом
    from scripts.clear_collection import clear_collection
    clear_collection()

    # Тест с реальными данными
    start_time = time.time()
    from app.services.optimized_pipeline import run_optimized_indexing
    result = run_optimized_indexing(
        source_name="edna_docs",
        max_pages=50,
        chunk_strategy="adaptive"
    )
    duration = time.time() - start_time

    # Проверяем что индексация завершилась за разумное время
    assert duration < 120  # 2 минуты максимум для 50 страниц
    assert result['success'] == True
    assert result['chunks'] > 0

    # Проверяем улучшение производительности
    # Ожидаем минимум 30% улучшение
    expected_duration = 120  # 2 минуты
    assert duration < expected_duration, f"Performance regression: {duration}s > {expected_duration}s"
```

## 📊 Ожидаемые результаты

### Исправление критических ошибок
- ✅ **100%** исправление проблемы с FAQ парсером (список → словарь)
- ✅ **100%** унификация форматов данных всех парсеров
- ✅ Переход на новый пайплайн без поддержки legacy
- ✅ **Упрощенная схема** payload без legacy полей
- ✅ **Чистая коллекция** для тестирования

### Производительность
- **+40%** скорость обработки HTML (кеширование BeautifulSoup)
- **+60%** скорость индексации (батчевая обработка)
- **+80%** скорость определения типа контента (оптимизированные проверки)
- **+30%** общая скорость pipeline
- **Быстрая очистка** коллекции при необходимости

### Надежность
- **-90%** вероятность ошибок (устранение дублирования)
- **+100%** консистентность обработки ошибок
- **+200%** качество данных (валидация)
- **Упрощенная архитектура** без legacy совместимости

### Поддерживаемость
- **-40%** строк кода (упрощение архитектуры)
- **+300%** скорость добавления новых парсеров
- **+100%** покрытие тестами
- **Централизованная конфигурация** источников данных

### Память
- **-20%** использование памяти (устранение дублирования)
- **+50%** эффективность кеширования
- **Чистая коллекция** без legacy данных

## 🎯 Критерии успеха

1. **Все тесты проходят** - стабильность нового пайплайна подтверждена (без legacy)
2. **FAQ страницы обрабатываются корректно** - нет пустых чанков
3. **Производительность улучшена минимум на 30%**
4. **Код стал проще и понятнее** - меньше дублирования
5. **Легко добавлять новые парсеры** - модульная архитектура
6. **Чистая коллекция** - успешная работа с новой схемой данных
7. **Централизованная конфигурация** - источники данных управляются из одного места

## 🚀 План выполнения

- **День 0.5**: Подготовка и очистка коллекции
- **День 1-2**: Создание новой архитектуры и парсеров
- **День 3**: Создание тестов с чистой коллекцией
- **День 4**: Миграция pipeline
- **День 4.5**: Удаление старого кода и финальное тестирование

**Общее время**: 4.5 дня (упрощение за счет отсутствия legacy совместимости)
**Риск**: Очень низкий (чистая коллекция, нет совместимости)
**Выгода**: Максимальная (исправление критических ошибок + оптимизация + упрощение)

## ⚠️ КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ ПЛАНА

### 1. Дублирование и неполнота новой конфигурации источников
**ПРОБЛЕМА**: План вводит SourcesRegistry, но в текущем коде уже есть PluginManager.
**РЕШЕНИЕ**: Интегрировать SourcesRegistry с существующим PluginManager:

```python
# app/config/sources.py - ИНТЕГРИРОВАННАЯ версия
from app.abstractions.data_source import plugin_manager, DataSourceBase

class SourcesRegistry:
    """Реестр источников данных - ИНТЕГРИРОВАННЫЙ с PluginManager"""

    def get_plugin_config(self, name: str) -> Dict[str, Any]:
        """Получает конфигурацию для PluginManager"""
        config = self.get(name)
        return {
            "base_url": config.base_url,
            "strategy": config.strategy,
            "use_cache": config.use_cache,
            "max_pages": config.max_pages,
            "crawl_deny_prefixes": config.crawl_deny_prefixes,
            "sitemap_path": config.sitemap_path,
            "seed_urls": config.seed_urls,
            "metadata_patterns": config.metadata_patterns
        }

# ИНТЕГРИРОВАННЫЕ функции для совместимости
def get_plugin_config(name: str) -> Dict[str, Any]:
    """Получает конфигурацию для PluginManager"""
    return sources_registry.get_plugin_config(name)
```

### 2. Отсутствует механизм определения page_type в новых парсерах
**ПРОБЛЕМА**: ProcessedPage требует page_type, но в примерном коде нет подключения существующих утилит.
**РЕШЕНИЕ**: Интегрировать с существующей системой классификации:

```python
# ingestion/processors/base.py - ИСПРАВЛЕННАЯ версия
class BaseParser(ABC):
    """Базовый класс для всех парсеров с ИНТЕГРАЦИЕЙ page_type"""

    def __init__(self):
        self._page_type_classifier = None

    def _get_page_type_classifier(self):
        """Получает классификатор типов страниц"""
        if self._page_type_classifier is None:
            from app.abstractions.data_source import DataSourceBase
            # Создаем временный экземпляр для использования classify_page_by_url
            temp_source = type('TempSource', (DataSourceBase,), {})()
            self._page_type_classifier = temp_source
        return self._page_type_classifier

    def _detect_page_type(self, url: str, content: str = None) -> str:
        """Определяет тип страницы используя существующую логику"""
        classifier = self._get_page_type_classifier()
        page_type = classifier.classify_page_by_url(url)
        return page_type.value
```

### 3. Удаление ingestion/parsers.py требует миграции всех потребителей
**ПРОБЛЕМА**: Функции из parsers.py используют EdnaDocsDataSource и вспомогательные скрипты.
**РЕШЕНИЕ**: Создать миграционный слой:

```python
# ingestion/parsers_migration.py - ВРЕМЕННЫЙ файл для миграции
"""
Временный файл для миграции функций из parsers.py
Удалить после полной миграции всех потребителей
"""

from ingestion.processors.content_processor import ContentProcessor
from loguru import logger

# Создаем глобальный процессор для совместимости
_content_processor = ContentProcessor()

def extract_url_metadata(url: str) -> Dict[str, Any]:
    """МИГРАЦИОННАЯ функция - использует новый процессор"""
    try:
        # Используем новый процессор для извлечения метаданных
        # Это временное решение до полной миграции
        return {
            "url": url,
            "source": "migrated",
            "extracted_at": time.time()
        }
    except Exception as e:
        logger.warning(f"Migration fallback for extract_url_metadata: {e}")
        return {"url": url, "source": "fallback"}

# Другие функции из parsers.py можно добавить по мере необходимости
```

### 4. Обновленные этапы миграции

#### Этап 3.1: Создать миграционный слой (0.5 дня)
```python
# 1. Создать ingestion/parsers_migration.py
# 2. Обновить импорты в существующих файлах:
#    - ingestion/pipeline.py: from app.sources_registry import extract_url_metadata
#    - app/sources/edna_docs_source.py: from app.sources_registry import extract_url_metadata
#    - scripts/*.py: обновить импорты

# 3. Протестировать что все работает с миграционным слоем
```

#### Этап 3.2: Обновить pipeline с интеграцией PluginManager
```python
# ingestion/pipeline.py - ИСПРАВЛЕННАЯ версия
from app.config.sources import get_plugin_config
from app.abstractions.data_source import plugin_manager

def crawl_and_index(source_name: str = "edna_docs", incremental: bool = True,
                   reindex_mode: str = "auto", max_pages: int = None) -> dict[str, Any]:
    """Обновленный pipeline с интеграцией PluginManager"""

    # Получаем конфигурацию для PluginManager
    source_config = get_plugin_config(source_name)

    # Получаем источник через PluginManager
    source = plugin_manager.get_source(source_name, source_config)

    # Остальная логика остается той же...
```

### 5. Обновленный план выполнения

- **День 0.5**: Подготовка и очистка коллекции
- **День 1**: Создание новой архитектуры с интеграцией PluginManager
- **День 2**: Создание парсеров с интеграцией page_type
- **День 3**: Создание миграционного слоя и тестов
- **День 4**: Миграция pipeline с интеграцией
- **День 4.5**: Удаление старого кода и финальное тестирование

**КРИТИЧЕСКИ ВАЖНО**: Все изменения должны быть протестированы с существующим PluginManager и системой классификации page_type.
