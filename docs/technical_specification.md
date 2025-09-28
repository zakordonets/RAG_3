# Техническая спецификация RAG-системы (Phase 2)

## Обзор системы

RAG-система для edna Chat Center представляет собой интеллектуального помощника с комплексной системой оценки качества (Phase 2), который использует комбинацию векторного поиска, генерации текста и RAGAS метрик для предоставления точных ответов на вопросы пользователей на основе документации продукта.

## 🆕 Phase 2.1: Автотесты и CI/CD

### Архитектурные компоненты тестирования

#### 1. Test Suite Architecture
- **Технология**: pytest 8.3.2 + pytest-asyncio
- **Структура**: Unit, Integration, End-to-End тесты
- **Маркировка**: @pytest.mark.slow, @pytest.mark.integration
- **Конфигурация**: pytest.ini с настройками asyncio

#### 2. End-to-End Pipeline Tests
- **Покрытие**: От извлечения документа до записи в Qdrant
- **Сценарии**: Извлечение, chunking, индексация, поиск
- **Валидация**: Enhanced metadata, конфигурация, плагины
- **Очистка**: Автоматическое удаление тестовых данных

#### 3. CI/CD Pipeline
- **Технология**: GitHub Actions
- **Поддержка**: Python 3.9, 3.10, 3.11
- **Сервисы**: Redis, Qdrant для тестов
- **Этапы**: Линтинг, тесты, покрытие, безопасность

#### 4. Development Tools
- **Makefile**: Удобные команды разработки
- **Линтинг**: flake8, black, isort, mypy
- **Покрытие**: pytest-cov с HTML отчетами
- **Форматирование**: Автоматическое форматирование кода

#### 5. Plugin System
- **Абстракции**: DataSource, Page, CrawlResult
- **Регистрация**: Автоматическая регистрация источников
- **Расширяемость**: Легкое добавление новых источников
- **Валидация**: Типизация и валидация конфигурации

### Примеры использования автотестов

#### Запуск тестов
```bash
# Быстрые тесты для разработки
make test-fast

# Полный набор тестов
make test

# Тесты с покрытием кода
make test-coverage

# Конкретный тип тестов
python scripts/run_tests.py --type unit --verbose
```

#### Добавление новых тестов
```python
# tests/test_new_feature.py
import pytest
from app.services.new_service import NewService

class TestNewFeature:
    def test_basic_functionality(self):
        """Тест базовой функциональности"""
        service = NewService()
        result = service.process("test")
        assert result == "expected"

    @pytest.mark.integration
    def test_integration(self):
        """Интеграционный тест"""
        # Тест интеграции с другими компонентами
        pass

    @pytest.mark.slow
    def test_performance(self):
        """Медленный тест производительности"""
        # Тест производительности
        pass
```

#### CI/CD конфигурация
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    services:
      redis:
        image: redis:7-alpine
      qdrant:
        image: qdrant/qdrant:latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest tests/ -v --cov=app
```

## 🆕 Phase 2: RAGAS Quality System

### Архитектурные компоненты качества

#### 1. RAGAS Evaluator
- **Технология**: RAGAS 0.1.21 + LangChain 0.2.16
- **Метрики**: Faithfulness, Context Precision, Answer Relevancy
- **LLM**: YandexGPT с детерминированными параметрами
- **Embeddings**: BGE-M3 unified embeddings
- **Таймауты**: 25 секунд с автоматическим fallback

#### 2. Quality Manager
- **Назначение**: Центральный менеджер оценки качества
- **Функции**: RAGAS оценка, сохранение данных, статистика
- **Интеграция**: Автоматическое создание взаимодействий

#### 3. Quality Database
- **Технология**: SQLAlchemy 2.0 + SQLite/PostgreSQL
- **Схема**: JSON сериализация для сложных структур
- **Индексы**: Оптимизация запросов по дате и ID

#### 4. Quality API
- **Endpoints**: /v1/admin/quality/*
- **Функции**: Статистика, тренды, корреляция, фидбек
- **Валидация**: Marshmallow схемы

#### 5. Telegram Feedback Integration
- **Технология**: Inline кнопки с callback обработкой
- **Функции**: Сбор пользовательских оценок (👍/👎)
- **Интеграция**: Автоматическое сохранение в Quality DB

## Архитектурные компоненты

### 1. Channel Adapters (Адаптеры каналов)

#### Telegram Adapter
- **Технология**: Long Polling API
- **Форматирование**: MarkdownV2 с fallback
- **Обработка ошибок**: Timeout handling, retry logic
- **Логирование**: Подробные логи для диагностики

```python
# Пример использования
from adapters.telegram_polling import run_polling_loop
run_polling_loop(api_base="http://localhost:9000")
```

#### Web Adapter (планируется)
- **Технология**: WebSocket + REST API
- **Аутентификация**: JWT токены
- **UI**: React/Vue.js интерфейс

### 2. Core API

#### Flask Application
- **Фреймворк**: Flask + Flask-RESTful
- **Порт**: 9000 (настраивается)
- **CORS**: Поддержка cross-origin запросов
- **Логирование**: Structured logging с loguru

#### Endpoints

##### Chat API
```http
POST /v1/chat/query
Content-Type: application/json

{
  "channel": "telegram",
  "chat_id": "123456789",
  "message": "Как настроить маршрутизацию?"
}
```

**Response:**
```json
{
  "answer": "Для настройки маршрутизации...",
  "sources": [
    {
      "title": "Настройка маршрутизации",
      "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/"
    }
  ],
  "channel": "telegram",
  "chat_id": "123456789"
}
```

##### Quality API (Phase 2)
```http
GET /v1/admin/quality/stats?days=7
GET /v1/admin/quality/interactions?limit=10
GET /v1/admin/quality/trends?days=30&metric=faithfulness
GET /v1/admin/quality/correlation?days=30
POST /v1/admin/quality/feedback
```

##### Admin API
```http
GET /v1/admin/health
POST /v1/admin/reindex
```

### 3. Query Processing

#### Entity Extraction
- **Цель**: Извлечение ключевых сущностей из запроса
- **Технология**: NER модели (планируется)
- **Применение**: Улучшение качества поиска

#### Query Rewriting
- **Цель**: Переформулирование запроса для лучшего поиска
- **Примеры**:
  - "Как настроить?" → "настройка конфигурация параметры"
  - "Проблема с API" → "API ошибка проблема решение"

#### Query Decomposition
- **Цель**: Разбиение сложных запросов на простые
- **Пример**: "Как настроить маршрутизацию и сегментацию?" → два отдельных запроса

### 4. Embeddings

#### Dense Embeddings
- **Модель**: BAAI/bge-m3 (1024 dim)
- **Технология**: SentenceTransformers
- **Использование**: Семантический поиск
- **Производительность**: ~5-10 сек на запрос

```python
def embed_dense(text: str) -> list[float]:
    model = SentenceTransformer("BAAI/bge-m3")
    return model.encode(text).tolist()
```

#### Sparse Embeddings
- **Модель**: BGE-M3 sparse
- **Технология**: FlagEmbedding
- **Использование**: Keyword matching
- **Формат**: {indices: [...], values: [...]}

```python
def embed_sparse(text: str) -> dict:
    # Возвращает sparse представление для Qdrant
    return {"indices": [...], "values": [...]}
```

### 5. Vector Search

#### Qdrant Configuration
- **Версия**: 1.7+
- **Коллекция**: edna_docs
- **Индексы**: HNSW для dense, SparseVector для sparse
- **Параметры**:
  - `m`: 16 (количество связей)
  - `ef_construct`: 100
  - `ef_search`: 50

#### Hybrid Search
- **Алгоритм**: RRF (Reciprocal Rank Fusion)
- **Веса**: Dense=0.7, Sparse=0.3
- **K**: 60 (для RRF)
- **Результаты**: Top-20 кандидатов

```python
def hybrid_search(dense_vec, sparse_vec, k=20):
    # Dense search
    dense_results = client.search(
        collection_name="edna_docs",
        query_vector=dense_vec,
        limit=k
    )

    # Sparse search
    sparse_results = client.search(
        collection_name="edna_docs",
        query_sparse=sparse_vec,
        limit=k
    )

    # RRF fusion
    return rrf_fusion(dense_results, sparse_results)
```

### 6. Reranking

#### BGE-reranker-v2-m3
- **Модель**: BAAI/bge-reranker-v2-m3
- **Устройство**: CPU (настраивается)
- **Вход**: Query + Top-20 документов
- **Выход**: Переранжированный список Top-10

```python
def rerank(query: str, candidates: list, top_n=10):
    reranker = BGEM3FlagReranker("BAAI/bge-reranker-v2-m3")
    scores = reranker.compute_score([(query, doc) for doc in candidates])
    return sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)[:top_n]
```

### 7. LLM Router

#### Провайдеры
1. **YandexGPT** (по умолчанию)
2. **GPT-5** (fallback)
3. **Deepseek** (fallback)

#### Fallback Logic
```python
def generate_answer(query, context, policy=None):
    order = ["YANDEX", "GPT5", "DEEPSEEK"]
    for provider in order:
        try:
            return call_llm(provider, query, context)
        except Exception:
            continue
    return "LLM недоступны"
```

#### Prompt Engineering
```python
prompt = f"""
Вы — ассистент по edna Chat Center. Используйте только предоставленный контекст.
Отвечайте структурировано с заголовками, списками и ссылками.
Используйте markdown форматирование: **жирный текст**, ### заголовки, * списки.
В конце добавьте ссылку 'Подробнее' на основную страницу документации.

Вопрос: {query}

Контекст:
{sources_block}
"""
```

## Data Pipeline

### 1. Crawling

#### Стратегии
- **Jina Reader**: Обход антибота, извлечение контента
- **Browser**: Playwright для сложных страниц
- **HTTP**: Прямые запросы для простых страниц

#### Конфигурация
```python
CRAWL_STRATEGY = "jina"  # jina, browser, http
CRAWL_TIMEOUT_S = 30
CRAWL_MAX_PAGES = 1000
CRAWL_DELAY_MS = 1000
CRAWL_JITTER_MS = 500
```

#### Обработка URL
- Нормализация API ссылок (`/docs/api` → `/docs/api/index`)
- Фильтрация по префиксам
- Обработка sitemap.xml

### 2. Parsing

#### Docusaurus Parser
```python
def extract_main_text(soup):
    # Основной контент
    main_content = soup.select_one(".theme-doc-markdown")
    # Боковое меню
    sidebar = soup.select_one(".theme-doc-sidebar-menu")
    # Пагинация
    pagination = soup.select_one(".pagination-nav")
```

#### Специализированные парсеры
- **API Documentation**: Извлечение endpoints, параметров
- **Release Notes**: Версии, фичи, багфиксы
- **FAQ**: Вопросы и ответы

### 3. Chunking

#### Стратегия
- **Минимальный размер**: 50 токенов
- **Максимальный размер**: 500 токенов
- **Перекрытие**: 50 токенов между чанками
- **Дедупликация**: По хешу содержимого

```python
def chunk_text(text: str) -> list[str]:
    chunks = []
    sentences = split_into_sentences(text)
    current_chunk = []

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > MAX_TOKENS:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
        else:
            current_chunk.append(sentence)

    return chunks
```

### 4. Indexing

#### Metadata Schema
```python
payload = {
    "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/",
    "page_type": "guide",  # guide, api, faq, release_notes
    "source": "docs-site",
    "language": "ru",
    "title": "Настройка маршрутизации",
    "text": "Содержимое чанка",
    "chunk_id": "unique_id",
    "created_at": "2025-01-01T00:00:00Z"
}
```

#### Batch Processing
```python
def upsert_chunks(chunks: list[dict]) -> int:
    # Batch размер: 100 чанков
    # Upsert с проверкой существования
    # Возврат количества обработанных чанков
```

## Performance Characteristics

### Время обработки (целевые значения)
- **Query Processing**: <1 сек
- **Dense Embedding**: 5-10 сек
- **Sparse Embedding**: 3-5 сек
- **Vector Search**: 1-2 сек
- **Reranking**: 20-30 сек
- **LLM Generation**: 30-60 сек
- **Total**: 60-120 сек

### Масштабируемость
- **Concurrent Users**: 100+ (с горизонтальным масштабированием)
- **Documents**: 10,000+ страниц
- **Chunks**: 100,000+ чанков
- **QPS**: 10+ запросов в секунду

### Ресурсы
- **RAM**: 8GB+ (рекомендуется 16GB)
- **CPU**: 4+ cores
- **Storage**: 2GB+ для эмбеддингов
- **Network**: Стабильное соединение с API

## Security

### API Security
- **Rate Limiting**: Защита от DDoS
- **Input Validation**: Проверка входных данных
- **Error Handling**: Безопасные сообщения об ошибках

### Data Security
- **API Keys**: Хранение в переменных окружения
- **HTTPS**: Обязательно для production
- **Access Control**: Ограничение доступа к admin endpoints

### Privacy
- **Logging**: Без персональных данных
- **Data Retention**: Настраиваемые политики
- **GDPR Compliance**: Готовность к требованиям

## Monitoring & Observability

### Логирование
```python
# Структурированные логи
logger.info(f"Processing query: {query[:100]}...")
logger.info(f"Query processed in {time_taken:.2f}s")
logger.error(f"Failed to process: {error}")
```

### Метрики
- **Response Time**: Время обработки запросов
- **Success Rate**: Процент успешных запросов
- **LLM Usage**: Использование провайдеров
- **Search Quality**: Precision@10, Recall@10

### Health Checks
```python
def health_check():
    return {
        "status": "ok",
        "qdrant": check_qdrant(),
        "llm": check_llm_providers(),
        "embeddings": check_embedding_service()
    }
```

## Deployment

### Development
```bash
# Локальная разработка
python wsgi.py
python adapters/telegram_polling.py
```

### Production
```bash
# Docker Compose
docker-compose up -d

# Kubernetes
kubectl apply -f k8s/
```

### CI/CD
- **Testing**: pytest + coverage
- **Linting**: flake8 + black
- **Security**: bandit + safety
- **Deployment**: GitHub Actions

## Troubleshooting

### Common Issues

#### High Response Time
- Проверьте доступность LLM API
- Увеличьте timeout настройки
- Оптимизируйте размер чанков

#### Poor Search Quality
- Переиндексируйте документацию
- Настройте веса hybrid search
- Проверьте качество парсинга

#### Memory Issues
- Уменьшите batch размеры
- Используйте streaming для больших данных
- Настройте garbage collection

### Debug Tools
```python
# Включение debug режима
DEBUG = True
LOG_LEVEL = "DEBUG"

# Профилирование
import cProfile
cProfile.run('process_query("test")')
```

## Future Enhancements

### Short Term
- [ ] Web интерфейс
- [ ] A/B тестирование ответов
- [ ] Кэширование частых запросов
- [ ] Batch обработка запросов

### Medium Term
- [ ] Многоязычность
- [ ] Voice интерфейс
- [ ] Аналитика использования
- [ ] Персонализация ответов

### Long Term
- [ ] Fine-tuning моделей
- [ ] Real-time обучение
- [ ] Multi-modal поиск
- [ ] Автоматическое обновление знаний
