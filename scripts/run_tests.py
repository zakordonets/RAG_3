#!/usr/bin/env python3
"""
Скрипт для запуска автотестов с различными конфигурациями
"""

import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, description):
    """Запуск команды с выводом"""
    print(f"\n🔧 {description}")
    print(f"Команда: {' '.join(cmd)}")
    print("-" * 60)

    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} - УСПЕШНО")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ОШИБКА (код {e.returncode})")
        return False
    except Exception as e:
        print(f"❌ {description} - ИСКЛЮЧЕНИЕ: {e}")
        return False

def check_services():
    """Проверка доступности сервисов"""
    print("🔍 Проверка сервисов...")

    services = [
        ("Redis", "python -c \"import redis; r=redis.from_url('redis://localhost:6379'); print('OK' if r.ping() else 'ERROR')\""),
        ("Qdrant", "python -c \"from qdrant_client import QdrantClient; c=QdrantClient('localhost'); print('OK' if c.get_collections() is not None else 'ERROR')\"")
    ]

    all_ok = True
    for service_name, cmd in services:
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            status = "✅" if result.returncode == 0 else "❌"
            print(f"  {status} {service_name}: {result.stdout.strip()}")
            if result.returncode != 0:
                all_ok = False
        except Exception as e:
            print(f"  ❌ {service_name}: Ошибка - {e}")
            all_ok = False

    return all_ok

def main():
    parser = argparse.ArgumentParser(description="Запуск автотестов")
    parser.add_argument("--type", choices=["unit", "integration", "e2e", "slow", "all", "fast"],
                       default="fast", help="Тип тестов для запуска")
    parser.add_argument("--coverage", action="store_true", help="Включить покрытие кода")
    parser.add_argument("--parallel", action="store_true", help="Запустить тесты параллельно")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument("--check-services", action="store_true", help="Проверить сервисы перед тестами")
    parser.add_argument("--lint", action="store_true", help="Запустить линтеры")
    parser.add_argument("--format", action="store_true", help="Форматировать код")

    args = parser.parse_args()

    print("🚀 ЗАПУСК АВТОТЕСТОВ")
    print("=" * 60)

    # Проверка сервисов
    if args.check_services:
        if not check_services():
            print("❌ Некоторые сервисы недоступны. Запустите их перед тестами.")
            return 1
        print("✅ Все сервисы доступны")

    # Форматирование кода
    if args.format:
        run_command(["python", "-m", "black", "app/", "tests/", "scripts/", "--line-length=120"],
                   "Форматирование кода с black")
        run_command(["python", "-m", "isort", "app/", "tests/", "scripts/"],
                   "Сортировка импортов с isort")

    # Линтинг
    if args.lint:
        run_command(["python", "-m", "flake8", "app/", "tests/", "scripts/",
                    "--max-line-length=120", "--ignore=E203,W503"],
                   "Линтинг с flake8")
        run_command(["python", "-m", "mypy", "app/", "--ignore-missing-imports"],
                   "Проверка типов с mypy")

    # Подготовка команды pytest
    cmd = ["python", "-m", "pytest", "tests/"]

    # Выбор типа тестов
    if args.type == "unit":
        cmd.extend(["-m", "not slow and not integration"])
    elif args.type == "integration":
        cmd.extend(["-m", "integration"])
    elif args.type == "e2e":
        cmd.extend(["-m", "e2e"])
    elif args.type == "slow":
        cmd.extend(["-m", "slow"])
    elif args.type == "fast":
        cmd.extend(["-m", "not slow"])
    # "all" - без дополнительных фильтров

    # Покрытие кода
    if args.coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])

    # Параллельное выполнение
    if args.parallel:
        cmd.extend(["-n", "auto"])

    # Подробный вывод
    if args.verbose:
        cmd.append("-v")

    # Запуск тестов
    success = run_command(cmd, f"Запуск тестов ({args.type})")

    if success:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        if args.coverage:
            print("📊 Отчет о покрытии сохранен в htmlcov/index.html")
        return 0
    else:
        print("\n❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        return 1

if __name__ == "__main__":
    sys.exit(main())
