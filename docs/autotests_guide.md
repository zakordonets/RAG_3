# Руководство по автотестам

## Обзор

Система включает полный набор автотестов для end-to-end проверки pipeline от извлечения документа до записи в Qdrant. Тесты обеспечивают надежность системы и упрощают разработку.

## Быстрый старт

### Установка зависимостей
```bash
# Установка всех зависимостей
make dev-setup

# Или вручную
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Запуск тестов
```bash
# Быстрые тесты (рекомендуется для разработки)
make test-fast

# Все тесты
make test

# Конкретный тип тестов
make test-unit        # Unit тесты
make test-integration # Интеграционные тесты
make test-e2e         # End-to-end тесты
make test-slow        # Медленные тесты
```

### Профили запуска

| Профиль | Команда | Назначение |
| --- | --- | --- |
| `fast` | `make test-fast` | Параллельный запуск unit тестов без `slow`, оптимальный цикл разработки. |
| `ci-unit` | `make ci-test` | То же, что GitHub Actions `unit` job: xdist + HTML/JSON отчеты, порог покрытия 70 %. |
| `ci-full` | `make ci-test-all` | Полный прогон с параллелизацией, используется для ночных/ручных проверок. |
| `coverage` | `make coverage-extended` | Строгая проверка покрытия (`--cov-fail-under=70`) + `coverage.xml/htmlcov`. |
| `property` | `python -m pytest tests/property --maxfail=1 --hypothesis-profile=ci` | Property-based тесты на Hypothesis. Установите `HYPOTHESIS_PROFILE=ci` для детерминизма. |

## Структура тестов

### Типы тестов

#### Unit тесты
- **Местоположение**: `tests/test_*.py`
- **Цель**: Тестирование отдельных функций и классов
- **Время выполнения**: < 1 секунды
- **Примеры**: Валидация конфигурации, обработка данных, утилиты

#### Integration тесты
- **Маркер**: `@pytest.mark.integration`
- **Цель**: Тестирование взаимодействия компонентов
- **Время выполнения**: 1-10 секунд
- **Примеры**: Подключение к Redis, работа с Qdrant, интеграция с LLM

#### End-to-End тесты
- **Маркер**: `@pytest.mark.e2e`
- **Цель**: Полное тестирование pipeline
- **Время выполнения**: 10-60 секунд
- **Примеры**: Полный RAG pipeline, индексация → поиск → генерация ответа

#### Медленные тесты
- **Маркер**: `@pytest.mark.slow`
- **Цель**: Тесты производительности и полной индексации
- **Время выполнения**: > 60 секунд
- **Примеры**: Полная переиндексация, нагрузочные тесты

#### Property-based тесты
- **Местоположение**: `tests/property/`
- **Инструменты**: [Hypothesis](https://hypothesis.readthedocs.io)
- **Цель**: Генеративная проверка инвариантов (whitelist ссылок, устойчивость чанкинга)
- **Запуск**: `python -m pytest tests/property --hypothesis-profile=ci`
- **Советы**: Экспортируйте `HYPOTHESIS_PROFILE=ci` для повторяемости; увеличивайте `--maxfail` только при локальной отладке.

### Структура файлов

```
tests/
├── conftest.py                              # Фикстуры pytest
│
├── fixtures/                                # Общие тестовые данные
│   ├── data_samples.py                      # Литералы markdown/URL/чанков
│   └── factories.py                         # Фабрики payload и структур
│
├── Core тесты
│   ├── test_unified_pipeline.py             # Унифицированный pipeline
│   ├── test_unified_indexing.py             # Индексация
│   ├── test_unified_integration.py          # Интеграционные тесты
│   ├── test_rag_system_comprehensive.py     # Комплексные RAG тесты
│
├── Quality тесты
│   ├── test_ragas_quality.py                # RAGAS метрики качества
│   ├── test_integration_phase2.py           # Phase 2 интеграция
│   ├── test_monitoring_quality.py           # Мониторинг качества
│   ├── test_indexing_quality.py             # Качество индексации
│
├── Retrieval тесты
│   ├── test_retrieval_auto_merge.py         # Auto-merge функциональность
│   ├── test_retrieval_auto_merge_extended.py # Расширенные тесты auto-merge
│
├── Data loading тесты
│   ├── test_universal_loader.py             # Универсальный загрузчик
│   ├── test_docusaurus_crawler.py           # Docusaurus crawler
│   ├── test_docusaurus_utils.py             # Утилиты Docusaurus
│   ├── test_sdk_docs_integration.py         # Интеграционные тесты SDK документации
│   ├── test_sdk_docs_pipeline.py            # Smoke-тесты пайплайна SDK документации
│   ├── test_ingestion_config_loader.py     # Тесты загрузки конфигурации индексации
│
├── Chunking тесты
│   ├── test_adaptive_chunker.py             # Адаптивный chunking
│   ├── test_universal_chunker_v2.py         # Универсальный chunker v2
│
├── Integration тесты
│   ├── test_qdrant_integration.py           # Интеграция с Qdrant
│   ├── test_unified_adapters.py             # Адаптеры
│   ├── test_unified_contracts.py            # Контракты
│   ├── test_unified_tokenizer.py            # Токенизация
│
├── Utility тесты
│   ├── test_utils.py                        # Общие утилиты
│   ├── test_links.py                        # Обработка ссылок
│   ├── test_pathing.py                      # Работа с путями
│   ├── test_clean.py                        # Очистка данных
│   ├── test_short_pages_fixes.py            # Исправления коротких страниц
│   ├── test_updated_config.py               # Конфигурация
│
└── services/                                # Тесты сервисов
    ├── test_context_optimizer.py            # Оптимизация контекста
    ├── test_llm_router.py                   # LLM роутер
    └── test_telegram_adapter.py             # Telegram адаптер

scripts/
├── run_tests.py                             # Запуск тестов
├── init_qdrant.py                           # Инициализация Qdrant
├── init_quality_db.py                       # Инициализация БД качества
├── clear_collection.py                      # Очистка коллекции
├── recreate_collection_with_sparse.py       # Пересоздание с sparse
├── reindex_instructions.py                  # Инструкции по индексации
│
└── Диагностические скрипты
    ├── check_canonical_url.py               # Проверка canonical URL
    ├── check_file_indexed.py                # Проверка индексации файла
    ├── check_full_text.py                   # Проверка полного текста
    ├── check_start_urls.py                  # Проверка start URLs
    ├── check_text_field.py                  # Проверка текстовых полей
    ├── deep_analysis.py                     # Глубокий анализ
    └── test_retrieval_for_url.py            # Тест поиска по URL

pytest.ini                                   # Конфигурация pytest
Makefile                                     # Команды разработки
requirements-dev.txt                         # Зависимости для разработки
```

## Основные тесты

### 1. Unified Pipeline Tests

**Файл**: `tests/test_unified_pipeline.py`

**Покрываемые сценарии**:
- Полный унифицированный pipeline индексации
- Тестирование DAG архитектуры
- Проверка всех этапов обработки документов
- Валидация выходных данных

### 2. RAG System Comprehensive Tests

**Файл**: `tests/test_rag_system_comprehensive.py`

**Функциональность**:
- Комплексное тестирование RAG системы
- End-to-end тесты: запрос → поиск → генерация → ответ
- Проверка quality system (RAGAS метрики)
- Тестирование различных сценариев использования

### 3. RAGAS Quality Tests

**Файл**: `tests/test_ragas_quality.py`

**Покрываемые метрики**:
- **Faithfulness**: Соответствие ответа контексту
- **Answer Relevancy**: Релевантность ответа запросу
- **Context Precision**: Точность выбора контекста
- Сохранение результатов в БД качества
- Анализ корреляции с пользовательским фидбеком

### 4. Auto-Merge Retrieval Tests

**Файлы**:
- `tests/test_retrieval_auto_merge.py`
- `tests/test_retrieval_auto_merge_extended.py`

**Функциональность**:
- Тестирование функции Auto-Merge соседних чанков
- Проверка улучшения контекста
- Валидация метаданных объединения
- Сравнение с базовым поиском

### 5. Integration Tests

**Файл**: `tests/test_integration_phase2.py`

**Покрываемые компоненты**:
- Интеграция всех компонентов Phase 2
- Circuit Breakers и устойчивость к сбоям
- Кэширование (Redis + in-memory)
- Rate limiting и безопасность
- Мониторинг и метрики Prometheus

### 6. Services Tests

**Файлы в** `tests/services/`:
- **test_context_optimizer.py**: Оптимизация контекста, дедупликация
- **test_llm_router.py**: Маршрутизация LLM с fallback
- **test_telegram_adapter.py**: Telegram bot адаптер

### 7. Unified Indexing Tests

**Файл**: `tests/test_unified_indexing.py`

**Функциональность**:
- Тестирование единой системы индексации
- Проверка адаптеров источников данных
- Валидация метаданных и эмбеддингов
- Тестирование записи в Qdrant с sparse векторами

### 8. SDK Documentation Ingestion Tests

**Файлы**:
- `tests/test_sdk_docs_integration.py` - Интеграционные тесты
- `tests/test_sdk_docs_pipeline.py` - Smoke-тесты пайплайна
- `tests/test_ingestion_config_loader.py` - Тесты конфигурации
- `tests/test_docusaurus_crawler.py` - Тесты crawler с `top_level_meta`
- `tests/test_docusaurus_utils.py` - Тесты утилит с пустым `site_docs_prefix`

**Функциональность**:
- **Поддержка пустого `site_docs_prefix`**: Тестирование формирования URL без префикса `/docs` для SDK документации
- **Работа с `top_level_meta`**: Проверка добавления метаданных платформ (android, ios, web, main) в документы
- **Множественные источники**: Тестирование конфигурации с несколькими источниками Docusaurus
- **Интеграция адаптера**: Проверка работы `DocusaurusAdapter` с `top_level_meta` и пустым префиксом
- **Приоритет метаданных**: Тестирование корректного мержа `top_level_meta` с `_category_.json`
- **Конфигурация**: Валидация загрузки и обработки конфигурации с SDK источниками

**Примеры тестов**:

```python
# Тест пустого site_docs_prefix
def test_fs_to_url_empty_prefix():
    """Тест формирования URL без префикса /docs"""
    url = fs_to_url(
        docs_root=Path("C:/SDK_docs/docs"),
        abs_path=Path("C:/SDK_docs/docs/android/intro.md"),
        site_base="https://docs-sdk.edna.ru",
        docs_prefix=""
    )
    assert url == "https://docs-sdk.edna.ru/android/intro"

# Тест адаптера с top_level_meta
def test_adapter_with_top_level_meta():
    """Тест адаптера с метаданными платформ"""
    adapter = DocusaurusAdapter(
        docs_root="...",
        site_base_url="https://docs-sdk.edna.ru",
        site_docs_prefix="",
        top_level_meta={
            "android": {"sdk_platform": "android", "product": "sdk"}
        }
    )
    docs = list(adapter.iter_documents())
    assert docs[0].meta["sdk_platform"] == "android"
```

**Запуск тестов SDK документации**:

```bash
# Все тесты SDK документации
python -m pytest tests/test_sdk_docs_integration.py tests/test_sdk_docs_pipeline.py -v

# Только интеграционные тесты
python -m pytest tests/test_sdk_docs_integration.py -v

# Только smoke-тесты пайплайна
python -m pytest tests/test_sdk_docs_pipeline.py -v

# Тесты утилит с пустым префиксом
python -m pytest tests/test_docusaurus_utils.py -k "empty_prefix" -v

# Тесты crawler с top_level_meta
python -m pytest tests/test_docusaurus_crawler.py -k "top_level" -v
```

## Команды разработки

### Makefile команды

```bash
# Тестирование
make test              # Все тесты
make test-unit         # Unit тесты
make test-integration  # Интеграционные тесты
make test-e2e          # End-to-end тесты
make test-slow         # Медленные тесты
make test-fast         # Быстрые тесты (без медленных)
make test-pipeline     # Тесты unified pipeline
make test-quality      # Тесты системы качества

# Качество кода
make lint              # Линтинг (flake8, mypy)
make format            # Форматирование (black, isort)

# Разработка
make dev-setup         # Настройка среды разработки
make install           # Установка зависимостей
make clean             # Очистка временных файлов

# Мониторинг
make check-services    # Проверка сервисов (Redis, Qdrant)

# Индексация
make reindex           # Полная переиндексация через ingestion pipeline
make reindex-incremental # Инкрементальная переиндексация

# Отладка
make debug-collection  # Отладка коллекции Qdrant
make debug-pipeline    # Отладка unified pipeline
make debug-retrieval   # Отладка поиска по URL
```

### Скрипт запуска тестов

```bash
# Базовые команды
python scripts/run_tests.py --type unit --verbose
python scripts/run_tests.py --type integration
python scripts/run_tests.py --type e2e

# С дополнительными опциями
python scripts/run_tests.py --type fast --coverage
python scripts/run_tests.py --type unit --parallel
python scripts/run_tests.py --type fast --check-services

# Помощь
python scripts/run_tests.py --help
```

## Добавление новых тестов

### 1. Создание unit теста

```python
# tests/test_new_feature.py
import pytest
from app.services.new_service import NewService

class TestNewFeature:
    def test_basic_functionality(self):
        """Тест базовой функциональности"""
        service = NewService()
        result = service.process("test_input")
        assert result == "expected_output"

    def test_error_handling(self):
        """Тест обработки ошибок"""
        service = NewService()
        with pytest.raises(ValueError):
            service.process("invalid_input")
```

### 2. Создание интеграционного теста

```python
# tests/test_integration.py
import pytest
from app.services.integration_service import IntegrationService

class TestIntegration:
    @pytest.mark.integration
    def test_redis_integration(self):
        """Тест интеграции с Redis"""
        service = IntegrationService()
        result = service.cache_data("key", "value")
        assert service.get_cached_data("key") == "value"

    @pytest.mark.integration
    def test_qdrant_integration(self):
        """Тест интеграции с Qdrant"""
        service = IntegrationService()
        # Тест взаимодействия с Qdrant
        pass
```

### 3. Создание end-to-end теста

```python
# tests/test_e2e_custom.py
import pytest
from app.orchestration.orchestrator import handle_query

class TestE2ECustom:
    @pytest.mark.e2e
    def test_full_rag_pipeline(self):
        """Полный тест RAG pipeline"""
        # Тест от запроса до ответа с проверкой качества
        response = handle_query(
            channel="api",
            chat_id="test_user",
            message="Как настроить маршрутизацию?"
        )

        # Проверка структуры ответа
        assert "answer_markdown" in response
        assert response["answer_markdown"] is not None
        assert len(response["sources"]) > 0
        assert "interaction_id" in response

        # Проверка метаданных
        assert "processing_time" in response
        assert response["processing_time"] > 0
```

### 4. Маркировка тестов

```python
import pytest

class TestExamples:
    @pytest.mark.slow
    def test_performance(self):
        """Медленный тест производительности"""
        # Тест производительности
        pass

    @pytest.mark.integration
    def test_external_service(self):
        """Интеграционный тест"""
        # Тест внешних сервисов
        pass

    @pytest.mark.e2e
    def test_full_workflow(self):
        """End-to-end тест"""
        # Полный workflow
        pass
```

## CI/CD Pipeline

### GitHub Actions

Автоматические тесты запускаются при:
- Push в ветки `main`, `develop`
- Создании Pull Request

**Конфигурация**: `.github/workflows/ci.yml`

**Этапы**:
1. **Установка зависимостей**
2. **Линтинг и проверка типов**
3. **Unit тесты**
4. **Интеграционные тесты**
5. **Медленные тесты** (только на main)
6. **Генерация отчетов о покрытии**

### Локальная проверка CI

```bash
# Проверка линтинга
make lint

# Проверка типов
python -m mypy app/

# Запуск тестов как в CI
make ci-test

# Все тесты как в CI
make ci-test-all
```

## Отладка тестов

### Проблемы с тестами

#### 1. Тесты не запускаются
```bash
# Проверка установки pytest
python -m pytest --version

# Проверка конфигурации
python -m pytest --collect-only
```

#### 2. Ошибки импорта
```bash
# Проверка PYTHONPATH
export PYTHONPATH=$PWD:$PYTHONPATH

# Или в Windows
set PYTHONPATH=%CD%;%PYTHONPATH%
```

#### 3. Проблемы с сервисами
```bash
# Проверка доступности сервисов
make check-services

# Запуск тестов без проверки сервисов
python scripts/run_tests.py --type unit --no-check-services
```

### Отладочные команды

```bash
# Подробный вывод
python scripts/run_tests.py --type unit --verbose

# Остановка на первой ошибке
python -m pytest tests/ -x

# Запуск конкретного теста
python -m pytest tests/test_unified_pipeline.py::TestUnifiedPipeline::test_full_pipeline -v

# Запуск с отладочным выводом
python -m pytest tests/ -s -v

# Проверка коллекции Qdrant
python scripts/check_file_indexed.py

# Тест поиска по конкретному URL
python scripts/test_retrieval_for_url.py
```

## Лучшие практики

### 1. Структура тестов
- Используйте описательные имена тестов
- Группируйте связанные тесты в классы
- Добавляйте docstrings для объяснения тестов
- Повторно используйте `tests.fixtures.data_samples` и `tests.fixtures.factories`, чтобы не дублировать markdown/URL/чанки

### 2. Маркировка
- Используйте соответствующие маркеры (@pytest.mark.slow, @pytest.mark.integration)
- Не помечайте unit тесты как медленные
- Группируйте тесты по типу в отдельные файлы

### 3. Очистка данных
- Всегда очищайте тестовые данные после тестов
- Используйте уникальные идентификаторы для тестовых данных
- Не полагайтесь на порядок выполнения тестов

### 4. Производительность
- Unit тесты должны выполняться быстро (< 1 сек)
- Используйте моки для внешних сервисов в unit тестах
- Группируйте медленные тесты отдельно

### 5. Надежность
- Тесты должны быть детерминированными
- Не используйте случайные данные без фиксации seed
- Проверяйте как успешные, так и неуспешные сценарии

## Мониторинг и отчеты

### Покрытие кода
```bash
# Генерация отчета о покрытии
make test-coverage

# Просмотр отчета
open htmlcov/index.html
```

- Локально `make coverage-extended` применяет порог `--cov-fail-under=70` для `app`, `ingestion`, `adapters`.
- GitHub Actions `unit` job также останавливается при покрытии < 70 % и выгружает `coverage.xml`/`htmlcov`.
- Для релизных проверок используйте `python -m pytest tests/ --cov=app --cov=ingestion --cov=adapters --cov-report=xml --cov-fail-under=80`.

### Логи тестов
```bash
# Сохранение логов
python scripts/run_tests.py --type fast > test_results.log 2>&1

# Просмотр логов в реальном времени
python scripts/run_tests.py --type fast --verbose | tee test_results.log
```

### Статистика тестов
```bash
# Информация о проекте
make info

# Количество тестов
python -m pytest --collect-only -q
```

### CI отчеты
- `unit` job (GitHub Actions) прикрепляет `report.html`, `report.json`, `htmlcov/`, `coverage.xml` и публикует покрытие в Codecov.
- `integration` и `slow` job выгружают `report.html`/`report.json` для последующего анализа.
- Артефакты сохраняются 7 дней; используйте их для ретроспектив отладок и сверки покрытия.

## Заключение

Система автотестов обеспечивает:

- **Надежность**: Все критические пути покрыты тестами
- **Быстроту**: Unit тесты выполняются за 30 секунд
- **Автоматизацию**: CI/CD pipeline для непрерывной интеграции
- **Удобство**: Простые команды для разработки
- **Расширяемость**: Легко добавлять новые тесты

## Дополнительные ресурсы

Для получения дополнительной информации см.:
- 📖 [Architecture Overview](architecture.md) - Архитектура системы
- 📋 [Technical Specification](technical_specification.md) - Техническая спецификация
- 🛠️ [Development Guide](development_guide.md) - Руководство разработчика
- 🔧 [Internal API](internal_api.md) - Внутренние сервисы и API
- 📝 [API Reference](api_reference.md) - Справочник публичного API
- 📚 [README.md](../README.md) - Основная документация проекта

## История изменений

### v4.3.0 (Октябрь 2025)
- ✅ Полное покрытие унифицированного pipeline тестами
- ✅ Добавлены тесты RAGAS quality system
- ✅ Тесты Auto-Merge функциональности
- ✅ Комплексные тесты RAG системы
- ✅ Тесты для всех сервисов (Context Optimizer, LLM Router, etc.)
- ✅ Обновлена структура тестов под новую архитектуру
- ✅ **Тесты SDK документации**: Добавлены интеграционные тесты для загрузчика SDK документации
  - Тесты поддержки пустого `site_docs_prefix`
  - Тесты работы с `top_level_meta` для платформ (android, ios, web, main)
  - Smoke-тесты полного пайплайна индексации SDK документации
  - Тесты загрузки конфигурации с множественными источниками

### v4.2.0
- Тесты для гибридного поиска (dense + sparse)
- Интеграционные тесты с Qdrant
- Тесты Circuit Breakers

### v4.1.0
- Базовая структура автотестов
- Unit и интеграционные тесты
- CI/CD pipeline
