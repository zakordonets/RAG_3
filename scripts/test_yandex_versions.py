#!/usr/bin/env python3
"""
Скрипт для тестирования разных версий YandexGPT (/latest, /rc, /deprecated)
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

def test_model_version(version_suffix=""):
    """Тестирует конкретную версию модели"""

    model_name = f"yandexgpt{version_suffix}"
    model_uri = f"gpt://{CONFIG.yandex_catalog_id}/{model_name}"

    logger.info(f"\n🔍 Тестируем модель: {model_name}")
    logger.info(f"📤 Model URI: {model_uri}")

    url = f"{CONFIG.yandex_api_url}/completion"
    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }

    payload = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": "100"
        },
        "messages": [
            {
                "role": "user",
                "text": "Как называется твоя модель? Назови точное название и версию."
            }
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        status = resp.status_code

        if status == 200:
            data = resp.json()
            model_version = data.get("result", {}).get("modelVersion", "Не указано")
            response_text = data["result"]["alternatives"][0]["message"]["text"]
            usage = data.get("result", {}).get("usage", {})

            logger.success(f"✅ {model_name} работает!")
            logger.info(f"📋 Версия: {model_version}")
            logger.info(f"📋 Ответ: {response_text}")
            logger.info(f"📊 Токены: {usage.get('totalTokens', 'N/A')}")

            return {
                "success": True,
                "model_name": model_name,
                "model_version": model_version,
                "response": response_text,
                "usage": usage
            }
        else:
            logger.warning(f"⚠️ {model_name}: HTTP {status} - {resp.text[:200]}")
            return {
                "success": False,
                "model_name": model_name,
                "error": f"HTTP {status}"
            }

    except Exception as e:
        logger.error(f"❌ {model_name}: {type(e).__name__}: {e}")
        return {
            "success": False,
            "model_name": model_name,
            "error": str(e)
        }

def main():
    """Тестирует разные версии YandexGPT"""

    logger.info("🚀 Тестирование версий YandexGPT")
    logger.info("=" * 60)

    # Проверяем конфигурацию
    if not CONFIG.yandex_api_key:
        logger.error("❌ Yandex API ключ не настроен")
        return

    if not CONFIG.yandex_catalog_id:
        logger.error("❌ Yandex Catalog ID не настроен")
        return

    logger.info(f"📋 Catalog ID: {CONFIG.yandex_catalog_id}")
    logger.info(f"📋 API URL: {CONFIG.yandex_api_url}")

    # Тестируем разные версии
    versions = [
        "",           # Базовая версия (yandexgpt)
        "/latest",    # Последняя стабильная версия
        "/rc",        # Release candidate
        "/deprecated" # Устаревшая версия
    ]

    results = []

    for version_suffix in versions:
        result = test_model_version(version_suffix)
        results.append(result)

    # Сводка результатов
    logger.info("\n" + "=" * 60)
    logger.info("📊 СВОДКА РЕЗУЛЬТАТОВ")
    logger.info("=" * 60)

    working_models = []

    for result in results:
        if result["success"]:
            logger.success(f"✅ {result['model_name']}: {result['model_version']}")
            working_models.append(result)
        else:
            logger.error(f"❌ {result['model_name']}: {result['error']}")

    if working_models:
        logger.info(f"\n🎯 Доступно рабочих моделей: {len(working_models)}")

        # Рекомендуем лучшую версию
        if any(r["model_name"] == "yandexgpt/rc" for r in working_models):
            logger.info("💡 Рекомендация: Используйте yandexgpt/rc для доступа к новейшим функциям")
        elif any(r["model_name"] == "yandexgpt/latest" for r in working_models):
            logger.info("💡 Рекомендация: Используйте yandexgpt/latest для стабильной версии")
        else:
            logger.info("💡 Рекомендация: Используйте базовую версию yandexgpt")
    else:
        logger.error("❌ Ни одна версия модели не работает")

if __name__ == "__main__":
    main()
