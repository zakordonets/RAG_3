# Руководство по стилю кода

## Общие принципы

### 1. Читаемость превыше всего
Код должен быть понятен не только автору, но и другим разработчикам через 6 месяцев.

### 2. Консистентность
Следуйте единому стилю во всем проекте.

### 3. Простота
Избегайте излишней сложности. Простое решение часто лучше элегантного.

## Python Style Guide

### PEP 8 Compliance
Следуйте [PEP 8](https://pep8.org/) с некоторыми дополнениями:

```python
# Хорошо
def calculate_user_score(user_id: int, actions: list[dict]) -> float:
    """Вычисляет рейтинг пользователя на основе действий."""
    if not actions:
        return 0.0

    total_score = sum(action.get('score', 0) for action in actions)
    return total_score / len(actions)

# Плохо
def calc_score(uid,acts):
    if not acts:return 0.0
    return sum(a.get('score',0) for a in acts)/len(acts)
```

### Именование

#### Переменные и функции
```python
# snake_case для переменных и функций
user_name = "john_doe"
def calculate_embedding(text: str) -> list[float]:
    pass

# Константы в UPPER_CASE
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30
```

#### Классы
```python
# PascalCase для классов
class EmbeddingService:
    pass

class ChatCenterAPI:
    pass
```

#### Приватные методы
```python
class EmbeddingService:
    def __init__(self):
        self._model = None  # Один подчеркивание для protected

    def _load_model(self):  # Один подчеркивание для private
        pass

    def __validate_input(self):  # Два подчеркивания для name mangling
        pass
```

### Type Hints

Всегда используйте type hints:

```python
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass

@dataclass
class SearchResult:
    id: str
    score: float
    payload: Dict[str, Any]
    vector: Optional[List[float]] = None

def process_query(
    query: str,
    context: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], None]:
    """Обрабатывает пользовательский запрос."""
    pass
```

### Docstrings

Используйте Google style docstrings:

```python
def hybrid_search(
    dense_vector: List[float],
    sparse_vector: Dict[str, List],
    k: int = 20,
    boosts: Optional[Dict[str, float]] = None
) -> List[Dict[str, Any]]:
    """
    Выполняет гибридный поиск по dense и sparse векторам.

    Args:
        dense_vector: Dense вектор запроса (1024 dim)
        sparse_vector: Sparse вектор запроса {indices: [...], values: [...]}
        k: Количество кандидатов для поиска
        boosts: Дополнительные бусты для метаданных

    Returns:
        Список документов с релевантностью, отсортированный по убыванию score

    Raises:
        QdrantError: При ошибках подключения к Qdrant
        ValidationError: При неверном формате векторов

    Example:
        >>> dense_vec = [0.1, 0.2, ...]
        >>> sparse_vec = {"indices": [1, 2], "values": [0.5, 0.3]}
        >>> results = hybrid_search(dense_vec, sparse_vec, k=10)
        >>> len(results)
        10
    """
    pass
```

### Импорты

```python
# Стандартная библиотека
import os
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass

# Сторонние библиотеки
import requests
from loguru import logger
from qdrant_client import QdrantClient

# Локальные импорты
from app.config import CONFIG
from app.services.embeddings import embed_dense
```

### Обработка ошибок

```python
# Хорошо: специфичные исключения
class EmbeddingError(Exception):
    """Ошибка при создании эмбеддингов."""
    pass

class LLMError(Exception):
    """Ошибка при обращении к LLM."""
    pass

def embed_text(text: str) -> List[float]:
    try:
        return model.encode(text)
    except Exception as e:
        raise EmbeddingError(f"Failed to embed text: {e}") from e

# Плохо: общие исключения
def embed_text(text: str) -> List[float]:
    try:
        return model.encode(text)
    except:
        return []
```

### Логирование

```python
from loguru import logger

def process_query(query: str) -> Dict[str, Any]:
    logger.info("Processing query", query_length=len(query))

    try:
        result = do_processing(query)
        logger.info("Query processed successfully",
                   processing_time=result.time_taken)
        return result
    except Exception as e:
        logger.error("Query processing failed",
                    error=str(e), query=query[:100])
        raise
```

## Структура файлов

### Модули
```python
# app/services/embeddings.py
"""
Модуль для работы с эмбеддингами.

Содержит функции для создания dense и sparse эмбеддингов
с использованием различных моделей.
"""

from __future__ import annotations

import os
from typing import Iterable
import requests
from loguru import logger
from sentence_transformers import SentenceTransformer

from app.config import CONFIG

# Константы модуля
EMBEDDING_DIM = CONFIG.embedding_dim
SPARSE_SERVICE_URL = CONFIG.sparse_service_url

# Глобальные переменные
_dense_model: SentenceTransformer | None = None

def _get_dense_model() -> SentenceTransformer:
    """Получает модель для dense эмбеддингов."""
    global _dense_model
    if _dense_model is None:
        logger.info(f"Loading dense embedding model: {CONFIG.embedding_model_name}")
        _dense_model = SentenceTransformer(CONFIG.embedding_model_name)
    return _dense_model

def embed_dense(text: str) -> List[float]:
    """Создает dense эмбеддинг для текста."""
    model = _get_dense_model()
    return model.encode(text).tolist()

def embed_sparse(text: str) -> Dict[str, List]:
    """Создает sparse эмбеддинг для текста."""
    # Реализация...
    pass
```

### Классы
```python
class ChatCenterAPI:
    """Клиент для работы с Chat Center API."""

    def __init__(self, base_url: str = "http://localhost:9000"):
        """
        Инициализирует API клиент.

        Args:
            base_url: Базовый URL API сервера
        """
        self.base_url = base_url
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self) -> None:
        """Настраивает HTTP сессию."""
        self.session.headers.update({
            'User-Agent': 'ChatCenter-API-Client/1.0',
            'Content-Type': 'application/json'
        })

    def ask(self, message: str, chat_id: str = "default") -> Dict[str, Any]:
        """
        Задает вопрос системе.

        Args:
            message: Текст вопроса
            chat_id: Идентификатор чата

        Returns:
            Ответ системы с источниками

        Raises:
            APIError: При ошибке API
        """
        # Реализация...
        pass
```

## Конфигурация

### Использование dataclasses
```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class AppConfig:
    """Конфигурация приложения."""

    # API настройки
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # LLM настройки
    yandex_api_key: str = ""
    yandex_catalog_id: str = ""
    default_llm: str = "yandex"

    # Telegram настройки
    telegram_bot_token: str = ""
    telegram_poll_interval: float = 1.0

    # Поиск
    hybrid_dense_weight: float = 0.7
    hybrid_sparse_weight: float = 0.3
    rerank_top_n: int = 10

    # Краулинг
    crawl_deny_prefixes: List[str] = field(default_factory=lambda: [
        "https://docs-chatcenter.edna.ru/blog/",
        "https://docs-chatcenter.edna.ru/search/"
    ])

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Создает конфигурацию из переменных окружения."""
        # Реализация...
        pass
```

## Тестирование

### Структура тестов
```python
# tests/test_embeddings.py
import pytest
from unittest.mock import Mock, patch
from app.services.embeddings import embed_dense, embed_sparse

class TestEmbeddings:
    """Тесты для модуля эмбеддингов."""

    @patch('app.services.embeddings._get_dense_model')
    def test_embed_dense_success(self, mock_model):
        """Тест успешного создания dense эмбеддинга."""
        # Arrange
        mock_model.return_value.encode.return_value = [0.1, 0.2, 0.3]
        text = "test text"

        # Act
        result = embed_dense(text)

        # Assert
        assert result == [0.1, 0.2, 0.3]
        mock_model.return_value.encode.assert_called_once_with(text)

    @patch('requests.post')
    def test_embed_sparse_error(self, mock_post):
        """Тест обработки ошибки sparse эмбеддинга."""
        # Arrange
        mock_post.side_effect = requests.RequestException("Network error")

        # Act & Assert
        with pytest.raises(EmbeddingError):
            embed_sparse("test text")
```

### Фикстуры
```python
# tests/conftest.py
import pytest
from app import create_app
from app.config import AppConfig

@pytest.fixture
def app():
    """Создает тестовое приложение."""
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """Создает тестовый клиент."""
    return app.test_client()

@pytest.fixture
def config():
    """Создает тестовую конфигурацию."""
    return AppConfig(
        qdrant_url="http://test-qdrant:6333",
        yandex_api_key="test_key"
    )
```

## Документация

### Комментарии
```python
# Хорошо: объясняет "почему", а не "что"
# Используем RRF для комбинирования результатов, так как он
# показывает лучшие результаты по сравнению с простым усреднением
def rrf_fusion(dense_results, sparse_results, k=60):
    pass

# Плохо: объясняет "что"
# Складываем результаты dense и sparse поиска
def combine_results(dense, sparse):
    pass
```

### README файлы
```markdown
# Модуль эмбеддингов

Модуль для создания векторных представлений текста.

## Функции

- `embed_dense()` - создание dense эмбеддингов
- `embed_sparse()` - создание sparse эмбеддингов

## Пример использования

```python
from app.services.embeddings import embed_dense, embed_sparse

# Dense эмбеддинг
dense_vec = embed_dense("Привет, мир!")

# Sparse эмбеддинг
sparse_vec = embed_sparse("Привет, мир!")
```
```

## Git

### Commit Messages
Используйте [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: добавить поддержку MarkdownV2 форматирования
fix: исправить ошибку timeout в Telegram боте
docs: обновить API документацию
style: применить black форматирование
refactor: вынести конфигурацию в отдельный модуль
test: добавить тесты для эмбеддингов
chore: обновить зависимости
```

### Branch Naming
```
feature/add-web-interface
fix/telegram-timeout-issue
docs/update-api-reference
refactor/extract-config-module
```

## Инструменты

### Форматирование
```bash
# Black для форматирования
black app/ tests/

# isort для сортировки импортов
isort app/ tests/
```

### Линтинг
```bash
# flake8 для проверки стиля
flake8 app/ tests/

# mypy для проверки типов
mypy app/
```

### Pre-commit
```yaml
# .pre-commit-config.yaml
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

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
```

## Заключение

Следование этому руководству поможет поддерживать высокое качество кода и облегчит работу в команде. Помните: хороший код - это код, который легко читать, понимать и изменять.
