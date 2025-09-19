# Отчет об исправлении YandexGPT API

## Проблема
YandexGPT API возвращал HTTP 404 ошибку при попытке использования.

## Причина
Использовался неправильный базовый URL для API:
- ❌ **Неправильно**: `https://llm.api.cloud.yandex.net/v1`
- ✅ **Правильно**: `https://llm.api.cloud.yandex.net/foundationModels/v1`

## Исправления

### 1. Обновлен базовый URL в конфигурации
**Файл**: `app/config.py`
```python
# Было:
yandex_api_url: str = os.getenv("YANDEX_API_URL", "https://llm.api.cloud.yandex.net/v1")

# Стало:
yandex_api_url: str = os.getenv("YANDEX_API_URL", "https://llm.api.cloud.yandex.net/foundationModels/v1")
```

### 2. Обновлен URL в .env файле
**Файл**: `.env`
```bash
# Было:
YANDEX_API_URL=https://llm.api.cloud.yandex.net/v1

# Стало:
YANDEX_API_URL=https://llm.api.cloud.yandex.net/foundationModels/v1
```

### 3. Обновлен формат запроса согласно документации
**Файл**: `app/services/llm_router.py`
```python
# Новый формат payload для completion API
payload = {
    "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
    "completionOptions": {
        "stream": False,
        "temperature": 0.2,
        "maxTokens": str(min(max_tokens, CONFIG.yandex_max_tokens))
    },
    "messages": [
        {
            "role": "user",
            "text": prompt
        }
    ]
}
```

### 4. Обновлен парсинг ответа
**Файл**: `app/services/llm_router.py`
```python
# Новый формат парсинга ответа
text = data["result"]["alternatives"][0]["message"]["text"]
```

## Результат
✅ YandexGPT API теперь работает корректно
✅ RAG пайплайн полностью функционален с YandexGPT
✅ Ответы генерируются на русском языке с правильным форматированием

## Тестирование
Создан тестовый скрипт `scripts/test_yandex_api.py` для проверки работы API.

**Пример успешного ответа:**
```json
{
  "result": {
    "alternatives": [
      {
        "message": {
          "role": "assistant",
          "text": "Привет! У меня всё хорошо, спасибо. А как у вас дела?"
        },
        "status": "ALTERNATIVE_STATUS_FINAL"
      }
    ],
    "usage": {
      "inputTextTokens": "15",
      "completionTokens": "15",
      "totalTokens": "30"
    },
    "modelVersion": "09.02.2025"
  }
}
```
