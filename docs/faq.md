# Часто задаваемые вопросы (FAQ)

## Общие вопросы

### Что такое RAG-система?

RAG (Retrieval-Augmented Generation) — это архитектура, которая сочетает поиск по векторной базе данных с генерацией текста с помощью больших языковых моделей. Система сначала находит релевантные документы по запросу пользователя, а затем использует их как контекст для генерации точного ответа.

### Какие преимущества дает RAG по сравнению с обычными чат-ботами?

- **Точность**: Ответы основаны на актуальной документации
- **Актуальность**: Легко обновлять знания без переобучения модели
- **Прозрачность**: Пользователь видит источники информации
- **Контроль**: Можно точно контролировать, какую информацию использует система

### Как часто нужно обновлять данные?

Рекомендуется обновлять данные:
- **Еженедельно** — для стабильных проектов
- **Ежедневно** — для активно развивающихся продуктов
- **По требованию** — при значительных изменениях в документации

## Технические вопросы

### Почему система отвечает медленно?

Время ответа зависит от нескольких факторов:

1. **Эмбеддинги** (5-10 сек): Создание векторных представлений
2. **Поиск** (1-2 сек): Поиск в векторной базе данных
3. **Реренкинг** (20-30 сек): Переранжирование результатов
4. **LLM генерация** (30-60 сек): Создание ответа

**Оптимизация:**
- Используйте кэширование для частых запросов
- Настройте асинхронную обработку
- Рассмотрите использование более быстрых моделей

### Как увеличить качество поиска?

1. **Улучшите парсинг**:
   - Добавьте специализированные парсеры для разных типов контента
   - Улучшите извлечение метаданных

2. **Настройте чанкинг**:
   - Оптимизируйте размер чанков (50-500 токенов)
   - Добавьте перекрытие между чанками

3. **Настройте веса поиска**:
   - Экспериментируйте с `HYBRID_DENSE_WEIGHT` и `HYBRID_SPARSE_WEIGHT`
   - Добавьте бусты для важных метаданных

### Почему система не находит нужную информацию?

Возможные причины:

1. **Документ не проиндексирован**:
   - Проверьте, что URL есть в индексе
   - Запустите переиндексацию

2. **Плохое качество парсинга**:
   - Проверьте, что контент извлекается корректно
   - Добавьте специальные селекторы для вашего сайта

3. **Неподходящий запрос**:
   - Попробуйте переформулировать вопрос
   - Используйте ключевые слова из документации

4. **Проблемы с эмбеддингами**:
   - Проверьте, что модель загружена корректно
   - Убедитесь в стабильности подключения к API

### Как добавить поддержку других языков?

1. **Обновите парсеры**:
   ```python
   def extract_main_text(soup):
       # Добавьте поддержку языковых селекторов
       if soup.find('html', {'lang': 'en'}):
           # Английская версия
           pass
       elif soup.find('html', {'lang': 'ru'}):
           # Русская версия
           pass
   ```

2. **Настройте метаданные**:
   ```python
   payload = {
       "url": url,
       "language": detect_language(text),  # Автоопределение языка
       "text": text,
       # ...
   }
   ```

3. **Используйте мультиязычные модели**:
   - BGE-M3 поддерживает множество языков
   - Настройте промпты для разных языков

### Как масштабировать систему?

**Горизонтальное масштабирование:**

1. **API серверы**:
   ```yaml
   # docker-compose.yml
   services:
     rag-api:
       deploy:
         replicas: 3
   ```

2. **Load balancer**:
   ```nginx
   upstream rag_api {
       server rag-api-1:9000;
       server rag-api-2:9000;
       server rag-api-3:9000;
   }
   ```

3. **Qdrant кластер**:
   - Настройте репликацию
   - Используйте шардирование

**Вертикальное масштабирование:**
- Увеличьте RAM для кэширования
- Используйте GPU для эмбеддингов
- Оптимизируйте размеры батчей

## Проблемы и решения

### Ошибка "ModuleNotFoundError: No module named 'app'"

**Причина**: Python не может найти модуль `app`.

**Решение**:
```bash
# Установите PYTHONPATH
export PYTHONPATH=/path/to/your/project:$PYTHONPATH

# Или запустите из корневой директории
cd /path/to/your/project
python adapters/telegram_polling.py
```

### Ошибка "Qdrant connection failed"

**Причина**: Qdrant недоступен или неправильно настроен.

**Решение**:
1. Проверьте, что Qdrant запущен:
   ```bash
   docker ps | grep qdrant
   ```

2. Проверьте подключение:
   ```bash
   curl http://localhost:6333/collections
   ```

3. Проверьте настройки в `.env`:
   ```env
   QDRANT_URL=http://localhost:6333
   QDRANT_API_KEY=your_key
   ```

### Ошибка "LLM providers unavailable"

**Причина**: Все LLM провайдеры недоступны.

**Решение**:
1. Проверьте API ключи:
   ```bash
   # Проверка YandexGPT
   curl -H "Authorization: Api-Key $YANDEX_API_KEY" \
        "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
   ```

2. Проверьте квоты и лимиты API

3. Добавьте fallback провайдеры

### Ошибка "Telegram formatting error"

**Причина**: В HTML остаются неподдерживаемые теги или превышена длина сообщения.

**Решение**:
1. Проверьте Markdown ответа — адаптер конвертирует его в HTML, поэтому некорректные конструкции попадут в лог.
2. Ознакомьтесь с логами `TelegramAdapter`: там выводятся длины сообщений, количество частей и первые 300 символов HTML.
3. При необходимости сократите ответ или обновите allow-list тегов через `TELEGRAM_HTML_ALLOWLIST`.

### Медленная индексация

**Причина**: Большое количество документов или медленный парсинг.

**Решение**:
1. Увеличьте параллелизм:
   ```env
   CRAWL_CONCURRENCY=16
   ```

2. Используйте более быструю стратегию:
   ```env
   CRAWL_STRATEGY=jina  # Вместо browser
   ```

3. Ограничьте количество страниц:
   ```env
   CRAWL_MAX_PAGES=500
   ```

4. Используйте инкрементальную индексацию

## Настройка и конфигурация

### Как настроить разные модели эмбеддингов?

1. **Dense эмбеддинги**:
   ```env
   EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
   EMBEDDING_DIM=384
   ```

2. **Sparse эмбеддинги**:
   ```env
   SPARSE_SERVICE_URL=http://localhost:8001
   ```

3. **Реренкинг**:
   ```env
   RERANKER_MODEL=BAAI/bge-reranker-base
   RERANKER_DEVICE=cuda  # Если есть GPU
   ```

### Как настроить разные LLM провайдеры?

1. **YandexGPT** (по умолчанию):
   ```env
   YANDEX_API_KEY=your_key
   YANDEX_CATALOG_ID=your_catalog
   DEFAULT_LLM=yandex
   ```

2. **OpenAI GPT**:
   ```env
   GPT5_API_URL=https://api.openai.com/v1/chat/completions
   GPT5_API_KEY=your_key
   GPT5_MODEL=gpt-4
   ```

3. **Deepseek**:
   ```env
   DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
   DEEPSEEK_API_KEY=your_key
   DEEPSEEK_MODEL=deepseek-chat
   ```

### Как настроить мониторинг?

1. **Prometheus метрики**:
   ```python
   from prometheus_client import Counter, Histogram, start_http_server

   request_count = Counter('requests_total', 'Total requests')
   request_duration = Histogram('request_duration_seconds', 'Request duration')

   @request_duration.time()
   def handle_query(query):
       request_count.inc()
       # ... обработка запроса
   ```

2. **Логирование**:
   ```python
   from loguru import logger

   logger.add("logs/app.log", rotation="1 day", retention="30 days")
   logger.add("logs/error.log", level="ERROR", rotation="1 week")
   ```

3. **Health checks**:
   ```python
   def health_check():
       return {
           "status": "ok",
           "qdrant": check_qdrant(),
           "llm": check_llm_providers(),
           "memory": get_memory_usage()
       }
   ```

## Безопасность

### Как защитить API от злоупотреблений?

1. **Rate limiting**:
   ```python
   from flask_limiter import Limiter

   limiter = Limiter(
       app,
       key_func=lambda: request.remote_addr,
       default_limits=["100 per hour"]
   )

   @app.route('/v1/chat/query')
   @limiter.limit("10 per minute")
   def chat_query():
       # ...
   ```

2. **Аутентификация**:
   ```python
   from functools import wraps
   import jwt

   def require_auth(f):
       @wraps(f)
       def decorated(*args, **kwargs):
           token = request.headers.get('Authorization')
           if not token:
               return {'error': 'Token required'}, 401
           try:
               data = jwt.decode(token, app.config['SECRET_KEY'])
               current_user = data['user_id']
           except:
               return {'error': 'Invalid token'}, 401
           return f(current_user, *args, **kwargs)
       return decorated
   ```

3. **Валидация входных данных**:
   ```python
   from marshmallow import Schema, fields, validate

   class ChatRequestSchema(Schema):
       message = fields.Str(required=True, validate=validate.Length(max=1000))
       chat_id = fields.Str(required=True, validate=validate.Length(max=100))
       channel = fields.Str(required=True, validate=validate.OneOf(['telegram', 'web']))
   ```

### Как защитить API ключи?

1. **Переменные окружения**:
   ```bash
   # Никогда не коммитьте .env файл
   echo ".env" >> .gitignore
   ```

2. **Docker secrets**:
   ```yaml
   services:
     rag-api:
       secrets:
         - yandex_api_key
         - telegram_bot_token

   secrets:
     yandex_api_key:
       external: true
     telegram_bot_token:
       external: true
   ```

3. **Kubernetes secrets**:
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: rag-secrets
   type: Opaque
   data:
     YANDEX_API_KEY: <base64-encoded>
   ```

## Производительность

### Как оптимизировать время ответа?

1. **Кэширование**:
   ```python
   from functools import lru_cache
   import redis

   redis_client = redis.Redis(host='localhost', port=6379, db=0)

   @lru_cache(maxsize=1000)
   def get_embedding(text):
       # Кэширование эмбеддингов
       pass

   def cache_query_result(query, result):
       redis_client.setex(f"query:{hash(query)}", 3600, json.dumps(result))
   ```

2. **Асинхронная обработка**:
   ```python
   import asyncio
   import aiohttp

   async def process_queries_async(queries):
       async with aiohttp.ClientSession() as session:
           tasks = [process_single_query(session, q) for q in queries]
           return await asyncio.gather(*tasks)
   ```

3. **Batch обработка**:
   ```python
   def embed_batch(texts):
       # Обработка нескольких текстов за раз
       return model.encode(texts)
   ```

### Как уменьшить использование памяти?

1. **Lazy loading**:
   ```python
   class LazyModel:
       def __init__(self):
           self._model = None

       @property
       def model(self):
           if self._model is None:
               self._model = load_model()
           return self._model
   ```

2. **Очистка памяти**:
   ```python
   import gc

   def process_large_batch(data):
       results = []
       for chunk in chunks(data, 100):
           result = process_chunk(chunk)
           results.append(result)
           del chunk
           gc.collect()
       return results
   ```

3. **Оптимизация размеров**:
   ```python
   # Используйте более компактные модели
   EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dim
   # Вместо
   # EMBEDDING_MODEL_NAME = "BAAI/bge-m3"  # 1024 dim
   ```

## Поддержка и сообщество

### Где получить помощь?

1. **Документация**: [docs/](docs/)
2. **GitHub Issues**: [Создать issue](https://github.com/your-repo/issues)
3. **Email**: support@example.com
4. **Telegram**: @your_support_bot

### Как внести вклад в проект?

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

### Как сообщить об ошибке?

При создании issue укажите:
- Версию системы
- Шаги для воспроизведения
- Ожидаемое поведение
- Фактическое поведение
- Логи и скриншоты

### Как предложить новую функцию?

1. Создайте issue с тегом "enhancement"
2. Опишите проблему, которую решает функция
3. Предложите решение
4. Обсудите с сообществом
5. Реализуйте и создайте PR
