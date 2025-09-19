# Redis Setup для RAG системы

## 🚀 Быстрый старт

### 1. Запуск Redis через Docker Compose

```bash
# Запустить только Redis
docker-compose up -d redis

# Проверить статус
docker-compose ps

# Посмотреть логи
docker-compose logs redis
```

### 2. Альтернативный способ - отдельный контейнер

```bash
# Запустить Redis без пароля
docker run -d --name rag-redis -p 6379:6379 redis:7-alpine

# Запустить Redis с паролем
docker run -d --name rag-redis -p 6379:6379 -e REDIS_PASSWORD=your_password redis:7-alpine redis-server --requirepass your_password
```

## ⚙️ Конфигурация

### Переменные окружения в .env:

```env
# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=                    # Оставьте пустым для работы без пароля
```

### Для Docker Compose (в .env):

```env
# Redis Configuration
REDIS_URL=redis://redis:6379       # Для контейнеров используйте имя сервиса
REDIS_PASSWORD=                    # Опционально
```

## 🔧 Проверка работы

### 1. Проверка подключения

```bash
# Через redis-cli
docker exec -it rag-redis redis-cli ping
# Должно вернуть: PONG

# Через Python
python -c "import redis; r = redis.Redis(host='localhost', port=6379); print(r.ping())"
```

### 2. Проверка в приложении

После запуска Redis, в логах приложения должно появиться:
```
INFO | app.caching:__init__:80 - Redis connection successful
```

Вместо:
```
WARNING | app.caching:__init__:80 - Redis connection failed: Error 10061...
```

## 📊 Преимущества Redis

- **Кеширование эмбеддингов** - ускорение повторных запросов
- **Кеширование результатов поиска** - быстрые ответы на похожие вопросы
- **Rate limiting** - защита от спама
- **Session storage** - для Telegram бота

## 🛠️ Управление

### Остановка Redis:
```bash
docker-compose down redis
# или
docker stop rag-redis
```

### Удаление данных:
```bash
docker volume rm rag_clean_redis_data
```

### Мониторинг:
```bash
# Статистика Redis
docker exec -it rag-redis redis-cli info

# Мониторинг в реальном времени
docker exec -it rag-redis redis-cli monitor
```

## 🔒 Безопасность

### Для production:

1. **Установите пароль:**
   ```env
   REDIS_PASSWORD=strong_password_here
   ```

2. **Ограничьте доступ:**
   ```yaml
   # В docker-compose.yml
   redis:
     ports:
       - "127.0.0.1:6379:6379"  # Только локальный доступ
   ```

3. **Используйте SSL:**
   ```env
   REDIS_URL=rediss://localhost:6380
   ```

## 🚨 Troubleshooting

### Проблема: Redis не запускается
```bash
# Проверить логи
docker-compose logs redis

# Перезапустить
docker-compose restart redis
```

### Проблема: Приложение не подключается
1. Проверьте, что Redis запущен: `docker-compose ps`
2. Проверьте URL в .env файле
3. Проверьте, что порт 6379 свободен: `netstat -an | findstr :6379`

### Проблема: Медленная работа
```bash
# Очистить кеш
docker exec -it rag-redis redis-cli flushall

# Проверить использование памяти
docker exec -it rag-redis redis-cli info memory
```
