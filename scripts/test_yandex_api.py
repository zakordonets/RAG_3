#!/usr/bin/env python3
"""
Простой тест для проверки YandexGPT API
"""
import os
import sys
import requests
import json
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_yandex_api():
    """Тестирует YandexGPT API с разными эндпоинтами"""

    logger.info("🧪 Тестирование YandexGPT API")
    logger.info("=" * 50)

    # Проверяем конфигурацию
    logger.info(f"API URL: {CONFIG.yandex_api_url}")
    logger.info(f"Model: {CONFIG.yandex_model}")
    logger.info(f"Catalog ID: {CONFIG.yandex_catalog_id}")
    logger.info(f"API Key: {'*' * 20}{CONFIG.yandex_api_key[-4:] if CONFIG.yandex_api_key else 'None'}")

    # Тестовые эндпоинты для проверки
    endpoints = [
        "/completion",
        "/text:generate",
        "/llm/v1alpha/instruct/text:generate",
        "/llm/v1alpha/instruct/completion"
    ]

    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }

    # Простой тестовый запрос
    test_prompt = "Привет! Как дела?"

    for endpoint in endpoints:
        url = f"{CONFIG.yandex_api_url}{endpoint}"
        logger.info(f"\n🔍 Тестируем эндпоинт: {url}")

        # Пробуем разные форматы payload
        payloads = [
            # Новый формат (completion)
            {
                "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.2,
                    "maxTokens": "100"
                },
                "messages": [
                    {
                        "role": "user",
                        "text": test_prompt
                    }
                ]
            },
            # Старый формат (text:generate)
            {
                "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
                "maxTokens": "100",
                "temperature": 0.2,
                "texts": [test_prompt]
            }
        ]

        for i, payload in enumerate(payloads):
            try:
                logger.info(f"  📤 Payload {i+1}: {json.dumps(payload, ensure_ascii=False, indent=2)}")

                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                status = resp.status_code

                logger.info(f"  📥 Статус: {status}")

                if status == 200:
                    try:
                        data = resp.json()
                        logger.success(f"  ✅ Успех! Ответ: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
                        return True
                    except Exception as e:
                        logger.error(f"  ❌ Ошибка парсинга JSON: {e}")
                        logger.info(f"  📄 Сырой ответ: {resp.text[:500]}")
                else:
                    logger.warning(f"  ⚠️ HTTP {status}: {resp.text[:200]}")

            except requests.exceptions.Timeout:
                logger.error(f"  ⏰ Таймаут запроса")
            except requests.exceptions.ConnectionError:
                logger.error(f"  🔌 Ошибка подключения")
            except Exception as e:
                logger.error(f"  ❌ Ошибка: {type(e).__name__}: {e}")

    logger.error("❌ Все эндпоинты не работают")
    return False

def test_iam_token():
    """Тестирует использование IAM токена вместо API ключа"""

    logger.info("\n🔑 Тестирование с IAM токеном")
    logger.info("=" * 50)

    # Проверяем, есть ли IAM токен в конфигурации
    if not hasattr(CONFIG, 'yandex_iam_token') or not CONFIG.yandex_iam_token:
        logger.warning("IAM токен не найден в конфигурации")
        return False

    url = f"{CONFIG.yandex_api_url}/completion"
    headers = {
        "Authorization": f"Bearer {CONFIG.yandex_iam_token}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }

    payload = {
        "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": "100"
        },
        "messages": [
            {
                "role": "user",
                "text": "Привет! Как дела?"
            }
        ]
    }

    try:
        logger.info(f"URL: {url}")
        logger.info(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        status = resp.status_code

        logger.info(f"Статус: {status}")

        if status == 200:
            data = resp.json()
            logger.success(f"✅ IAM токен работает! Ответ: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
            return True
        else:
            logger.warning(f"⚠️ HTTP {status}: {resp.text[:200]}")

    except Exception as e:
        logger.error(f"❌ Ошибка с IAM токеном: {type(e).__name__}: {e}")

    return False

def main():
    """Главная функция тестирования"""

    logger.info("🚀 Запуск тестов YandexGPT API")
    logger.info("=" * 60)

    # Проверяем базовую конфигурацию
    if not CONFIG.yandex_api_key:
        logger.error("❌ Yandex API ключ не настроен")
        return

    if not CONFIG.yandex_catalog_id:
        logger.error("❌ Yandex Catalog ID не настроен")
        return

    if not CONFIG.yandex_model:
        logger.error("❌ Yandex модель не настроена")
        return

    # Тестируем API ключ
    success = test_yandex_api()

    if not success:
        # Тестируем IAM токен
        test_iam_token()

    logger.info("=" * 60)
    if success:
        logger.success("✅ Тестирование завершено успешно!")
    else:
        logger.error("❌ Тестирование завершено с ошибками")

if __name__ == "__main__":
    main()
