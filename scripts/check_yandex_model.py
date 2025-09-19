#!/usr/bin/env python3
"""
Скрипт для проверки используемой модели YandexGPT
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

def check_yandex_model():
    """Проверяет какая модель YandexGPT используется"""

    logger.info("🔍 Проверка модели YandexGPT")
    logger.info("=" * 50)

    # Показываем конфигурацию
    logger.info(f"API URL: {CONFIG.yandex_api_url}")
    logger.info(f"Catalog ID: {CONFIG.yandex_catalog_id}")
    logger.info(f"Model: {CONFIG.yandex_model}")
    logger.info(f"Max Tokens: {CONFIG.yandex_max_tokens}")
    logger.info(f"API Key: {'*' * 20}{CONFIG.yandex_api_key[-4:] if CONFIG.yandex_api_key else 'None'}")

    # Подготавливаем запрос
    url = f"{CONFIG.yandex_api_url}/completion"
    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }

    # Запрос на получение названия модели
    payload = {
        "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": "100"
        },
        "messages": [
            {
                "role": "user",
                "text": "Как называется твоя модель? Назови точное название модели, которую ты используешь."
            }
        ]
    }

    try:
        logger.info(f"\n📤 Отправляем запрос к: {url}")
        logger.info(f"📤 Model URI: gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}")

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        status = resp.status_code

        logger.info(f"📥 Статус ответа: {status}")

        if status == 200:
            data = resp.json()

            # Извлекаем информацию о модели
            try:
                model_version = data.get("result", {}).get("modelVersion", "Не указано")
                usage = data.get("result", {}).get("usage", {})
                response_text = data["result"]["alternatives"][0]["message"]["text"]

                logger.success("✅ Запрос успешен!")
                logger.info(f"📋 Версия модели: {model_version}")
                logger.info(f"📋 Название модели из конфигурации: {CONFIG.yandex_model}")
                logger.info(f"📋 Ответ модели о своём названии: {response_text}")

                # Детальная информация об использовании токенов
                if usage:
                    logger.info(f"📊 Токены:")
                    logger.info(f"  - Входные: {usage.get('inputTextTokens', 'N/A')}")
                    logger.info(f"  - Выходные: {usage.get('completionTokens', 'N/A')}")
                    logger.info(f"  - Всего: {usage.get('totalTokens', 'N/A')}")

                # Показываем полный ответ для анализа
                logger.info(f"\n📄 Полный ответ API:")
                logger.info(json.dumps(data, ensure_ascii=False, indent=2))

                return {
                    "success": True,
                    "model_version": model_version,
                    "response_text": response_text,
                    "usage": usage,
                    "full_response": data
                }

            except KeyError as e:
                logger.error(f"❌ Ошибка парсинга ответа: {e}")
                logger.info(f"📄 Сырой ответ: {json.dumps(data, ensure_ascii=False, indent=2)}")
                return {"success": False, "error": f"Parse error: {e}"}

        else:
            logger.error(f"❌ HTTP {status}: {resp.text[:500]}")
            return {"success": False, "error": f"HTTP {status}"}

    except requests.exceptions.Timeout:
        logger.error("⏰ Таймаут запроса")
        return {"success": False, "error": "Timeout"}
    except requests.exceptions.ConnectionError:
        logger.error("🔌 Ошибка подключения")
        return {"success": False, "error": "Connection error"}
    except Exception as e:
        logger.error(f"❌ Ошибка: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}

def check_available_models():
    """Проверяет доступные модели (если API поддерживает)"""

    logger.info("\n🔍 Проверка доступных моделей")
    logger.info("=" * 50)

    # Пробуем разные эндпоинты для получения списка моделей
    endpoints = [
        "/models",
        "/foundationModels",
        "/llm/v1alpha/models"
    ]

    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }

    for endpoint in endpoints:
        url = f"{CONFIG.yandex_api_url}{endpoint}"
        try:
            logger.info(f"🔍 Проверяем: {url}")
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                logger.success(f"✅ Найден эндпоинт: {url}")
                logger.info(f"📄 Ответ: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
                return data
            else:
                logger.warning(f"⚠️ {url}: HTTP {resp.status_code}")

        except Exception as e:
            logger.debug(f"❌ {url}: {e}")

    logger.warning("⚠️ Не удалось найти эндпоинт для получения списка моделей")
    return None

def main():
    """Главная функция"""

    logger.info("🚀 Проверка модели YandexGPT")
    logger.info("=" * 60)

    # Проверяем базовую конфигурацию
    if not CONFIG.yandex_api_key:
        logger.error("❌ Yandex API ключ не настроен")
        return

    if not CONFIG.yandex_catalog_id:
        logger.error("❌ Yandex Catalog ID не настроен")
        return

    # Проверяем модель
    result = check_yandex_model()

    if result["success"]:
        logger.info("\n" + "=" * 60)
        logger.success("✅ Проверка завершена успешно!")
        logger.info(f"📋 Название модели: {CONFIG.yandex_model}")
        logger.info(f"📋 Версия модели: {result['model_version']}")
        logger.info(f"📋 Ответ модели о своём названии: {result['response_text']}")
    else:
        logger.error(f"❌ Ошибка: {result['error']}")

    # Пробуем получить список доступных моделей
    check_available_models()

if __name__ == "__main__":
    main()
