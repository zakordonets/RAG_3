# Telegram Bot 409 Conflict Fix

## Описание

Утилита для исправления ошибки 409 (Conflict) в Telegram Bot API.

## Проблема

Ошибка 409 возникает когда:
- Несколько экземпляров бота пытаются использовать long polling одновременно
- У бота установлен webhook, который конфликтует с polling
- Предыдущий процесс бота не завершился корректно

## Использование

### Windows (PowerShell)
```powershell
.\fix_telegram_409.ps1
```

### Windows (CMD)
```cmd
fix_telegram_409.bat
```

### Linux/macOS/Прямой запуск
```bash
python scripts/fix_telegram_409.py
```

## Что делает скрипт

1. ✅ Проверяет статус бота
2. ✅ Проверяет наличие webhook
3. ✅ Удаляет webhook (если установлен)
4. ✅ Очищает pending updates
5. ✅ Проверяет работоспособность getUpdates

## Автоматическое исправление

С версии 2.0 бот автоматически:
- Проверяет и удаляет webhook при запуске
- Обрабатывает ошибку 409 во время работы
- Пытается автоматически восстановить соединение

## Ручное исправление

Если автоматическое исправление не помогло:

### 1. Остановите все экземпляры бота

**Windows (PowerShell):**
```powershell
Get-Process python | Where-Object {$_.CommandLine -like "*telegram*"} | Stop-Process
```

**Linux/macOS:**
```bash
ps aux | grep telegram | grep -v grep | awk '{print $2}' | xargs kill
```

### 2. Остановите Docker контейнеры

```bash
docker-compose down
```

### 3. Удалите webhook вручную

```python
import requests
BOT_TOKEN = "your_token"
requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
    json={"drop_pending_updates": True}
)
```

### 4. Подождите и перезапустите

Подождите 1-2 минуты, затем запустите бота снова:

```bash
.\start_telegram_bot.ps1
```

## Отладка

### Проверка запущенных процессов

```bash
# Windows
Get-Process python

# Linux/macOS
ps aux | grep python
```

### Проверка Docker контейнеров

```bash
docker ps | grep telegram
```

### Проверка webhook

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

## Предотвращение

Чтобы избежать ошибки 409:

1. ✅ Запускайте только один экземпляр бота
2. ✅ Используйте polling ИЛИ webhook (не оба)
3. ✅ В Docker Compose: `replicas: 1`
4. ✅ В Kubernetes: `replicas: 1` в deployment
5. ✅ Корректно останавливайте бота (Ctrl+C или `docker-compose down`)

## Подробная документация

- [FAQ - Ошибка 409](../docs/faq.md#ошибка-telegram-bot-409-conflict)
- [Quickstart - Troubleshooting](../docs/quickstart.md#troubleshooting)
- [Deployment Guide](../docs/deployment_guide.md)

## Поддержка

Если проблема не решается:
1. Проверьте логи: `tail -f logs/app.log`
2. Создайте issue с описанием проблемы
3. Приложите вывод скрипта `fix_telegram_409.py`
