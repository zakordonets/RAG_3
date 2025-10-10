# Руководство по разработке

## 📚 О документе

Практическое руководство для разработчиков, работающих с RAG-системой для edna Chat Center.

**Версия**: v4.3.1
**Дата обновления**: 9 октября 2024

## 🎯 Для кого этот документ

- **Новые разработчики** - быстрый старт и настройка окружения
- **Контрибьюторы** - стандарты кода и workflow
- **Расширение функциональности** - добавление новых компонентов

## 🔗 Связанная документация

| Документ | Описание |
|----------|----------|
| [Architecture](architecture.md) | Архитектура системы и компоненты |
| [Internal API](internal_api.md) | API внутренних сервисов |
| [Autotests Guide](autotests_guide.md) | Тестирование и QA |
| [Adding Data Sources](adding_data_sources.md) | Интеграция новых источников данных |
| [Deployment Guide](deployment_guide.md) | Развертывание в production |
| [API Reference](api_reference.md) | REST API документация |

---

## 🚀 Быстрый старт

### Для новых разработчиков (5 минут)

```bash
# 1. Клонирование
git clone <repository-url>
cd RAG_clean

# 2. Окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Переменные окружения
cp env.example .env
# Отредактируйте .env с вашими ключами

# 5. Инициализация
python scripts/init_qdrant.py
python scripts/init_quality_db.py

# 6. Проверка работоспособности
pytest tests/ -v

# 7. Запуск в dev режиме
python wsgi.py
```

### Первый запрос к API

```bash
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "test",
    "chat_id": "dev_123",
    "message": "Как настроить маршрутизацию?"
  }'
```

---

## 🏗️ Архитектура проекта

Полная структура описана в [architecture.md](architecture.md). Основные компоненты:

```
RAG_clean/
├── app/              # Flask API и бизнес-логика
│   ├── routes/       # REST endpoints (chat, admin, quality)
│   ├── services/     # Сервисы (embeddings, retrieval, LLM)
│   └── infrastructure/  # Кэш, метрики, circuit breakers
│
├── ingestion/        # DAG-архитектура индексации
│   ├── adapters/     # Адаптеры источников данных
│   ├── pipeline/     # Обработка документов
│   └── chunking/     # Universal chunker
│
├── adapters/         # Каналы коммуникации (Telegram и др.)
└── tests/            # Автотесты (29 файлов)
```

**Подробнее**: [architecture.md](architecture.md), [internal_api.md](internal_api.md)

---

## ⚙️ Настройка среды разработки

### 1. Необходимые инструменты

```bash
# Python 3.11+
python --version

# Git
git --version

# Docker (опционально, для полного стека)
docker --version
docker-compose --version
```

### 2. Настройка IDE (VS Code рекомендуется)

Создайте `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"],
  "editor.formatOnSave": true,
  "editor.rulers": [88, 120],
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true
  }
}
```

### 3. Pre-commit hooks

```bash
# Установка
pip install pre-commit
pre-commit install

# Создание конфигурации
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=120]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
EOF

# Проверка
pre-commit run --all-files
```

### 4. Запуск зависимостей через Docker

```bash
# Запуск Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# Запуск Redis (для кэширования)
docker run -d -p 6379:6379 redis

# Или полный стек
docker-compose up -d qdrant redis
```

---

## 👨‍💻 Workflow разработки

### Типичный цикл разработки

```bash
# 1. Создайте feature branch
git checkout -b feature/your-feature-name

# 2. Внесите изменения
# ... редактируйте код ...

# 3. Запустите тесты
pytest tests/ -v

# 4. Проверьте код
black .
flake8 .
mypy app/

# 5. Коммит
git add .
git commit -m "feat: добавлена новая функция"

# 6. Push и создайте PR
git push origin feature/your-feature-name
```

### Naming Conventions

**Branches:**
- `feature/` - новая функциональность
- `fix/` - исправление багов
- `refactor/` - рефакторинг
- `docs/` - документация

**Commits** (следуем [Conventional Commits](https://www.conventionalcommits.org/)):
- `feat:` - новая функция
- `fix:` - исправление бага
- `refactor:` - рефакторинг кода
- `docs:` - изменения в документации
- `test:` - добавление/изменение тестов
- `chore:` - рутинные задачи

**Код:**
- Файлы: `snake_case.py`
- Классы: `PascalCase`
- Функции/переменные: `snake_case`
- Константы: `UPPER_SNAKE_CASE`

---

## 🔧 Основные задачи разработки

### 1. Добавление нового API endpoint

```python
# app/routes/custom.py
from flask import Blueprint, request, jsonify
from loguru import logger

custom_bp = Blueprint('custom', __name__)

@custom_bp.route('/v1/custom/action', methods=['POST'])
def custom_action():
    """
    Custom action endpoint
    ---
    tags:
      - Custom
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            param:
              type: string
    responses:
      200:
        description: Success
    """
    try:
        data = request.get_json()
        result = process_custom_action(data)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Custom action failed: {e}")
        return jsonify({"error": str(e)}), 500

# app/__init__.py - регистрация
app.register_blueprint(custom_bp)
```

### 2. Добавление нового сервиса

```python
# app/services/custom_service.py
from typing import Dict, Any
from loguru import logger

class CustomService:
    """Кастомный сервис для специфичной бизнес-логики."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("CustomService initialized")

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка данных."""
        logger.debug(f"Processing data: {data}")

        # Бизнес-логика
        result = self._do_processing(data)

        logger.info("Processing completed")
        return result

    def _do_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Внутренняя логика обработки."""
        # Реализация
        pass
```

### 3. Добавление нового LLM провайдера

```python
# app/services/core/llm_router.py

def _custom_llm_complete(prompt: str, max_tokens: int = 800) -> str:
    """Интеграция с кастомным LLM."""
    import requests
    from app.config.app_config import CONFIG

    if not CONFIG.custom_llm_api_key:
        raise RuntimeError("Custom LLM API key not set")

    response = requests.post(
        CONFIG.custom_llm_url,
        headers={"Authorization": f"Bearer {CONFIG.custom_llm_api_key}"},
        json={"prompt": prompt, "max_tokens": max_tokens},
        timeout=60
    )
    response.raise_for_status()
    return response.json()["text"]

# Добавьте в fallback chain
def generate_answer(query: str, context: list[dict]) -> str:
    providers = ["YANDEX", "CUSTOM_LLM", "GPT5"]  # Добавили CUSTOM_LLM

    for provider in providers:
        try:
            if provider == "CUSTOM_LLM":
                return _custom_llm_complete(prompt)
            # ... другие провайдеры
        except Exception as e:
            logger.warning(f"{provider} failed: {e}")
            continue
```

**Подробнее о добавлении источников данных**: [adding_data_sources.md](adding_data_sources.md)

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С выводом
pytest -v

# Конкретный файл
pytest tests/test_services.py

# Конкретный тест
pytest tests/test_services.py::test_embedding

# С покрытием
pytest --cov=app --cov-report=html

# Параллельно (быстрее)
pytest -n auto
```

### Структура тестов

```python
# tests/test_my_feature.py
import pytest
from unittest.mock import Mock, patch
from app.services.my_service import MyService

@pytest.fixture
def my_service():
    """Фикстура для создания сервиса."""
    config = {"param": "value"}
    return MyService(config)

def test_my_service_success(my_service):
    """Тест успешного выполнения."""
    result = my_service.process({"input": "test"})
    assert result["status"] == "success"
    assert "output" in result

def test_my_service_error(my_service):
    """Тест обработки ошибок."""
    with pytest.raises(ValueError):
        my_service.process({"invalid": "data"})

@patch('app.services.my_service.external_api_call')
def test_my_service_with_mock(mock_api, my_service):
    """Тест с моком внешнего вызова."""
    mock_api.return_value = {"data": "mocked"}

    result = my_service.process({"input": "test"})

    mock_api.assert_called_once()
    assert result["data"] == "mocked"
```

**Полное руководство**: [autotests_guide.md](autotests_guide.md)

---

## ✅ Code Quality и Review

### Автоматические проверки

```bash
# Форматирование (автоисправление)
black .

# Линтинг
flake8 . --max-line-length=120 --extend-ignore=E203

# Type checking
mypy app/ --ignore-missing-imports

# Security check
bandit -r app/

# All-in-one
make lint  # если настроен Makefile
```

### Checklist для Code Review

**Автор PR:**
- [ ] Код следует архитектурным принципам
- [ ] Добавлены тесты (покрытие >= 80%)
- [ ] Обновлена документация
- [ ] Пройдены все линтеры
- [ ] Нет hardcoded значений
- [ ] Логирование добавлено где необходимо
- [ ] Обработка ошибок реализована

**Ревьюер:**
- [ ] Код читаемый и понятный
- [ ] Нет дублирования
- [ ] Производительность приемлема
- [ ] Безопасность не нарушена
- [ ] API контракт не сломан

### Примеры хорошего кода

**✅ Хорошо:**
```python
def calculate_cosine_similarity(
    vec_a: list[float],
    vec_b: list[float]
) -> float:
    """
    Вычисляет косинусное сходство между векторами.

    Args:
        vec_a: Первый вектор
        vec_b: Второй вектор

    Returns:
        Косинусное сходство [0, 1]

    Raises:
        ValueError: Если векторы разной длины
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have same length")

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)
```

**❌ Плохо:**
```python
def calc(a, b):
    return sum(a[i]*b[i] for i in range(len(a)))/(sum(a[i]**2 for i in range(len(a)))**0.5*sum(b[i]**2 for i in range(len(b)))**0.5) if sum(a[i]**2 for i in range(len(a)))**0.5 != 0 else 0
```

---

## 🐛 Отладка и профилирование

### Логирование

```python
from loguru import logger

# Настройка (в app/__init__.py)
logger.add("logs/debug.log", level="DEBUG", rotation="1 day")
logger.add("logs/error.log", level="ERROR", rotation="1 week")

# Использование
logger.debug("Детальная отладочная информация")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка", exc_info=True)  # С stack trace

# Структурированное логирование
logger.info("Query processed", query_len=len(query), time_ms=elapsed_ms)
```

### Профилирование производительности

```python
import cProfile
import pstats

def profile_function():
    """Профилирование функции."""
    profiler = cProfile.Profile()
    profiler.enable()

    # Ваш код
    result = heavy_computation()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Топ 20 функций
```

### Мониторинг памяти

```python
import tracemalloc

tracemalloc.start()

# Ваш код
result = process_large_data()

current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.1f} MB")
print(f"Peak: {peak / 1024 / 1024:.1f} MB")

tracemalloc.stop()
```

### Отладка через Makefile

```bash
# Просмотр логов
make logs

# Проверка метрик
make metrics

# Диагностика системы
make diagnose
```

---

## 🚀 CI/CD

### GitHub Actions

Основной workflow в `.github/workflows/ci.yml`:

```yaml
name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Lint
        run: |
          black --check .
          flake8 .

      - name: Test
        run: pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Deployment Pipeline

```bash
# Production deployment
make deploy-prod

# Staging deployment
make deploy-staging

# Rollback
make rollback
```

**Полное руководство**: [deployment_guide.md](deployment_guide.md)

---

## 📚 Архитектурные принципы

### 1. Разделение ответственности (Separation of Concerns)

- **Routes** - HTTP endpoints, валидация входных данных
- **Services** - бизнес-логика
- **Infrastructure** - кэширование, метрики, circuit breakers
- **Adapters** - внешние каналы коммуникации

### 2. Dependency Injection

```python
# ✅ Хорошо
class Orchestrator:
    def __init__(self, embedding_svc, retrieval_svc, llm_svc):
        self.embedding_svc = embedding_svc
        self.retrieval_svc = retrieval_svc
        self.llm_svc = llm_svc

# ❌ Плохо
class Orchestrator:
    def __init__(self):
        self.embedding_svc = EmbeddingService()  # Жесткая зависимость
```

### 3. Error Handling

```python
# ✅ Правильная обработка ошибок
class ServiceError(Exception):
    """Базовая ошибка сервиса."""
    pass

class EmbeddingError(ServiceError):
    """Ошибка при создании embeddings."""
    pass

def embed_text(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    try:
        return model.encode(text)
    except Exception as e:
        raise EmbeddingError(f"Failed to embed: {e}") from e
```

### 4. Configuration Management

```python
# ✅ Используйте переменные окружения
from dataclasses import dataclass
import os

@dataclass
class AppConfig:
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    yandex_api_key: str = os.getenv("YANDEX_API_KEY", "")

    def validate(self):
        if not self.yandex_api_key:
            raise ValueError("YANDEX_API_KEY is required")
```

---

## 🔗 Полезные ссылки

### Документация проекта
- [Architecture Overview](architecture.md)
- [Internal API Reference](internal_api.md)
- [REST API Documentation](api_reference.md)
- [Adding Data Sources](adding_data_sources.md)
- [Deployment Guide](deployment_guide.md)
- [Testing Guide](autotests_guide.md)

### Внешние ресурсы
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Black Code Style](https://black.readthedocs.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)

### Мониторинг
- [Prometheus Metrics](http://localhost:9090) (локально)
- [Grafana Dashboards](http://localhost:3000) (локально)
- [Swagger UI](http://localhost:9000/apidocs) (API документация)

---

## 🤝 Вклад в проект

### Процесс контрибуции

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения и добавьте тесты
4. Убедитесь, что все проверки проходят
5. Создайте Pull Request с описанием изменений
6. Дождитесь code review

### Сообщение об ошибках

При создании issue включите:
- Описание проблемы
- Шаги для воспроизведения
- Ожидаемое и фактическое поведение
- Версия системы и окружение
- Логи (если применимо)

---

## 📞 Поддержка

**Вопросы?** Создайте issue в репозитории или обратитесь к [README.md](../README.md) для контактов.
