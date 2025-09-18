## План реализации RAG-ассистента edna Chat Center

### Этап 0. Инициализация репозитория и окружения
- Создать структуру проекта (Flask app factory, blueprints, services, ingestion, adapters, config, tests, docs).
- Подготовить `.env` с параметрами Qdrant, Ollama, Deepseek, Yandex.
- Базовая зависимость: Flask, Flask-RESTful, Flask-Cors, pydantic, httpx/requests, qdrant-client, rapidfuzz/simhash, beautifulsoup4, lxml, tenacity, python-dotenv, uvicorn/gunicorn, FlagEmbedding, sentencepiece, numpy, tqdm, loguru, prometheus-client.

### Этап 1. Каналы и API
1) Blueprint `adapters.telegram`:
   - `POST /v1/chat/telegram/webhook`: валидация апдейта, извлечение `chat_id`, `text`, проксирование в `/v1/chat/query`.
   - Отправка ответа пользователю через Telegram Bot API.
2) Универсальный эндпоинт `POST /v1/chat/query` (blueprint `routes.chat`):
   - Вход: `{channel, chat_id, message, session_id?}`.
   - Вызов сервиса оркестрации `services/orchestrator.handle_query`.

### Этап 2. Query Processing
- `services/query_processing.py`:
  - `extract_entities(text)`: доменные сущности (АРМ агента, API, администратор и пр.).
  - `rewrite_query(text)`: нормализация и расширение аббревиатур (синонимы, лемматизация при необходимости).
  - `maybe_decompose(text)`: правило для декомпозиции (по коннекторам «и», «как … если …» и т.п.) с max_depth=3.
  - Возврат: `{normalized_text, entities, boosts, subqueries?}`.

### Этап 3. Embeddings
- `services/embeddings.py`:
  - `embed_dense(text)` → Ollama BGE-M3.
  - `embed_sparse(text)` → локальная инференс-функция BGE-M3 sparse (FlagEmbedding) с возвратом `{term: weight}`.
  - Батч-режим для списков текстов.

### Этап 4. Retrieval (Qdrant)
- `services/retrieval.py`:
  - `hybrid_search(dense, sparse, k, boosts)`: параллельные запросы dense/sparse, RRF, metadata-boost, top-N.
  - Конфигурируемые веса: старт 0.5/0.5, затем A/B-тест.
  - Возврат кандидатов с payload и скором.

### Этап 5. Reranking
- `services/rerank.py`:
  - BGE-reranker-v2-m3 по top-N (например, 30 → 10).
  - Учитывать вопросительные формы для бонуса FAQ в финальном скоре.

### Этап 6. Generation (LLM Router)
- `services/llm_router.py`:
  - Провайдеры: GPT-5, YandexGPT 5.1 Pro, Deepseek.
  - Роутинг: основной — GPT-5; если недоступен — Yandex; если недоступен — Deepseek.
  - Промпт-шаблоны: стиль, запрет галлюцинаций, цитирование источников.
  - Итеративный режим: при недостаточном покрытии контекста — дополнительный retrieve (до глубины 3).

### Этап 7. Ingestion: краулер и парсеры
- `ingestion/crawler.py`: обходит `https://docs-chatcenter.edna.ru/` (site map/robots, белый список доменов), хранит сырые HTML и метаданные `url`, `last_modified`.
- `ingestion/parsers.py`: специализированные парсеры:
  - `parse_api_documentation(html)` → endpoints/parameters/examples/responses.
  - `parse_release_notes(html)` → version/features/fixes/breaking_changes.
  - `parse_faq_content(html)` → список Q/A.
  - `parse_guides(html)` → заголовки, параграфы, списки, таблицы, ссылки, изображения.
- `ingestion/chunker.py`: чанкинг с Quality Gates (min/max токенов, no-empty, dedup по хэшу/SimHash, сохранение иерархии заголовков и таблиц).
- `ingestion/indexer.py`: вычисление dense+sparse эмбеддингов, upsert в Qdrant, инкрементальность по `hash/updated_at` (удаление устаревших).

### Этап 8. Схема Qdrant и инициализация
- `scripts/init_qdrant.py`: создание коллекции `chatcenter_docs` с HNSW-параметрами из ENV, проверка индексов.

### Этап 9. Observability & Evaluation
- Логирование (loguru) пайплайна: запрос, сущности, переформулировка, кандидаты, веса, метрики.
- `metrics/collector.py`: расчёт Context Relevance/Coverage, Precision@K/Recall@K; Answer Relevancy, Faithfulness, Completeness.
- `routes/admin.py`: `POST /v1/admin/reindex`, `GET /v1/admin/metrics`.
- Простейший экспортер Prometheus.

### Этап 10. Тесты
- Unit-тесты: парсеры, чанкер, embeddings, hybrid_search, rerank, llm_router (с моками), orchestrator.
- Интеграционные: end-to-end запрос → ответ, smoke для инкрементальной индексации.

### Этап 11. Деплой и запуск
- Конфиги `.env`, Dockerfile (опционально), systemd/pm2 для API, отдельный процесс для краулера/индексера.
- Настройка Telegram webhook.

### Риск-реестр и смягчение
- Доступность провайдеров LLM → реализован fallback.
- Производительность sparse-экстракции → батчинг и кэширование (позже).
- Изменения структуры портала → устойчивый парсинг, тесты на выборке страниц.
- Drift релевантности → offline A/B на golden set и переобучение reranker в будущем.

### Артефакты
- `docs/architecture.md` — архитектура (готово).
- `docs/implementation_plan.md` — этот план.
- `scripts/init_qdrant.py` — инициализация коллекции.
- `ingestion/*` — краулер, парсеры, чанкер, индексер.
- `services/*` — embeddings, retrieval, rerank, llm_router, orchestrator, query_processing.
- `routes/*` и `adapters/*` — API и адаптеры каналов.



