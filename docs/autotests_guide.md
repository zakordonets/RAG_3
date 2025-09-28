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

## Структура тестов

### Типы тестов

#### Unit тесты
- **Местоположение**: `tests/test_*.py`
- **Цель**: Тестирование отдельных функций и классов
- **Время выполнения**: < 1 секунды
- **Примеры**: Валидация конфигурации, обработка данных

#### Integration тесты
- **Маркер**: `@pytest.mark.integration`
- **Цель**: Тестирование взаимодействия компонентов
- **Время выполнения**: 1-10 секунд
- **Примеры**: Подключение к Redis, работа с Qdrant

#### End-to-End тесты
- **Маркер**: `@pytest.mark.e2e`
- **Цель**: Полное тестирование pipeline
- **Время выполнения**: 10-60 секунд
- **Примеры**: Извлечение → chunking → индексация → поиск

#### Медленные тесты
- **Маркер**: `@pytest.mark.slow`
- **Цель**: Тесты производительности и полной индексации
- **Время выполнения**: > 60 секунд
- **Примеры**: Полная переиндексация, нагрузочные тесты

### Структура файлов

```
tests/
├── test_end_to_end_pipeline.py  # Основные E2E тесты
└── test_*.py                    # Другие тесты

scripts/
├── test_full_pipeline.py        # Полный pipeline тест
├── run_tests.py                 # Скрипт запуска тестов
└── test_*.py                    # Специализированные тесты

pytest.ini                       # Конфигурация pytest
Makefile                         # Команды разработки
requirements-dev.txt             # Зависимости для разработки
```

## Основные тесты

### End-to-End Pipeline Tests

**Файл**: `tests/test_end_to_end_pipeline.py`

**Покрываемые сценарии**:
1. **Извлечение и chunking документа**
   - Извлечение документа через Jina Reader
   - Генерация чанков (adaptive/standard стратегии)
   - Валидация качества chunking

2. **Индексация с enhanced metadata**
   - Создание тестовых чанков
   - Индексация в Qdrant
   - Проверка enhanced metadata (complexity_score, semantic_density, boost_factor)
   - Автоматическая очистка тестовых данных

3. **Валидация конфигурации**
   - Проверка корректности параметров
   - Валидация настроек chunking
   - Проверка стратегий crawler

4. **Система плагинов**
   - Регистрация источников данных
   - Создание экземпляров источников
   - Проверка функциональности плагинов

5. **Метрики качества chunking**
   - Анализ размера чанков
   - Проверка сохранности текста
   - Валидация структуры данных

### Полный Pipeline Test

**Файл**: `scripts/test_full_pipeline.py`

**Функциональность**:
- Полный end-to-end тест от извлечения до записи в Qdrant
- Тестирование оптимизированного pipeline
- Анализ качества chunking с разными стратегиями
- Проверка статистики коллекции

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
make reindex           # Полная переиндексация
make reindex-test      # Тестовая переиндексация (5 страниц)

# Отладка
make debug-collection  # Отладка коллекции Qdrant
make debug-pipeline    # Отладка pipeline
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
# tests/test_e2e_pipeline.py
import pytest
from app.services.orchestrator import handle_query

class TestE2EPipeline:
    @pytest.mark.e2e
    def test_full_pipeline(self):
        """Полный тест pipeline"""
        # Тест от запроса до ответа
        response = handle_query("test query")
        assert "answer" in response
        assert response["answer"] is not None
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
python -m pytest tests/test_end_to_end_pipeline.py::TestEndToEndPipeline::test_single_document_extraction_and_chunking -v

# Запуск с отладочным выводом
python -m pytest tests/ -s -v
```

## Лучшие практики

### 1. Структура тестов
- Используйте описательные имена тестов
- Группируйте связанные тесты в классы
- Добавляйте docstrings для объяснения тестов

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

## Заключение

Система автотестов обеспечивает:

- **Надежность**: Все критические пути покрыты тестами
- **Быстроту**: Unit тесты выполняются за 30 секунд
- **Автоматизацию**: CI/CD pipeline для непрерывной интеграции
- **Удобство**: Простые команды для разработки
- **Расширяемость**: Легко добавлять новые тесты

Для получения дополнительной информации см.:
- [Отчет об интеграции автотестов](autotests_integration_report.md)
- [Техническая спецификация](technical_specification.md)
- [README.md](../README.md)
