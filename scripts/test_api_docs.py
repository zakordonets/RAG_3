#!/usr/bin/env python3
"""
Скрипт для тестирования API документации.
Проверяет доступность Swagger UI и OpenAPI спецификации.
"""

import requests
import json
import sys
from typing import Dict, Any


def test_swagger_ui(base_url: str = "http://localhost:9000") -> bool:
    """Тестирует доступность Swagger UI."""
    try:
        response = requests.get(f"{base_url}/apidocs", timeout=10)
        if response.status_code == 200:
            print("✅ Swagger UI доступен")
            return True
        else:
            print(f"❌ Swagger UI недоступен: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка доступа к Swagger UI: {e}")
        return False


def test_openapi_spec(base_url: str = "http://localhost:9000") -> bool:
    """Тестирует доступность OpenAPI спецификации."""
    try:
        response = requests.get(f"{base_url}/apispec_1.json", timeout=10)
        if response.status_code == 200:
            spec = response.json()
            print("✅ OpenAPI спецификация доступна")

            # Проверяем основные поля
            if "swagger" in spec and "info" in spec:
                print(f"   Версия OpenAPI: {spec.get('swagger', 'unknown')}")
                print(f"   Название API: {spec.get('info', {}).get('title', 'unknown')}")
                print(f"   Версия API: {spec.get('info', {}).get('version', 'unknown')}")

                # Подсчитываем endpoints
                paths = spec.get('paths', {})
                endpoint_count = len(paths)
                print(f"   Количество endpoints: {endpoint_count}")

                # Показываем доступные endpoints
                if endpoint_count > 0:
                    print("   Доступные endpoints:")
                    for path in sorted(paths.keys()):
                        methods = list(paths[path].keys())
                        print(f"     {path} [{', '.join(methods).upper()}]")

                return True
            else:
                print("❌ Некорректная OpenAPI спецификация")
                return False
        else:
            print(f"❌ OpenAPI спецификация недоступна: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка доступа к OpenAPI спецификации: {e}")
        return False


def test_api_endpoints(base_url: str = "http://localhost:9000") -> bool:
    """Тестирует основные API endpoints."""
    endpoints = [
        ("GET", "/v1/admin/health", "Health check"),
        ("GET", "/v1/admin/metrics", "Metrics"),
        ("GET", "/v1/admin/circuit-breakers", "Circuit Breakers"),
        ("GET", "/v1/admin/cache", "Cache status"),
        ("GET", "/v1/admin/rate-limiter", "Rate Limiter"),
        ("GET", "/v1/admin/security", "Security status"),
    ]

    success_count = 0
    total_count = len(endpoints)

    print(f"\n🧪 Тестирование {total_count} API endpoints:")

    for method, path, description in endpoints:
        try:
            url = f"{base_url}{path}"
            response = requests.request(method, url, timeout=10)

            if response.status_code == 200:
                print(f"   ✅ {method} {path} - {description}")
                success_count += 1
            else:
                print(f"   ❌ {method} {path} - {description} (HTTP {response.status_code})")
        except Exception as e:
            print(f"   ❌ {method} {path} - {description} (Ошибка: {e})")

    success_rate = (success_count / total_count) * 100
    print(f"\n📊 Результат: {success_count}/{total_count} endpoints работают ({success_rate:.1f}%)")

    return success_count == total_count


def test_chat_api(base_url: str = "http://localhost:9000") -> bool:
    """Тестирует основной chat API."""
    try:
        print("\n💬 Тестирование Chat API:")

        # Тестовый запрос
        test_data = {
            "message": "Тест API документации",
            "channel": "api",
            "chat_id": "test_docs"
        }

        response = requests.post(
            f"{base_url}/v1/chat/query",
            json=test_data,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            print("   ✅ Chat API работает")
            print(f"   📝 Ответ: {result.get('answer', 'N/A')[:100]}...")
            print(f"   ⏱️  Время обработки: {result.get('processing_time', 'N/A')}s")
            return True
        else:
            print(f"   ❌ Chat API ошибка: HTTP {response.status_code}")
            print(f"   📝 Ответ: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"   ❌ Chat API ошибка: {e}")
        return False


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование API документации RAG-системы")
    print("=" * 50)

    base_url = "http://localhost:9000"

    # Тестируем компоненты
    swagger_ok = test_swagger_ui(base_url)
    spec_ok = test_openapi_spec(base_url)
    endpoints_ok = test_api_endpoints(base_url)
    chat_ok = test_chat_api(base_url)

    # Итоговый результат
    print("\n" + "=" * 50)
    print("📋 Итоговый отчет:")
    print(f"   Swagger UI: {'✅' if swagger_ok else '❌'}")
    print(f"   OpenAPI Spec: {'✅' if spec_ok else '❌'}")
    print(f"   API Endpoints: {'✅' if endpoints_ok else '❌'}")
    print(f"   Chat API: {'✅' if chat_ok else '❌'}")

    all_ok = swagger_ok and spec_ok and endpoints_ok and chat_ok

    if all_ok:
        print("\n🎉 Все тесты пройдены! API документация работает корректно.")
        print(f"🌐 Откройте в браузере: {base_url}/apidocs")
        sys.exit(0)
    else:
        print("\n⚠️  Некоторые тесты не пройдены. Проверьте настройки сервера.")
        sys.exit(1)


if __name__ == "__main__":
    main()
