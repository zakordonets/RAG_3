# 📦 Backup - Устаревшие файлы после рефакторинга

## 🎯 Назначение

Эта папка содержит файлы, которые стали устаревшими после создания **единой архитектуры индексации** с **одним DAG** вместо трех параллельных конвейеров.

## 📁 Содержимое

### 🔧 services/ - Устаревшие сервисы индексации
- **`metadata_aware_indexer.py`** - Продвинутый индексер с метаданными
  - **Заменен на:** `ingestion/pipeline/indexers/qdrant_writer.py`
  - **Причина:** Функциональность объединена в единый QdrantWriter

- **`optimized_pipeline.py`** - Оптимизированный пайплайн
  - **Заменен на:** `ingestion/run_unified.py` + `ingestion/pipeline/dag.py`
  - **Причина:** Создан единый DAG для всех источников

### 🧪 tests/ - Устаревшие тесты
- **`test_end_to_end_pipeline.py`** - End-to-end тесты старого пайплайна
  - **Заменен на:** `tests/test_unified_integration.py`
  - **Причина:** Новые интеграционные тесты для единого DAG

- **`test_pipeline_mock.py`** - Моки старого пайплайна
  - **Заменен на:** `tests/test_unified_*` серия тестов
  - **Причина:** Новые тесты для единой архитектуры

### 📜 scripts/ - Устаревшие скрипты
- **`indexer.py`** - Старый production индексер
  - **Заменен на:** `ingestion/run_unified.py`
  - **Причина:** Единый entrypoint для всех источников

- **`manage_cache.py`** - Управление кешем
  - **Заменен на:** `ingestion/state/state_manager.py`
  - **Причина:** Единое управление состоянием для всех источников

### 📁 ingestion/ - Устаревшие компоненты индексации
- **`pipeline.py`** - Старый общий пайплайн
  - **Заменен на:** `ingestion/run_unified.py` + `ingestion/pipeline/dag.py`
  - **Причина:** Создан единый DAG для всех источников

- **`content_loader.py`** - Универсальный загрузчик
  - **Заменен на:** `ingestion/adapters/` (SourceAdapter)
  - **Причина:** Адаптеры источников более гибкие

- **`processors/`** - Старые процессоры (кроме docusaurus_markdown_processor)
  - **Заменены на:** `ingestion/normalizers/` (плагины)
  - **Причина:** Плагины нормализации более модульные

- **`crawlers/`** - Старые краулеры (кроме docusaurus_fs_crawler)
  - **Заменены на:** `ingestion/adapters/` (SourceAdapter)
  - **Причина:** Адаптеры унифицируют интерфейс

## 🔄 Миграция

### Что изменилось:
```
❌ БЫЛО: 3 параллельных конвейера
├─ Docusaurus Pipeline
├─ Websites Pipeline
└─ General Pipeline

✅ СТАЛО: Единый DAG с адаптерами
└─ Unified Pipeline DAG
   ├─ DocusaurusAdapter
   ├─ WebsiteAdapter
   └─ LocalFolderAdapter (готов)
```

### Новая архитектура:
- **`ingestion/run_unified.py`** - единый entrypoint
- **`ingestion/pipeline/dag.py`** - единый DAG
- **`ingestion/adapters/`** - адаптеры источников
- **`ingestion/normalizers/`** - плагины нормализации
- **`ingestion/state/state_manager.py`** - единое управление состоянием

## ⚠️ Важно

- **Функциональность сохранена** - ничего не потеряно
- **Производительность улучшена** - убрано дублирование
- **Код стал чище** - единые контракты и интерфейсы
- **Легче поддерживать** - один путь вместо трех

## 🚀 Использование новой архитектуры

```bash
# Docusaurus индексация
python ingestion/run_unified.py --source docusaurus --docs-root "C:\CC_RAG\docs"

# Website индексация
python ingestion/run_unified.py --source website --seed-urls "https://example.com"
```

**Дата создания backup:** 2025-10-07
**Причина:** Завершение рефакторинга на единую архитектуру
