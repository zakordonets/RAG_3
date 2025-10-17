# 🚀 Quickstart Guide - RAG-система для edna Chat Center

Этот гайд поможет вам быстро развернуть и начать использовать RAG-систему для edna Chat Center.

## Предварительные требования

### Системные требования
- **OS**: Linux, macOS, Windows (с WSL2)
- **Python**: 3.9, 3.10 или 3.11
- **RAM**: Минимум 8 GB, рекомендуется 16+ GB
- **GPU**: Опционально (NVIDIA с DirectML для ускорения)
- **Disk**: 10+ GB свободного места

### Необходимое ПО
- Docker и Docker Compose (для запуска Qdrant и Redis)
- Git
- Python с pip

## Шаг 1: Клонирование репозитория

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/rag-system.git
cd rag-system

# Создать виртуальное окружение
python -m venv venv

# Активировать виртуальное окружение
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

## Шаг 2: Установка зависимостей

```bash
# Установить основные зависимости
pip install -r requirements.txt

# Для разработки (опционально)
pip install -r requirements-dev.txt
```

## Шаг 3: Настройка конфигурации

### Создание .env файла

```bash
# Скопировать пример конфигурации
cp env.example .env
```

### Минимальная конфигурация

Откройте `.env` и настройте следующие параметры:

```bash
# === QDRANT ===
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=chatcenter_docs

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN=your_bot_token_here  # Получите у @BotFather

# === LLM (выберите один) ===
# YandexGPT (рекомендуется)
YANDEX_API_KEY=your_yandex_api_key
YANDEX_CATALOG_ID=your_catalog_id

# Или GPT-5
# GPT5_API_KEY=your_gpt5_key

# Или Deepseek
# DEEPSEEK_API_KEY=your_deepseek_key

# === EMBEDDINGS ===
EMBEDDINGS_BACKEND=auto  # Автоматический выбор стратегии
USE_SPARSE=true

# === CHUNKING ===
CHUNK_MIN_TOKENS=150
CHUNK_MAX_TOKENS=300
CHUNK_OVERLAP_BASE=100

# === REDIS ===
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
```

## Шаг 4: Запуск инфраструктуры

### Запуск Qdrant и Redis через Docker Compose

```bash
# Запустить Qdrant и Redis
docker-compose up -d qdrant redis

# Проверить статус
docker-compose ps
```

**Ожидаемый вывод:**
```
NAME                IMAGE                    STATUS
rag-qdrant          qdrant/qdrant:latest     Up
rag-redis           redis:7-alpine           Up
```

### Проверка доступности

```bash
# Проверить Qdrant
curl http://localhost:6333/collections

# Проверить Redis
docker exec rag-redis redis-cli ping
# Ожидается: PONG
```

## Шаг 5: Инициализация Qdrant коллекции

```bash
# Создать коллекцию с правильной схемой
python scripts/init_qdrant.py

# Или через API
curl -X POST http://localhost:5001/v1/admin/init
```

## Шаг 6: Индексация документации

### Вариант 1: Индексация Docusaurus документации

```bash
# Полная индексация из локальной папки
python ingestion/run.py docusaurus \
    --docs-root /path/to/your/docs \
    --reindex-mode full \
    --clear-collection

# Пример для edna Chat Center docs
python ingestion/run.py docusaurus \
    --docs-root C:\CC_RAG\docs \
    --reindex-mode full \
    --clear-collection
```

### Вариант 2: Индексация веб-сайта

```bash
# Индексация с веб-сайта
python ingestion/run.py website \
    --seed-urls "https://docs-chatcenter.edna.ru/" \
    --max-depth 3 \
    --reindex-mode full
```

### Прогресс индексации

Вы увидите примерно такой вывод:

```
📊 Подготовка документов...
📄 Найдено 156 документов для обработки
📄 Обработано 10/156 документов (6.4%)
📄 Обработано 20/156 документов (12.8%)
...
📄 Обработано 156/156 документов (100.0%)

📊 Финальная статистика:
  📄 Документов обработано: 156/156
  ❌ Ошибок документов: 0
  📦 Всего чанков: 489
  ✅ Чанков обработано: 489
  ⏱️  Время выполнения: 245.32s
```

## Шаг 7: Запуск Flask API

```bash
# Запустить Flask приложение
python wsgi.py
```

**Ожидаемый вывод:**
```
 * Serving Flask app 'app'
 * Debug mode: off
 * Running on http://0.0.0.0:9000 (Press CTRL+C to quit)
```

### Проверка работоспособности

```bash
# Проверить health check
curl http://localhost:9000/v1/admin/health

# Ожидается:
{
  "status": "ok",
  "components": {
    "qdrant": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "embeddings": {"status": "healthy"}
  }
}
```

## Шаг 8: Запуск Telegram бота

### В отдельном терминале

```bash
# Активировать виртуальное окружение
source venv/bin/activate  # Linux/macOS
# или venv\Scripts\activate  # Windows

# Запустить Telegram polling
python adapters/telegram/polling.py
```

**Ожидаемый вывод:**
```
🤖 Telegram bot started (long polling)
📡 Polling for updates every 1 seconds...
```

### Альтернатива: Через скрипт

```bash
# Windows
start_telegram_bot.bat

# Linux/macOS с PowerShell
pwsh start_telegram_bot.ps1
```

## Шаг 9: Первый запрос

### Через Telegram

1. Найдите вашего бота в Telegram по имени
2. Нажмите `/start`
3. Отправьте вопрос, например: "Как настроить маршрутизацию?"

### Через API

```bash
# Отправить запрос через API
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web",
    "chat_id": "test_user",
    "message": "Как настроить маршрутизацию?"
  }'
```

**Ожидаемый ответ:**
```json
{
  "answer": "Для настройки маршрутизации в edna Chat Center...",
  "sources": [
    {
      "title": "Настройка маршрутизации",
      "url": "https://docs-chatcenter.edna.ru/docs/admin/routing/"
    }
  ],
  "channel": "web",
  "chat_id": "test_user"
}
```

## Шаг 10: Мониторинг (опционально)

### Запуск Prometheus и Grafana

```bash
# Запустить полный стек мониторинга
docker-compose up -d

# Или только мониторинг
docker-compose up -d prometheus grafana
```

### Доступ к интерфейсам

- **Swagger UI**: http://localhost:9000/apidocs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:8080 (логин: admin, пароль: admin)
- **Qdrant Dashboard**: http://localhost:6333/dashboard

### Импорт Grafana дашборда

1. Откройте Grafana: http://localhost:8080
2. Войдите (admin/admin)
3. Dashboards → Import
4. Загрузите файл: `monitoring/grafana/dashboards/rag-overview.json`

## Готово! 🎉

Теперь ваша RAG-система работает и готова к использованию.

## Следующие шаги

### Для пользователей
- 📖 Изучите [примеры использования](examples.md)
- ❓ Проверьте [FAQ](faq.md)
- 📊 Настройте [мониторинг](monitoring_setup.md)

### Для разработчиков
- 🛠️ Прочитайте [Development Guide](development_guide.md)
- 🏗️ Изучите [Architecture](architecture.md)
- 🧪 Запустите [тесты](testing_strategy.md)

### Для администраторов
- 🚀 Настройте [production deployment](deployment_guide.md)
- 📊 Подключите [Prometheus и Grafana](monitoring_setup.md)
- 🔄 Настройте [автоматическую переиндексацию](reindexing-guide.md)

## Решение проблем

### Проблема: Qdrant не запускается

```bash
# Проверить логи
docker-compose logs qdrant

# Пересоздать контейнер
docker-compose down
docker-compose up -d qdrant
```

### Проблема: Embeddings не работают

```bash
# Проверить доступность модели
python -c "from app.services.core.embeddings import get_embeddings_service; svc = get_embeddings_service(); print(svc.embed_dense('test')[:5])"

# Если ошибка - попробуйте CPU fallback
# В .env установите:
EMBEDDING_DEVICE=cpu
```

### Проблема: LLM не отвечает

```bash
# Проверить API ключи в .env
# Проверить доступность LLM провайдера
curl -X GET http://localhost:9000/v1/admin/circuit-breakers

# Если Circuit Breaker открыт - сбросить
curl -X POST http://localhost:9000/v1/admin/circuit-breakers/reset
```

### Проблема: Telegram бот не отвечает

```bash
# Проверить токен
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('TELEGRAM_BOT_TOKEN'))"

# Проверить соединение с API
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Проверить Flask API
curl http://localhost:9000/v1/admin/health
```

## Troubleshooting

### Ошибка "Telegram Bot 409 Conflict"

Если вы видите в логах:
```
ERROR | __main__:get_updates:193 - Failed to get updates: 409
```

**Причина**: Несколько экземпляров бота пытаются одновременно получать обновления, или установлен webhook.

**Решение**:
```bash
python scripts/fix_telegram_409.py
```

После исправления бот автоматически будет предотвращать эту проблему при запуске.

### Бот не отвечает

1. **Проверьте статус Flask API**:
   ```bash
   curl http://localhost:9000/v1/admin/health
   ```

2. **Проверьте логи бота**:
   ```bash
   # Если запущен через скрипт
   tail -f logs/app.log

   # Если запущен через Docker
   docker-compose logs -f telegram-bot
   ```

3. **Проверьте Qdrant**:
   ```bash
   curl http://localhost:6333/collections
   ```

### Медленные ответы

1. **Включите кэширование** (если не включено):
   ```bash
   CACHE_ENABLED=true
   ```

2. **Увеличьте количество workers**:
   ```bash
   gunicorn --workers 4 --threads 2 wsgi:app
   ```

3. **Используйте GPU** (если доступно):
   ```bash
   RERANKER_DEVICE=cuda
   ```

### Проблемы с индексацией

1. **Проверьте коллекцию в Qdrant**:
   ```bash
   python scripts/deep_analysis.py
   ```

2. **Переиндексируйте данные**:
   ```bash
   python ingestion/run.py --force
   ```

3. **Проверьте логи индексации**:
   ```bash
   tail -f logs/reindex.log
   ```

Подробнее в [FAQ](faq.md#проблемы-и-решения).

## Полезные команды

```bash
# Проверить статус всех сервисов
docker-compose ps

# Посмотреть логи
docker-compose logs -f

# Перезапустить сервис
docker-compose restart qdrant

# Остановить все
docker-compose down

# Очистить всё (включая volumes)
docker-compose down -v

# Запустить тесты
make test

# Проверить покрытие
make test-coverage

# Форматировать код
make format

# Линтинг
make lint
```

## Дополнительная информация

- 📚 [Полная документация](README.md)
- 🏗️ [Архитектура системы](architecture.md)
- 🔧 [API Reference](api_reference.md)
- 💡 [Примеры кода](examples.md)

---

**Нужна помощь?** Проверьте [FAQ](faq.md) или создайте issue в репозитории.
