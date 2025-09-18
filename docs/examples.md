# Примеры использования

## Базовые примеры

### 1. Простой запрос к API

```python
import requests

# Отправка запроса
response = requests.post(
    "http://localhost:9000/v1/chat/query",
    json={
        "channel": "web",
        "chat_id": "user123",
        "message": "Как настроить маршрутизацию в Chat Center?"
    }
)

# Обработка ответа
if response.status_code == 200:
    data = response.json()
    print(f"Ответ: {data['answer']}")
    print(f"Источники: {len(data['sources'])}")
    for source in data['sources']:
        print(f"- {source['title']}: {source['url']}")
else:
    print(f"Ошибка: {response.status_code} - {response.text}")
```

### 2. Проверка состояния системы

```python
import requests

# Проверка здоровья системы
health_response = requests.get("http://localhost:9000/v1/admin/health")
health_data = health_response.json()

print(f"Статус системы: {health_data['status']}")
if 'components' in health_data:
    for component, status in health_data['components'].items():
        print(f"{component}: {status}")
```

### 3. Переиндексация документации

```python
import requests

# Запуск переиндексации
reindex_response = requests.post(
    "http://localhost:9000/v1/admin/reindex",
    json={"incremental": True}
)

if reindex_response.status_code == 200:
    data = reindex_response.json()
    print(f"Переиндексация запущена: {data['job_id']}")
    print(f"Ожидаемое время: {data['estimated_duration_minutes']} минут")
```

## Продвинутые примеры

### 1. Асинхронный клиент

```python
import asyncio
import aiohttp
import json

async def ask_question_async(session, message, chat_id="default"):
    """Асинхронный запрос к API."""
    url = "http://localhost:9000/v1/chat/query"
    payload = {
        "channel": "web",
        "chat_id": chat_id,
        "message": message
    }

    async with session.post(url, json=payload) as response:
        if response.status == 200:
            data = await response.json()
            return data
        else:
            error_text = await response.text()
            raise Exception(f"API error: {response.status} - {error_text}")

async def process_multiple_questions():
    """Обработка нескольких вопросов параллельно."""
    questions = [
        "Как настроить маршрутизацию?",
        "Что такое сегментация?",
        "Как добавить бота?",
        "Где найти API документацию?",
        "Как настроить уведомления?"
    ]

    async with aiohttp.ClientSession() as session:
        tasks = [
            ask_question_async(session, question, f"user_{i}")
            for i, question in enumerate(questions)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Вопрос {i+1}: Ошибка - {result}")
            else:
                print(f"Вопрос {i+1}: {result['answer'][:100]}...")

# Запуск
asyncio.run(process_multiple_questions())
```

### 2. Класс-обертка для API

```python
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ChatResponse:
    answer: str
    sources: List[Dict[str, str]]
    channel: str
    chat_id: str

class ChatCenterAPI:
    """Клиент для работы с Chat Center API."""

    def __init__(self, base_url: str = "http://localhost:9000"):
        self.base_url = base_url
        self.session = requests.Session()

    def ask(self, message: str, chat_id: str = "default", channel: str = "web") -> ChatResponse:
        """Задать вопрос системе."""
        response = self.session.post(
            f"{self.base_url}/v1/chat/query",
            json={
                "channel": channel,
                "chat_id": chat_id,
                "message": message
            }
        )
        response.raise_for_status()

        data = response.json()
        return ChatResponse(
            answer=data["answer"],
            sources=data["sources"],
            channel=data["channel"],
            chat_id=data["chat_id"]
        )

    def health_check(self) -> Dict:
        """Проверить состояние системы."""
        response = self.session.get(f"{self.base_url}/v1/admin/health")
        response.raise_for_status()
        return response.json()

    def reindex(self, incremental: bool = True) -> Dict:
        """Запустить переиндексацию."""
        response = self.session.post(
            f"{self.base_url}/v1/admin/reindex",
            json={"incremental": incremental}
        )
        response.raise_for_status()
        return response.json()

    def close(self):
        """Закрыть сессию."""
        self.session.close()

# Использование
api = ChatCenterAPI()

try:
    # Задать вопрос
    response = api.ask("Как настроить маршрутизацию?")
    print(f"Ответ: {response.answer}")

    # Проверить здоровье
    health = api.health_check()
    print(f"Система: {health['status']}")

finally:
    api.close()
```

### 3. Интеграция с Flask приложением

```python
from flask import Flask, request, jsonify, render_template
from chat_center_api import ChatCenterAPI

app = Flask(__name__)
api = ChatCenterAPI()

@app.route('/')
def index():
    """Главная страница с формой."""
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_question():
    """Обработка вопроса пользователя."""
    data = request.get_json()
    message = data.get('message', '')
    chat_id = data.get('chat_id', 'web_user')

    if not message:
        return jsonify({'error': 'Message is required'}), 400

    try:
        response = api.ask(message, chat_id)
        return jsonify({
            'answer': response.answer,
            'sources': response.sources
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Проверка состояния системы."""
    try:
        health_data = api.health_check()
        return jsonify(health_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
```

### 4. Telegram бот с дополнительной логикой

```python
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from chat_center_api import ChatCenterAPI

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class ChatCenterBot:
    def __init__(self, token: str, api_url: str = "http://localhost:9000"):
        self.api = ChatCenterAPI(api_url)
        self.application = Application.builder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Настройка обработчиков команд."""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start."""
        welcome_message = """
🤖 *Добро пожаловать в Chat Center Assistant!*

Я помогу вам с вопросами по настройке и использованию edna Chat Center.

*Доступные команды:*
/help - Справка
/status - Статус системы

Просто напишите ваш вопрос, и я постараюсь помочь!
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help."""
        help_message = """
*Справка по использованию:*

🔧 *Настройка:*
• Как настроить маршрутизацию?
• Как создать сегменты?
• Как добавить бота?

📊 *Мониторинг:*
• Как посмотреть статистику?
• Как настроить уведомления?

🔗 *API:*
• Где найти API документацию?
• Как использовать webhooks?

Просто напишите ваш вопрос!
        """
        await update.message.reply_text(help_message, parse_mode='Markdown')

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status."""
        try:
            health = self.api.health_check()
            status_message = f"🟢 *Система работает*\n\n"

            if 'components' in health:
                for component, status in health['components'].items():
                    emoji = "🟢" if status.get('status') == 'healthy' else "🔴"
                    status_message += f"{emoji} {component}: {status.get('status', 'unknown')}\n"

            await update.message.reply_text(status_message, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"🔴 Ошибка проверки статуса: {str(e)}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений."""
        message = update.message.text
        chat_id = str(update.effective_chat.id)

        # Показываем, что обрабатываем запрос
        await update.message.reply_text("🤔 Обрабатываю ваш запрос...")

        try:
            response = self.api.ask(message, chat_id, "telegram")

            # Отправляем ответ
            await update.message.reply_text(
                response.answer,
                parse_mode='MarkdownV2',
                disable_web_page_preview=True
            )

            # Отправляем источники, если есть
            if response.sources:
                sources_text = "\n📚 *Источники:*\n"
                for source in response.sources[:3]:  # Показываем только первые 3
                    sources_text += f"• [{source['title']}]({source['url']})\n"

                await update.message.reply_text(
                    sources_text,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )

        except Exception as e:
            error_message = f"❌ Произошла ошибка при обработке запроса:\n{str(e)}"
            await update.message.reply_text(error_message)

    def run(self):
        """Запуск бота."""
        self.application.run_polling()

# Использование
if __name__ == '__main__':
    bot = ChatCenterBot("YOUR_BOT_TOKEN")
    bot.run()
```

## Примеры интеграции

### 1. Интеграция с Django

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from chat_center_api import ChatCenterAPI

api = ChatCenterAPI()

@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """API endpoint для чата."""
    try:
        data = json.loads(request.body)
        message = data.get('message', '')
        chat_id = data.get('chat_id', 'django_user')

        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        response = api.ask(message, chat_id)
        return JsonResponse({
            'answer': response.answer,
            'sources': response.sources
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def health_check(request):
    """Проверка состояния системы."""
    try:
        health = api.health_check()
        return JsonResponse(health)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

### 2. Интеграция с FastAPI

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from chat_center_api import ChatCenterAPI

app = FastAPI(title="Chat Center Integration")
api = ChatCenterAPI()

class ChatRequest(BaseModel):
    message: str
    chat_id: str = "fastapi_user"
    channel: str = "web"

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Обработка чат-запросов."""
    try:
        response = api.ask(request.message, request.chat_id, request.channel)
        return ChatResponse(
            answer=response.answer,
            sources=response.sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Проверка состояния системы."""
    try:
        return api.health_check()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. Интеграция с Slack

```python
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from chat_center_api import ChatCenterAPI

class SlackChatCenterBot:
    def __init__(self, slack_token: str, api_url: str = "http://localhost:9000"):
        self.slack_client = WebClient(token=slack_token)
        self.api = ChatCenterAPI(api_url)

    def handle_mention(self, event):
        """Обработка упоминаний бота."""
        channel = event["channel"]
        text = event["text"]
        user = event["user"]

        # Убираем упоминание бота из текста
        message = text.replace(f"<@{self.bot_id}>", "").strip()

        if not message:
            self.slack_client.chat_postMessage(
                channel=channel,
                text="Привет! Напишите ваш вопрос по Chat Center."
            )
            return

        try:
            # Получаем ответ от API
            response = self.api.ask(message, user, "slack")

            # Форматируем ответ для Slack
            slack_message = f"*Ответ:*\n{response.answer}"

            if response.sources:
                slack_message += "\n\n*Источники:*"
                for source in response.sources[:3]:
                    slack_message += f"\n• <{source['url']}|{source['title']}>"

            self.slack_client.chat_postMessage(
                channel=channel,
                text=slack_message
            )

        except Exception as e:
            self.slack_client.chat_postMessage(
                channel=channel,
                text=f"❌ Ошибка: {str(e)}"
            )
```

## Примеры тестирования

### 1. Unit тесты

```python
import pytest
from unittest.mock import Mock, patch
from chat_center_api import ChatCenterAPI

class TestChatCenterAPI:
    def setup_method(self):
        self.api = ChatCenterAPI("http://localhost:9000")

    @patch('requests.Session.post')
    def test_ask_success(self, mock_post):
        """Тест успешного запроса."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "sources": [{"title": "Test", "url": "http://test.com"}],
            "channel": "web",
            "chat_id": "test"
        }
        mock_post.return_value = mock_response

        response = self.api.ask("test question")

        assert response.answer == "Test answer"
        assert len(response.sources) == 1
        assert response.channel == "web"

    @patch('requests.Session.post')
    def test_ask_error(self, mock_post):
        """Тест обработки ошибки."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_post.return_value = mock_response

        with pytest.raises(Exception):
            self.api.ask("test question")
```

### 2. Integration тесты

```python
import pytest
import requests
from chat_center_api import ChatCenterAPI

@pytest.fixture
def api():
    return ChatCenterAPI("http://localhost:9000")

def test_health_check(api):
    """Тест проверки здоровья системы."""
    health = api.health_check()
    assert health["status"] == "ok"

def test_ask_question(api):
    """Тест задавания вопроса."""
    response = api.ask("Как настроить маршрутизацию?")
    assert "answer" in response.__dict__
    assert "sources" in response.__dict__
    assert len(response.sources) > 0
```

### 3. Load тесты

```python
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test():
    """Нагрузочное тестирование API."""
    questions = [
        "Как настроить маршрутизацию?",
        "Что такое сегментация?",
        "Как добавить бота?",
        "Где найти API документацию?",
        "Как настроить уведомления?"
    ] * 20  # 100 запросов

    async with aiohttp.ClientSession() as session:
        start_time = time.time()

        tasks = []
        for i, question in enumerate(questions):
            task = make_request(session, question, f"user_{i}")
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        duration = end_time - start_time

        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful

        print(f"Запросов: {len(questions)}")
        print(f"Успешных: {successful}")
        print(f"Неудачных: {failed}")
        print(f"Время: {duration:.2f} сек")
        print(f"RPS: {len(questions) / duration:.2f}")

async def make_request(session, question, chat_id):
    """Выполнение одного запроса."""
    url = "http://localhost:9000/v1/chat/query"
    payload = {
        "channel": "web",
        "chat_id": chat_id,
        "message": question
    }

    async with session.post(url, json=payload) as response:
        if response.status == 200:
            return await response.json()
        else:
            raise Exception(f"HTTP {response.status}")

# Запуск нагрузочного теста
asyncio.run(load_test())
```

## Заключение

Эти примеры показывают различные способы интеграции RAG-системы с вашими приложениями. Выберите подходящий подход в зависимости от ваших потребностей и технологического стека.
