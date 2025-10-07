# Руководство по разработке

## Обзор

Данное руководство предназначено для разработчиков, которые хотят внести вклад в проект RAG-системы для edna Chat Center или адаптировать его под свои нужды.

## Структура проекта (v4.0.0)

```
RAG_clean/
├── adapters/                 # Адаптеры каналов связи
│   └── telegram/            # Telegram адаптеры
│       ├── bot.py           # Telegram bot
│       ├── polling.py       # Long polling
│       └── rate_limiter.py  # Rate limiting
├── app/                      # Core API (Flask)
│   ├── __init__.py          # Flask app factory
│   ├── config/              # Конфигурация
│   ├── hardware/            # Hardware management
│   │   └── gpu_manager.py   # Unified GPU manager
│   ├── routes/              # API endpoints
│   │   ├── chat.py          # Chat API
│   │   ├── admin.py         # Admin API
│   │   └── quality.py       # Quality metrics API
│   └── services/            # Модульная бизнес-логика
│       ├── core/            # Основные сервисы
│       │   ├── embeddings.py    # BGE-M3 embeddings
│       │   ├── llm_router.py    # LLM роутинг
│       │   ├── query_processing.py # Обработка запросов
│       │   └── context_optimizer.py # Оптимизация контекста
│       ├── indexing/        # Сервисы индексации (упрощено)
│       ├── quality/         # Сервисы качества
│       ├── search/          # Сервисы поиска
│       └── infrastructure/  # Инфраструктурные сервисы
├── ingestion/               # 🏗️ Единая архитектура индексации
│   ├── adapters/            # 🔌 Адаптеры источников данных
│   │   ├── base.py          # Базовые интерфейсы
│   │   ├── docusaurus.py    # Docusaurus адаптер
│   │   └── website.py       # Website адаптер
│   ├── normalizers/         # 🧹 Плагины нормализации
│   │   ├── base.py          # Базовые нормализаторы
│   │   ├── docusaurus.py    # Docusaurus нормализация
│   │   └── html.py          # HTML нормализация
│   ├── pipeline/            # 🧩 Шаги пайплайна
│   │   ├── dag.py           # Единый DAG пайплайн
│   │   ├── chunker.py       # Шаг чанкинга
│   │   ├── embedder.py      # Шаг эмбеддингов
│   │   └── indexers/
│   │       └── qdrant_writer.py # Единый писатель в Qdrant
│   ├── state/               # 📊 Управление состоянием
│   │   └── state_manager.py # Единый менеджер состояния
│   ├── utils/               # 📦 Утилиты
│   │   ├── docusaurus_clean.py  # Очистка MDX
│   │   ├── docusaurus_links.py  # ContentRef обработка
│   │   └── docusaurus_pathing.py # Преобразование путей
│   ├── crawlers/            # 🕷️ Краулеры (упрощено)
│   │   └── docusaurus_fs_crawler.py # Файловый краулер
│   ├── chunkers/            # 🧩 Чанкеры (унифицированы)
│   │   └── unified_chunker.py # Единый чанкер
│   ├── run.py               # 🚀 Единый entrypoint
│   ├── indexer.py           # 📦 Простой индексер (совместимость)
│   └── config.yaml          # ⚙️ Конфигурация
├── tests/                   # 🧪 Тесты
│   ├── test_unified_*       # Тесты новой архитектуры (58 тестов)
│   ├── test_docusaurus_*    # Тесты Docusaurus (43 теста)
│   └── services/            # Тесты сервисов
├── backup/                  # 📦 Устаревшие файлы
│   ├── ingestion/           # Старые компоненты
│   ├── services/            # Устаревшие сервисы
│   ├── tests/               # Старые тесты
│   └── scripts/             # Устаревшие скрипты
└── docs/                    # 📚 Документация
│   │   ├── adaptive_chunker.py # Адаптивный чанкер
│   │   ├── semantic_chunker.py # Семантический чанкер
│   │   └── __init__.py     # Единый интерфейс экспорта
│   ├── processors/         # Обработчики контента
│   │   ├── content_processor.py # Диспетчер парсеров
│   │   ├── html_parser.py      # HTML парсер
│   │   ├── jina_parser.py      # Jina Reader парсер
│   │   └── markdown_parser.py  # Markdown парсер
│   ├── indexer.py          # Индексация в Qdrant
│   ├── pipeline.py         # Пайплайн индексации
│   └── universal_loader.py # Legacy универсальный загрузчик
├── sparse_service/          # Сервис sparse эмбеддингов
│   └── app.py              # FastAPI сервис
├── scripts/                # Утилиты
│   ├── init_qdrant.py      # Инициализация Qdrant
│   ├── indexer.py          # Единый модуль индексации
│   └── manage_cache.py     # Управление кешем
├── docs/                   # Документация
│   ├── refactoring_complete_report.md # 🆕 Полный отчет по рефакторингу
│   └── ...                 # Другие документы
├── tests/                  # Тесты
├── requirements.txt        # Python зависимости
├── env.example            # Пример конфигурации
├── wsgi.py                # WSGI entry point
└── README.md              # Основная документация
```

## Настройка среды разработки

### 1. Клонирование и настройка

```bash
# Клонирование репозитория
git clone <repository-url>
cd RAG_2

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Установка dev зависимостей
pip install pytest black flake8 mypy pre-commit
```

### 2. Единая архитектура индексации (v4.0.0)

**Новая архитектура упрощает разработку и поддержку:**

#### Основные принципы:
- **Единый DAG пайплайн** для всех источников данных
- **Source Adapters** для унификации интерфейсов
- **Pipeline Steps** для модульной обработки
- **Unified State Manager** для управления состоянием

#### Добавление нового источника данных:

1. **Создайте SourceAdapter:**
```python
# ingestion/adapters/my_source.py
from .base import SourceAdapter, RawDoc

class MySourceAdapter(SourceAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def iter_documents(self) -> Iterable[RawDoc]:
        # Логика получения документов
        for doc in self._fetch_documents():
            yield RawDoc(
                uri=f"mysource://{doc.id}",
                bytes=doc.content.encode('utf-8'),
                meta={"source": "mysource", "type": doc.type}
            )
```

2. **Создайте нормализаторы:**
```python
# ingestion/normalizers/my_source.py
from .base import PipelineStep, ParsedDoc

class MySourceNormalizer(PipelineStep):
    def process(self, doc: ParsedDoc) -> ParsedDoc:
        # Специфичная нормализация для вашего источника
        doc.text = self._clean_content(doc.text)
        return doc
```

3. **Обновите run.py:**
```python
# Добавьте в ingestion/run.py
def create_my_source_dag(config: Dict[str, Any]) -> PipelineDAG:
    return PipelineDAG([
        Parser(),
        MySourceNormalizer(),
        UnifiedChunkerStep(),
        Embedder(),
        QdrantWriter()
    ])
```

4. **Добавьте тесты:**
```python
# tests/test_my_source.py
def test_my_source_adapter():
    adapter = MySourceAdapter(config)
    docs = list(adapter.iter_documents())
    assert len(docs) > 0
```

### 3. Pre-commit hooks

```bash
# Установка pre-commit
pre-commit install

# Создание .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
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
        additional_dependencies: [types-requests, types-PyYAML]
EOF
```

### 3. IDE настройка

#### VS Code
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
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true
  }
}
```

## Архитектурные принципы

### 1. Разделение ответственности

Каждый модуль имеет четко определенную ответственность:

- **Adapters**: Взаимодействие с внешними каналами
- **Services**: Бизнес-логика и алгоритмы
- **Routes**: HTTP API endpoints
- **Ingestion**: Парсинг и индексация данных

### 2. Dependency Injection

```python
# Хорошо: внедрение зависимостей
class Orchestrator:
    def __init__(self, embedding_service, retrieval_service, llm_service):
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service

# Плохо: жестко закодированные зависимости
class Orchestrator:
    def __init__(self):
        self.embedding_service = EmbeddingService()  # Плохо
```

### 3. Error Handling

```python
# Хорошо: специфичные исключения
class EmbeddingError(Exception):
    pass

class LLMError(Exception):
    pass

def embed_text(text: str) -> list[float]:
    try:
        return model.encode(text)
    except Exception as e:
        raise EmbeddingError(f"Failed to embed text: {e}") from e
```

### 4. Logging

```python
# Хорошо: структурированное логирование
from loguru import logger

def process_query(query: str) -> dict:
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

## Добавление нового канала

### 1. Создание адаптера

Создайте файл `adapters/web_adapter.py`:

```python
from __future__ import annotations

import asyncio
import json
from typing import Any
from fastapi import FastAPI, WebSocket
from loguru import logger

class WebAdapter:
    def __init__(self, api_base: str = "http://localhost:9000"):
        self.api_base = api_base
        self.app = FastAPI()
        self.setup_routes()

    def setup_routes(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            logger.info("WebSocket connection established")

            try:
                while True:
                    data = await websocket.receive_text()
                    message_data = json.loads(data)

                    # Обработка сообщения
                    response = await self.process_message(message_data)
                    await websocket.send_text(json.dumps(response))

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.close()

    async def process_message(self, message_data: dict) -> dict[str, Any]:
        # Интеграция с Core API
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/v1/chat/query",
                json={
                    "channel": "web",
                    "chat_id": message_data.get("chat_id"),
                    "message": message_data.get("message")
                }
            )
            return response.json()

if __name__ == "__main__":
    adapter = WebAdapter()
    import uvicorn
    uvicorn.run(adapter.app, host="0.0.0.0", port=8001)
```

### 2. Обновление конфигурации

Добавьте в `app/config.py`:

```python
@dataclass
class AppConfig:
    # ... существующие поля ...

    # Web adapter
    web_adapter_host: str = "0.0.0.0"
    web_adapter_port: int = 8001
    web_adapter_enabled: bool = False
```

### 3. Добавление в docker-compose

```yaml
services:
  web-adapter:
    build: .
    command: python adapters/web_adapter.py
    ports:
      - "8001:8001"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - YANDEX_API_KEY=${YANDEX_API_KEY}
    depends_on:
      - rag-api
```

## Добавление нового LLM провайдера

### 1. Реализация провайдера

Добавьте в `app/services/llm_router.py`:

```python
def _claude_complete(prompt: str, max_tokens: int = 800) -> str:
    """Claude API integration."""
    if not CONFIG.claude_api_key:
        raise RuntimeError("Claude API key is not set")

    headers = {
        "x-api-key": CONFIG.claude_api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "model": CONFIG.claude_model or "claude-3-sonnet-20240229",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }

    resp = requests.post(CONFIG.claude_api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    try:
        return data["content"][0]["text"]
    except Exception:
        return str(data)

def generate_answer(query: str, context: list[dict], policy: dict[str, Any] | None = None) -> str:
    # ... существующий код ...

    order = [DEFAULT_LLM, "GPT5", "DEEPSEEK", "CLAUDE"]  # Добавили Claude
    for provider in order:
        try:
            if provider == "YANDEX":
                answer = _yandex_complete(prompt)
                return _format_for_telegram(answer)
            # ... другие провайдеры ...
            if provider == "CLAUDE":
                answer = _claude_complete(prompt)
                return _format_for_telegram(answer)
        except Exception:
            continue
```

### 2. Обновление конфигурации

```python
@dataclass
class AppConfig:
    # ... существующие поля ...

    # Claude
    claude_api_url: str = "https://api.anthropic.com/v1/messages"
    claude_api_key: str = ""
    claude_model: str = "claude-3-sonnet-20240229"
```

### 3. Обновление env.example

```env
# Claude
CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_API_KEY=your_claude_api_key
CLAUDE_MODEL=claude-3-sonnet-20240229
```

## Добавление нового парсера

### 1. Создание парсера

Добавьте в `ingestion/parsers.py`:

```python
def parse_api_specification(content: str) -> dict:
    """Парсер для OpenAPI/Swagger спецификаций."""
    soup = BeautifulSoup(content, "lxml")

    # Поиск OpenAPI спецификации
    script_tag = soup.find("script", {"type": "application/json"})
    if not script_tag:
        return {"endpoints": [], "schemas": []}

    try:
        spec = json.loads(script_tag.string)
        endpoints = []

        for path, methods in spec.get("paths", {}).items():
            for method, details in methods.items():
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": details.get("summary", ""),
                    "description": details.get("description", ""),
                    "parameters": details.get("parameters", []),
                    "responses": details.get("responses", {})
                })

        return {
            "endpoints": endpoints,
            "schemas": spec.get("components", {}).get("schemas", {}),
            "info": spec.get("info", {})
        }
    except json.JSONDecodeError:
        return {"endpoints": [], "schemas": []}
```

### 2. Интеграция в пайплайн

Обновите `ingestion/pipeline.py`:

```python
def classify_page(url: str) -> str:
    low = url.lower()
    if "faq" in low:
        return "faq"
    if "api" in low:
        return "api"
    if "openapi" in low or "swagger" in low:  # Новый тип
        return "api_spec"
    if "release" in low or "changelog" in low:
        return "release_notes"
    return "guide"

def crawl_and_index(incremental: bool = True) -> dict[str, Any]:
    # ... существующий код ...

    for p in all_pages:
        url = p["url"]
        html = p["html"]
        page_type = classify_page(url)

        # Специализированный парсинг
        if page_type == "api_spec":
            parsed = parse_api_specification(html)
            # Обработка спецификации...
        else:
            parsed = parse_guides(html)

        # ... остальной код ...
```

## Мониторинг и отладка

### 1. Запуск системы мониторинга

```bash
# Запуск Grafana + Prometheus для разработки
.\start_monitoring.ps1

# Доступ к интерфейсам
# Prometheus: http://localhost:9090
# Grafana: http://localhost:8080 (admin/admin123)
```

### 2. Отладка метрик

```python
# Проверка доступности метрик
import requests

# Проверка RAG API метрик
response = requests.get('http://localhost:9001/metrics')
print(f"RAG API метрики: {response.status_code}")

# Проверка Prometheus
response = requests.get('http://localhost:9090/api/v1/targets')
print(f"Prometheus targets: {response.status_code}")
```

### 3. Создание кастомных дашбордов

Создайте новый дашборд в `monitoring/grafana/dashboards/`:

```json
{
  "dashboard": {
    "title": "Custom RAG Dashboard",
    "panels": [
      {
        "title": "Custom Metric",
        "type": "graph",
        "targets": [
          {
            "expr": "rag_queries_total",
            "legendFormat": "Total Queries"
          }
        ]
      }
    ]
  }
}
```

### 4. Добавление новых метрик

```python
# app/metrics.py
from prometheus_client import Counter, Histogram

# Новая метрика
custom_counter = Counter(
    'rag_custom_metric_total',
    'Custom metric description',
    ['label1', 'label2']
)

# Использование
custom_counter.labels(label1='value1', label2='value2').inc()
```

## Тестирование

### 1. Unit тесты

Создайте `tests/test_services.py`:

```python
import pytest
from unittest.mock import Mock, patch
from app.services.core.embeddings import embed_dense, embed_sparse_optimized
from app.services.search.retrieval import hybrid_search
from app.services.core.llm_router import generate_answer

class TestEmbeddings:
    @patch('app.services.core.embeddings._get_bge_model')
    def test_embed_dense(self, mock_model):
        mock_model.return_value.encode.return_value = [0.1, 0.2, 0.3]

        result = embed_dense("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_model.return_value.encode.assert_called_once_with("test text")

    @patch('requests.post')
    def test_embed_sparse(self, mock_post):
        mock_post.return_value.json.return_value = {
            "sparse_vecs": {"1": 0.5, "2": 0.3}
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = embed_sparse_optimized("test text")

        assert result == {"indices": [1, 2], "values": [0.5, 0.3]}

class TestRetrieval:
    @patch('app.services.search.retrieval.client')
    def test_hybrid_search(self, mock_client):
        mock_client.search.return_value = [
            {"id": "1", "score": 0.9, "payload": {"text": "test"}}
        ]

        result = hybrid_search([0.1, 0.2], {"indices": [], "values": []})

        assert len(result) == 1
        assert result[0]["id"] == "1"

class TestLLMRouter:
    @patch('app.services.core.llm_router._yandex_complete')
    def test_generate_answer(self, mock_yandex):
        mock_yandex.return_value = "Test answer"

        context = [{"payload": {"url": "http://test.com", "title": "Test"}}]
        result = generate_answer("test query", context)

        assert "Test answer" in result
        mock_yandex.assert_called_once()
```

### 2. Integration тесты

Создайте `tests/test_integration.py`:

```python
import pytest
import requests
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_chat_endpoint(client):
    response = client.post('/v1/chat/query', json={
        'channel': 'test',
        'chat_id': '123',
        'message': 'test message'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert 'answer' in data
    assert 'sources' in data

def test_health_endpoint(client):
    response = client.get('/v1/admin/health')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
```

### 3. E2E тесты

Создайте `tests/test_e2e.py`:

```python
import pytest
import time
from adapters.telegram_polling import run_polling_loop
from app.services.infrastructure.orchestrator import handle_query

def test_full_pipeline():
    """Тест полного пайплайна обработки запроса."""
    query = "Как настроить маршрутизацию?"

    # Тест оркестратора
    result = handle_query("test", "123", query)

    assert "answer" in result
    assert "sources" in result
    assert len(result["sources"]) > 0
    assert result["channel"] == "test"
    assert result["chat_id"] == "123"
```

### 4. Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Конкретный тест
pytest tests/test_services.py::TestEmbeddings::test_embed_dense

# Параллельно
pytest -n auto
```

## Профилирование и оптимизация

### 1. Профилирование производительности

```python
import cProfile
import pstats
from app.services.infrastructure.orchestrator import handle_query

def profile_query_processing():
    profiler = cProfile.Profile()
    profiler.enable()

    # Ваш код
    result = handle_query("test", "123", "test query")

    profiler.disable()

    # Анализ результатов
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

if __name__ == "__main__":
    profile_query_processing()
```

### 2. Мониторинг памяти

```python
import tracemalloc
from app.services.infrastructure.orchestrator import handle_query

def monitor_memory():
    tracemalloc.start()

    # Ваш код
    result = handle_query("test", "123", "test query")

    # Анализ памяти
    current, peak = tracemalloc.get_traced_memory()
    print(f"Current memory usage: {current / 1024 / 1024:.2f} MB")
    print(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")

    # Топ-10 строк по памяти
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')

    for stat in top_stats[:10]:
        print(stat)

if __name__ == "__main__":
    monitor_memory()
```

### 3. Асинхронная оптимизация

```python
import asyncio
import aiohttp
from typing import List

async def async_embed_batch(texts: List[str]) -> List[List[float]]:
    """Асинхронная обработка батча текстов."""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for text in texts:
            task = async_embed_single(session, text)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results

async def async_embed_single(session: aiohttp.ClientSession, text: str) -> List[float]:
    """Асинхронное создание эмбеддинга для одного текста."""
    # Реализация асинхронного вызова
    pass
```

## Документирование кода

### 1. Docstrings

```python
def hybrid_search(
    dense_vector: list[float],
    sparse_vector: dict,
    k: int = 20,
    boosts: dict | None = None
) -> list[dict]:
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
    # Реализация...
```

### 2. Type Hints

```python
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass

@dataclass
class SearchResult:
    """Результат поиска документа."""
    id: str
    score: float
    payload: Dict[str, Any]
    vector: Optional[List[float]] = None

def process_query(
    query: str,
    context: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], None]:
    """
    Обрабатывает пользовательский запрос.

    Args:
        query: Текст запроса пользователя
        context: Контекстные документы
        options: Дополнительные опции обработки

    Returns:
        Результат обработки или None при ошибке
    """
    # Реализация...
```

## Code Review Guidelines

### 1. Checklist для ревьюера

- [ ] Код соответствует архитектурным принципам
- [ ] Есть тесты для новой функциональности
- [ ] Обновлена документация
- [ ] Нет хардкода и магических чисел
- [ ] Обработка ошибок реализована корректно
- [ ] Логирование добавлено где необходимо
- [ ] Производительность не деградировала
- [ ] Безопасность не нарушена

### 2. Примеры хорошего кода

```python
# Хорошо: читаемый и понятный код
def calculate_relevance_score(
    query_embedding: List[float],
    doc_embedding: List[float]
) -> float:
    """Вычисляет релевантность документа к запросу."""
    if len(query_embedding) != len(doc_embedding):
        raise ValueError("Embedding dimensions must match")

    # Косинусное сходство
    dot_product = sum(q * d for q, d in zip(query_embedding, doc_embedding))
    query_norm = sum(q * q for q in query_embedding) ** 0.5
    doc_norm = sum(d * d for d in doc_embedding) ** 0.5

    if query_norm == 0 or doc_norm == 0:
        return 0.0

    return dot_product / (query_norm * doc_norm)

# Плохо: нечитаемый код
def calc_rel(q, d):
    return sum(q[i]*d[i] for i in range(len(q)))/(sum(q[i]**2 for i in range(len(q)))**0.5*sum(d[i]**2 for i in range(len(d)))**0.5) if sum(q[i]**2 for i in range(len(q)))**0.5 != 0 and sum(d[i]**2 for i in range(len(d)))**0.5 != 0 else 0
```

## CI/CD Pipeline

### 1. GitHub Actions

Создайте `.github/workflows/ci.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

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
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest black flake8 mypy

    - name: Lint with flake8
      run: |
        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

    - name: Type check with mypy
      run: |
        mypy app/ --ignore-missing-imports

    - name: Format check with black
      run: |
        black --check .

    - name: Test with pytest
      run: |
        pytest tests/ --cov=app --cov-report=xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### 2. Pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
        args: [--line-length=88]

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-PyYAML]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

## Добавление новых источников данных

### 1. Обзор архитектуры

Система использует модульную архитектуру для работы с различными источниками данных:

- **SourcesRegistry** — централизованная конфигурация источников
- **CrawlerFactory** — фабрика для выбора подходящего краулера
- **BaseCrawler** — абстрактный базовый класс для всех краулеров
- **WebsiteCrawler** — для веб-сайтов
- **LocalFolderCrawler** — для локальных папок

### 2. Добавление нового источника

#### Шаг 1: Определите тип источника

```python
from app.sources_registry import SourceType

# Выберите подходящий тип
source_type = SourceType.DOCS_SITE  # или другой тип
```

#### Шаг 2: Создайте конфигурацию

```python
from app.sources_registry import SourceConfig

config = SourceConfig(
    name="my_new_source",
    base_url="https://example.com/",
    source_type=SourceType.DOCS_SITE,
    strategy="jina",  # или "http", "auto"
    use_cache=True,
    sitemap_path="/sitemap.xml",
    seed_urls=["https://example.com/"],
    crawl_deny_prefixes=["https://example.com/admin/"],
    metadata_patterns={
        r'/docs/': {'section': 'docs', 'user_role': 'all'},
    },
    timeout_s=30,
    crawl_delay_ms=1000,
)
```

#### Шаг 3: Зарегистрируйте источник

```python
from app.sources_registry import get_sources_registry

registry = get_sources_registry()
registry.register(config)
```

#### Шаг 4: Протестируйте источник

```python
from ingestion.crawlers import CrawlerFactory

# Создайте краулер
crawler = CrawlerFactory.create_crawler(config)

# Тестируйте получение URL
urls = crawler.get_available_urls()
print(f"Found {len(urls)} URLs")

# Тестируйте краулинг
results = crawler.crawl(max_pages=5)
for result in results:
    if result.error:
        print(f"❌ {result.url}: {result.error}")
    else:
        print(f"✅ {result.url}: {result.title}")
```

### 3. Создание кастомного краулера

Если стандартные краулеры не подходят:

```python
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult
from app.sources_registry import SourceConfig

class CustomCrawler(BaseCrawler):
    def get_available_urls(self) -> List[str]:
        # Ваша логика получения URL
        pass

    def crawl(self, max_pages: Optional[int] = None) -> List[CrawlResult]:
        # Ваша логика краулинга
        pass

# Зарегистрируйте краулер
from ingestion.crawlers import CrawlerFactory
from app.sources_registry import SourceType

CrawlerFactory.register_crawler(SourceType.CUSTOM, CustomCrawler)
```

### 4. Тестирование

Создайте тесты для вашего источника:

```python
# tests/test_my_source.py
import pytest
from app.sources_registry import get_source_config
from ingestion.crawlers import CrawlerFactory

def test_my_source():
    config = get_source_config("my_new_source")
    crawler = CrawlerFactory.create_crawler(config)

    # Тестируйте получение URL
    urls = crawler.get_available_urls()
    assert isinstance(urls, list)

    # Тестируйте краулинг
    results = crawler.crawl(max_pages=1)
    assert len(results) == 1
    assert not results[0].error
```

### 5. Документация

Добавьте документацию для вашего источника в `docs/adding_data_sources.md`.

## Отладка

### 1. Логирование

```python
import logging
from loguru import logger

# Настройка логирования
logger.add("logs/debug.log", level="DEBUG", rotation="1 day")
logger.add("logs/error.log", level="ERROR", rotation="1 week")

# Использование в коде
def process_query(query: str) -> dict:
    logger.debug(f"Processing query: {query[:100]}...")

    try:
        result = do_processing(query)
        logger.info(f"Query processed successfully in {result.time_taken:.2f}s")
        return result
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise
```

### 2. Debug режим

```python
# Включение debug режима
import os
os.environ["DEBUG"] = "true"

# Условное логирование
if os.getenv("DEBUG"):
    logger.debug("Debug information")
```

### 3. Профилирование

```python
import cProfile
import pstats
import io

def profile_function(func, *args, **kwargs):
    """Профилирует выполнение функции."""
    profiler = cProfile.Profile()
    profiler.enable()

    result = func(*args, **kwargs)

    profiler.disable()

    # Анализ результатов
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats()

    print(s.getvalue())
    return result
```

## Заключение

Это руководство должно помочь разработчикам эффективно работать с проектом. Помните:

1. **Следуйте архитектурным принципам**
2. **Пишите тесты для новой функциональности**
3. **Документируйте изменения**
4. **Используйте инструменты качества кода**
5. **Проводите code review**

Для вопросов и предложений создавайте issues в репозитории проекта.
