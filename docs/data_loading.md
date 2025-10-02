# Документация по загрузке и обработке документов

## Обзор
Новая система загрузки документов основана на модульной архитектуре:
- `SourcesRegistry` — централизованная конфигурация источников
- `CrawlerFactory` — фабрика краулеров для разных типов источников
- `BaseCrawler`/`WebsiteCrawler`/`LocalFolderCrawler` — модульная система краулеров
- `ContentProcessor` — унифицированная обработка контента (стратегии: Jina, HTML, Markdown)
- `AdaptiveChunker`/`Chunker` — адаптивный и простой чанкинг
- Индексация в Qdrant через `MetadataAwareIndexer`

Основные цели: единый формат данных (`ProcessedPage`), предсказуемость пайплайна, корректная кодировка, стабильные метрики и легкое добавление новых источников данных.

## Поток данных
1. Источник возвращает `CrawlResult` с `Page`
2. Для каждой `Page` выполняется `ContentProcessor.process(raw_content, url, strategy="auto")`
3. Результат (`ProcessedPage`) преобразуется в чанки (adaptive|simple)
4. Чанки обогащаются метаданными и индексируются в Qdrant

## Ключевые компоненты
- `app/sources_registry.py` — `SourceType`, `SourceConfig`, `SourcesRegistry`
- `ingestion/crawlers/` — модульная система краулеров:
  - `base_crawler.py` — `BaseCrawler`, `CrawlResult` (абстрактные классы)
  - `website_crawler.py` — `WebsiteCrawler` (веб-сайты, документация, блоги)
  - `local_folder_crawler.py` — `LocalFolderCrawler` (локальные папки)
  - `crawler_factory.py` — `CrawlerFactory` (выбор подходящего краулера)
- `ingestion/processors/content_processor.py` — диспетчер парсеров
- `ingestion/processors/{jina,html,markdown}_parser.py` — специализированные парсеры
- `ingestion/adaptive_chunker.py` — адаптивная стратегия чанкинга (short/medium/long)
- `ingestion/chunker.py` — простой чанкер (фиксированный диапазон BGE-M3)
- `app/tokenizer.py` — унифицированный токенайзер (BGE-M3, кэширование)
- `app/services/optimized_pipeline.py` — основной пайплайн

## Формат данных (после парсинга)
`ProcessedPage` содержит: `title`, `content`, `metadata` (включая `content_type`, `page_type`, доп. атрибуты).

Чанк payload включает минимум:
- `chunk_type` (short_document|medium_document|long_document|paragraph|section)
- `page_type` (guide|api|faq|release_notes|blog|unknown)
- `word_count`, `token_count`
- `adaptive_chunking` (True для адаптивной стратегии)
- Дополнительно для HTML: `section_title`, `section_index`

## Типы источников данных

Система поддерживает различные типы источников данных:

### Веб-сайты
- **DOCS_SITE** — документационные сайты (Docusaurus, MkDocs)
- **API_DOCS** — API документация (Swagger, OpenAPI)
- **BLOG** — блоги и новости
- **FAQ** — FAQ страницы
- **EXTERNAL** — внешние сайты

### Локальные файлы
- **LOCAL_FOLDER** — папки с документами
- **FILE_COLLECTION** — коллекции файлов (PDF, DOC, MD)

### Планируемые типы
- **GIT_REPOSITORY** — Git репозитории
- **CONFLUENCE** — Confluence wiki
- **NOTION** — Notion workspace

## Конфигурация
Параметры задаются через переменные окружения (`env.example`) и конфигурацию источников:

- Источники и краулинг: `CRAWL_MAX_PAGES`, `USE_CACHE`, `SEED_URLS`, `SITEMAP_PATH`, `CRAWL_DENY_PREFIXES`
- Стратегия чанкинга:
  - `CHUNK_STRATEGY=adaptive|simple`
  - BGE-M3 диапазон: `CHUNK_MIN_TOKENS=410`, `CHUNK_MAX_TOKENS=614`
  - Adaptive:
    - `ADAPTIVE_CHUNK_MIN_WORDS_SHORT=50`
    - `ADAPTIVE_CHUNK_MAX_WORDS_SHORT=300`
    - `ADAPTIVE_CHUNK_SIZE_MEDIUM=512`, `ADAPTIVE_CHUNK_OVERLAP_MEDIUM=100`
    - `ADAPTIVE_CHUNK_SIZE_LONG=800`, `ADAPTIVE_CHUNK_OVERLAP_LONG=160`
    - `ADAPTIVE_CHUNK_MIN_MERGE_TOKENS=50`

## Добавление нового источника
1. Создайте класс источника, унаследованный от `DataSourceBase`, и зарегистрируйте его в `plugin_manager`:
```python
from app.abstractions.data_source import DataSourceBase, register_data_source, Page, CrawlResult

@register_data_source("my_source")
class MySource(DataSourceBase):
    def fetch_pages(self, max_pages=None) -> CrawlResult:
        # верните CrawlResult(pages=[Page(...), ...], ...)
        ...

    def classify_page(self, page: Page):
        return self.classify_page_by_url(page.url)

    def get_source_name(self) -> str:
        return "my_source"
```
2. Опишите конфигурацию источника в `SourcesRegistry` (или передайте dict-конфиг напрямую в `OptimizedPipeline.index_from_source`).
3. Запустите пайплайн:
```python
from app.services.optimized_pipeline import run_optimized_indexing
run_optimized_indexing(source_name="my_source", max_pages=5, chunk_strategy="adaptive")
```

## Стратегии загрузки/парсинга
- `JinaParser` — обрабатывает формат Jina Reader (поле `Markdown Content:`)
- `HTMLParser` — обрабатывает HTML (включая Docusaurus: извлекает `h1..h3`, `p`, `li`, Permissions)
- `MarkdownParser` — обрабатывает Markdown, нормализует заголовки и кодовые блоки
- `ContentProcessor` со `strategy="auto"` сам выбирает парсер по сигнатурам контента

## Кодировка и логи
- Принудительно `utf-8` при загрузке HTTP в краулере
- `app/logging_config.py` настраивает корректный вывод UTF‑8 (Windows, PowerShell)
- Исключены межстрочные артефакты и нулевые ширины (очистка текста для логов)

## Метрики и наблюдаемость
Prometheus метрики:
- Счетчики/гистограммы чанков: `rag_chunks_created_total`, `rag_chunk_size_words`, `rag_chunk_size_tokens`
- Доля оптимальных чанков BGE‑M3: `rag_chunk_optimal_ratio{model="bge-m3"}`
- Последний запуск: `rag_last_run_*` (duration, success_rate, error_count, optimal_chunk_ratio)
- Dashboards: `monitoring/grafana/dashboards/rag_chunking_dashboard.json`

## Тестирование
- Юнит‑тесты: `tests/test_unified_tokenizer.py`, `tests/test_adaptive_chunker.py`, `tests/test_new_parsers.py`
- Интеграция (без сети): `tests/test_pipeline_mock.py`
- Интеграция (с Qdrant): `tests/test_qdrant_payload.py`
- Проверка структуры: `tests/test_payload_structure.py`

Запуск отдельных тестов:
```bash
python -m pytest tests/test_pipeline_mock.py -v
python -m pytest tests/test_qdrant_payload.py::test_adaptive_chunking_payload_in_qdrant -v -s
```

## Практические советы
- Для быстрых проверок ограничивайте страницы: `max_pages=3..5`
- Включайте `CHUNK_STRATEGY=adaptive` для производственных прогонов
- Следите за `rag_chunk_optimal_ratio` и распределением токенов; цель — максимум в 410–614
- При переходе со старых скриптов используйте `ingestion/parsers_migration.py` как совместимый слой
