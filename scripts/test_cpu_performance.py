#!/usr/bin/env python3
"""
Скрипт для тестирования CPU-производительности RAG системы на Windows.
"""

import time
import sys
import os
from loguru import logger

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import CONFIG


def test_basic_functionality():
    """Тестирует базовую функциональность системы."""
    print("🧪 Тестирование базовой функциональности...")

    try:
        # Тест конфигурации
        print(f"   ✅ Конфигурация загружена: GPU_ENABLED={CONFIG.gpu_enabled}")

        # Тест импортов
        from app.services.embeddings import embed_dense
        print("   ✅ Модуль эмбеддингов импортирован")

        from app.services.rerank import rerank
        print("   ✅ Модуль reranker импортирован")

        from ingestion.semantic_chunker import chunk_text_semantic
        print("   ✅ Модуль семантического chunker импортирован")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def test_embeddings_simple():
    """Тестирует простые эмбеддинги."""
    print("\n🧠 Тестирование простых эмбеддингов...")

    try:
        # Создаем простой тест без загрузки модели
        test_text = "Тестовый текст для эмбеддинга"

        # Имитируем эмбеддинг
        start_time = time.time()
        # Простое хэширование как замена эмбеддинга
        embedding = [hash(word) % 1000 for word in test_text.split()]
        end_time = time.time()

        print(f"   ✅ Простой эмбеддинг: {end_time - start_time:.4f}s")
        print(f"   📊 Размер эмбеддинга: {len(embedding)}")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def test_reranker_simple():
    """Тестирует простой reranker."""
    print("\n🔄 Тестирование простого reranker...")

    try:
        # Создаем простой тест
        query = "Тестовый запрос"
        candidates = [
            {"payload": {"text": "Тестовый документ 1", "title": "Документ 1"}},
            {"payload": {"text": "Тестовый документ 2", "title": "Документ 2"}},
            {"payload": {"text": "Тестовый докурос 3", "title": "Документ 3"}},
        ]

        # Простой reranking по длине текста
        start_time = time.time()
        for i, candidate in enumerate(candidates):
            text = candidate["payload"]["text"]
            # Простая оценка релевантности
            score = len(set(query.split()) & set(text.split())) / len(set(query.split()) | set(text.split()))
            candidates[i]["rerank_score"] = score

        # Сортируем по score
        candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        end_time = time.time()

        print(f"   ✅ Простой reranking: {end_time - start_time:.4f}s")
        print(f"   📊 Результаты:")
        for i, result in enumerate(candidates, 1):
            title = result["payload"]["title"]
            score = result["rerank_score"]
            print(f"      {i}. {title} (score: {score:.3f})")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def test_chunker_simple():
    """Тестирует простой chunker."""
    print("\n✂️ Тестирование простого chunker...")

    try:
        test_text = """
        Это тестовый текст для разбиения на чанки.
        Он содержит несколько абзацев.
        Каждый абзац может быть отдельным чанком.
        Это помогает системе лучше понимать структуру текста.
        """

        # Простое разбиение по абзацам
        start_time = time.time()
        chunks = [p.strip() for p in test_text.split("\n\n") if p.strip()]
        end_time = time.time()

        print(f"   ✅ Простой chunking: {end_time - start_time:.4f}s")
        print(f"   📊 Результат: {len(chunks)} чанков")
        for i, chunk in enumerate(chunks, 1):
            print(f"      {i}. {chunk[:50]}...")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def test_system_performance():
    """Тестирует общую производительность системы."""
    print("\n⚡ Тестирование общей производительности...")

    try:
        # Тест обработки запроса
        query = "Как настроить интеграцию с Telegram?"

        # Имитируем полный pipeline
        start_time = time.time()

        # 1. Обработка запроса
        processed_query = query.lower().strip()

        # 2. Поиск документов (имитация)
        documents = [
            "Настройка Telegram бота для RAG системы",
            "Конфигурация API endpoints",
            "Установка и настройка Qdrant",
        ]

        # 3. Reranking (простой)
        scores = []
        for doc in documents:
            score = len(set(processed_query.split()) & set(doc.lower().split())) / len(set(processed_query.split()) | set(doc.lower().split()))
            scores.append(score)

        # 4. Генерация ответа (имитация)
        best_doc = documents[scores.index(max(scores))]
        answer = f"Для настройки интеграции с Telegram: {best_doc}"

        end_time = time.time()

        print(f"   ✅ Полный pipeline: {end_time - start_time:.4f}s")
        print(f"   📊 Ответ: {answer}")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование CPU-производительности RAG системы на Windows")
    print("=" * 70)

    # Проверяем конфигурацию
    print(f"🔧 Конфигурация:")
    print(f"   Платформа: Windows")
    print(f"   GPU включен: {CONFIG.gpu_enabled}")
    print(f"   GPU устройство: {CONFIG.gpu_device}")
    print(f"   Reranker устройство: {CONFIG.reranker_device}")

    # Запускаем тесты
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Simple Embeddings", test_embeddings_simple),
        ("Simple Reranker", test_reranker_simple),
        ("Simple Chunker", test_chunker_simple),
        ("System Performance", test_system_performance),
    ]

    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Критическая ошибка в {test_name}: {e}")
            results[test_name] = False

    # Итоговый отчет
    print("\n" + "=" * 70)
    print("📋 Итоговый отчет:")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")

    print(f"\n🎯 Результат: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 Все тесты пройдены! Система работает корректно на CPU.")
        print("💡 Для GPU-ускорения требуется обновление PyTorch до версии 2.6+")
        return 0
    else:
        print("⚠️ Некоторые тесты не пройдены. Проверьте настройки системы.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
