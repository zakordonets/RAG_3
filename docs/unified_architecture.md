# Единая архитектура индексации

## 🎯 Обзор

Рефакторинг завершен! Создана **единая архитектура индексации** с **одним DAG** вместо трех параллельных конвейеров.

## 🏗️ Новая архитектура

### ❌ Было (3 параллельных конвейера):
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Docusaurus    │    │    Websites     │    │   General       │
│   Pipeline      │    │    Pipeline     │    │   Pipeline      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ FS → Clean →    │    │ HTTP → Parse →  │    │ Crawler →       │
│ Chunk → Embed → │    │ Clean → Chunk → │    │ Process →       │
│ Index           │    │ Embed → Index   │    │ Chunk → Index   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### ✅ Стало (единый DAG с адаптерами):
```
┌─────────────────────────────────────────────────────────────────┐
│                    ЕДИНЫЙ PIPELINE DAG                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📁 SOURCE ADAPTERS                                             │
│  ├─ DocusaurusAdapter (FS)                                     │
│  ├─ WebsiteAdapter (HTTP)                                      │
│  └─ LocalFolderAdapter (Local)                                 │
│                                                                 │
│  🔄 UNIFIED DAG                                                 │
│  Parse → Normalize → Chunk → Embed → Index                     │
│                                                                 │
│  📝 NORMALIZERS (плагины)                                      │
│  ├─ DocusaurusRules (ContentRef, JSX, frontmatter)            │
│  ├─ HtmlRules (HTML → text, cleanup)                          │
│  └─ BaseNormalizer (общие правила)                            │
│                                                                 │
│  🗄️ ЕДИНЫЙ WRITER                                              │
│  └─ QdrantWriter (upsert по chunk_id)                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Структура файлов

```
ingestion/
├── adapters/                 # Адаптеры источников
│   ├── __init__.py
│   ├── base.py              # SourceAdapter, RawDoc, ParsedDoc
│   ├── docusaurus.py        # DocusaurusAdapter (FS)
│   └── website.py           # WebsiteAdapter (HTTP)
├── normalizers/             # Нормализаторы (плагины)
│   ├── __init__.py
│   ├── base.py              # BaseNormalizer, Parser
│   ├── docusaurus.py        # DocusaurusNormalizer, URLMapper
│   └── html.py              # HtmlNormalizer, ContentExtractor
├── pipeline/                # Единый DAG
│   ├── __init__.py
│   ├── dag.py               # PipelineDAG
│   ├── chunker.py           # UnifiedChunkerStep
│   ├── embedder.py          # Embedder
│   └── indexers/
│       ├── __init__.py
│       └── qdrant_writer.py # Единый QdrantWriter
├── state/                   # Управление состоянием
│   ├── __init__.py
│   └── state_manager.py     # StateManager
├── run_unified.py           # Единый entrypoint
└── run.py                   # Старый entrypoint (для совместимости)
```

## 🔄 Единый DAG

### Шаги пайплайна:
1. **Parse** - преобразование RawDoc в ParsedDoc
2. **Normalize** - применение правил очистки (плагины)
3. **Chunk** - разбиение на семантические части
4. **Embed** - генерация dense + sparse векторов
5. **Index** - запись в Qdrant

### Адаптеры источников:
- **DocusaurusAdapter** - файловая система + frontmatter
- **WebsiteAdapter** - HTTP запросы + Playwright опционально
- **LocalFolderAdapter** - локальные папки (готов к реализации)

## 🚀 Использование

### Docusaurus:
```bash
python ingestion/run_unified.py --source docusaurus --docs-root "C:\CC_RAG\docs"
```

### Website:
```bash
python ingestion/run_unified.py --source website --seed-urls "https://example.com"
```

### С параметрами:
```bash
python ingestion/run_unified.py \
  --source docusaurus \
  --docs-root "C:\CC_RAG\docs" \
  --batch-size 16 \
  --chunk-max-tokens 300 \
  --reindex-mode changed
```

## 📊 Преимущества

### ✅ Устранено дублирование:
- **Один DAG** вместо трех параллельных конвейеров
- **Единый QdrantWriter** вместо двух индексаторов
- **Общие нормализаторы** с плагинами
- **Единый StateManager** для всех источников

### ✅ Улучшена модульность:
- **SourceAdapter** - легко добавить новые источники
- **PipelineStep** - легко добавить новые шаги
- **Плагины нормализации** - специфичные правила
- **Контракты** - четкие интерфейсы

### ✅ Упрощена поддержка:
- **Один entrypoint** для всех источников
- **Единая конфигурация** и логирование
- **Общие тесты** для всех компонентов
- **Четкая структура** кода

## 🧪 Тестирование

### Созданы тесты:
- **test_unified_contracts.py** - контракты и интерфейсы
- **test_unified_adapters.py** - адаптеры источников
- **test_unified_pipeline.py** - PipelineDAG
- **test_unified_integration.py** - интеграционные тесты
- **test_unified_indexing.py** - QdrantWriter и индексация

### Запуск тестов:
```bash
python -m pytest tests/test_unified_*.py -v
```

## 🔄 Миграция

### Поэтапный переход:
1. **Этап 1** ✅ - Создана новая архитектура
2. **Этап 2** 🔄 - Тестирование на реальных данных
3. **Этап 3** ⏳ - Переключение на новый пайплайн
4. **Этап 4** ⏳ - Удаление старых компонентов

### Совместимость:
- **Старый `run.py`** остается для совместимости
- **Новый `run_unified.py`** - единый entrypoint
- **Постепенный переход** без поломки существующей функциональности

## 🎉 Результат

**Архитектура стала:**
- **📉 Проще** - один путь вместо трех
- **🔧 Гибче** - легко добавлять источники
- **📖 Понятнее** - четкие контракты
- **🚀 Масштабируемее** - модульная структура

**Рефакторинг успешно завершен!** 🎉
