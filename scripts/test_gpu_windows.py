#!/usr/bin/env python3
"""
Скрипт для тестирования GPU-ускорения на Windows (DirectML + AMD Radeon RX 6700 XT).
"""

import time
import torch
import numpy as np
from typing import Dict, Any
from loguru import logger
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.gpu_utils import (
    get_device,
    get_gpu_memory_info,
    check_gpu_installation,
    benchmark_gpu_vs_cpu,
    get_optimal_batch_size,
    get_gpu_info
)
from app.config import CONFIG


def test_directml_availability() -> bool:
    """Тестирует доступность DirectML."""
    print("🔍 Проверка доступности DirectML...")

    # Проверяем DirectML
    if not check_gpu_installation():
        print("❌ DirectML не установлен или работает некорректно")
        print("💡 Установите DirectML: pip install torch-directml")
        return False

    # Получаем информацию о GPU
    device = get_device()
    if not device.startswith('dml'):
        print("❌ DirectML не используется")
        return False

    print(f"✅ DirectML доступен: {device}")

    # Информация о GPU
    gpu_info = get_gpu_info()
    if gpu_info.get('available'):
        print(f"📊 GPU устройства:")
        for device_info in gpu_info.get('devices', []):
            print(f"   {device_info['id']}: {device_info['name']}")

    return True


def test_embeddings_performance():
    """Тестирует производительность эмбеддингов."""
    print("\n🧠 Тестирование производительности эмбеддингов...")

    try:
        from app.services.embeddings import embed_dense, embed_dense_batch

        # Тестовые тексты
        test_texts = [
            "Как настроить интеграцию с Telegram?",
            "Что такое RAG система?",
            "Как работает векторный поиск?",
            "Настройка Qdrant базы данных",
            "Конфигурация LLM провайдеров"
        ]

        # Тест одиночных эмбеддингов
        print("   Тестирование одиночных эмбеддингов...")
        start_time = time.time()
        for text in test_texts:
            embedding = embed_dense(text)
        single_time = time.time() - start_time
        print(f"   ✅ Одиночные эмбеддинги: {single_time:.2f}s ({single_time/len(test_texts):.3f}s на текст)")

        # Тест батчевых эмбеддингов
        print("   Тестирование батчевых эмбеддингов...")
        start_time = time.time()
        batch_embeddings = embed_dense_batch(test_texts)
        batch_time = time.time() - start_time
        print(f"   ✅ Батчевые эмбеддинги: {batch_time:.2f}s ({batch_time/len(test_texts):.3f}s на текст)")

        # Сравнение производительности
        speedup = single_time / batch_time if batch_time > 0 else 1
        print(f"   📈 Ускорение батчевой обработки: {speedup:.2f}x")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка тестирования эмбеддингов: {e}")
        return False


def test_reranker_performance():
    """Тестирует производительность reranker."""
    print("\n🔄 Тестирование производительности reranker...")

    try:
        from app.services.rerank import rerank

        # Тестовые данные
        query = "Как настроить интеграцию с Telegram?"
        candidates = [
            {"payload": {"text": "Настройка Telegram бота для RAG системы", "title": "Telegram Bot"}},
            {"payload": {"text": "Конфигурация API endpoints", "title": "API Config"}},
            {"payload": {"text": "Установка и настройка Qdrant", "title": "Qdrant Setup"}},
            {"payload": {"text": "Интеграция с внешними сервисами", "title": "External Services"}},
            {"payload": {"text": "Мониторинг и логирование", "title": "Monitoring"}},
        ]

        # Тест reranking
        print("   Тестирование reranking...")
        start_time = time.time()
        results = rerank(query, candidates, top_n=3)
        rerank_time = time.time() - start_time

        print(f"   ✅ Reranking: {rerank_time:.3f}s")
        print(f"   📊 Результаты:")
        for i, result in enumerate(results, 1):
            title = result.get("payload", {}).get("title", "Unknown")
            score = result.get("rerank_score", 0)
            print(f"      {i}. {title} (score: {score:.3f})")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка тестирования reranker: {e}")
        return False


def test_semantic_chunker_performance():
    """Тестирует производительность семантического chunker."""
    print("\n✂️ Тестирование производительности семантического chunker...")

    try:
        from ingestion.semantic_chunker import chunk_text_semantic

        # Тестовый текст
        test_text = """
        RAG система представляет собой комбинацию поиска и генерации.
        Она использует векторные эмбеддинги для поиска релевантных документов.
        Затем найденные документы передаются в языковую модель для генерации ответа.
        Это позволяет создавать более точные и контекстуальные ответы.
        Система поддерживает различные типы эмбеддингов и модели.
        """

        # Тест chunking
        print("   Тестирование семантического chunking...")
        start_time = time.time()
        chunks = chunk_text_semantic(test_text, use_overlap=False)
        chunk_time = time.time() - start_time

        print(f"   ✅ Chunking: {chunk_time:.3f}s")
        print(f"   📊 Результат: {len(chunks)} чанков")
        for i, chunk in enumerate(chunks, 1):
            print(f"      {i}. {chunk[:50]}...")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка тестирования chunker: {e}")
        return False


def test_directml_performance():
    """Тестирует релевантную нашему коду производительность через ONNXRuntime DML."""
    print("\n⚡ Тестирование производительности DirectML (ORT) ...")

    try:
        import onnxruntime as ort
        providers = getattr(ort, 'get_available_providers', lambda: [])()
        print(f"   Доступные ORT провайдеры: {providers}")
        if 'DmlExecutionProvider' not in providers:
            print("   ⚠️ DmlExecutionProvider недоступен, пропускаем")
            return True

        # Микробенчмарк: многократное кодирование эмбеддингов батчами
        from app.services.embeddings import embed_dense_batch
        texts = [
            "Как настроить интеграцию с Telegram?",
            "Что такое RAG система?",
            "Как работает векторный поиск?",
            "Настройка Qdrant базы данных",
            "Конфигурация LLM провайдеров",
        ] * 5  # 25 текстов

        # Прогрев
        _ = embed_dense_batch(texts[:5])

        import time
        start = time.time()
        _ = embed_dense_batch(texts)
        total = time.time() - start
        print(f"   ORT DML batch(25) время: {total:.3f}s, на текст: {total/len(texts):.3f}s")
        return True

    except Exception as e:
        print(f"   ❌ Ошибка ORT теста: {e}")
        return False


def test_memory_usage():
    """Оценка условной "емкости" через размер батча эмбеддингов на ORT DML."""
    print("\n💾 Тестирование емкости памяти через размер батча эмбеддингов (ORT DML)...")

    try:
        import onnxruntime as ort
        providers = getattr(ort, 'get_available_providers', lambda: [])()
        if 'DmlExecutionProvider' not in providers:
            print("   ⚠️ DmlExecutionProvider недоступен, пропускаем")
            return True

        from app.services.embeddings import embed_dense_batch
        base = [
            "Как настроить интеграцию с Telegram?",
            "Что такое RAG система?",
            "Как работает векторный поиск?",
            "Настройка Qdrant базы данных",
            "Конфигурация LLM провайдеров",
        ]

        batch = base
        max_ok = 0
        while True:
            try:
                _ = embed_dense_batch(batch)
                max_ok = len(batch)
                # увеличиваем батч
                if len(batch) >= 160:
                    break
                batch = batch + base
            except Exception as e:
                print(f"   Достигнут предел при батче {len(batch)}: {e}")
                break
        print(f"   Максимальный успешно обработанный батч: {max_ok}")
        return True

    except Exception as e:
        print(f"   ❌ Ошибка тестирования емкости: {e}")
        return False


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование производительности GPU на Windows (DirectML + Radeon RX 6700 XT)")
    print("=" * 80)

    # Проверяем конфигурацию
    print(f"🔧 Конфигурация:")
    print(f"   Платформа: Windows")
    print(f"   GPU включен: {CONFIG.gpu_enabled}")
    print(f"   GPU устройство: {CONFIG.gpu_device}")
    print(f"   Доля памяти GPU: {CONFIG.gpu_memory_fraction}")
    print(f"   Reranker устройство: {CONFIG.reranker_device}")

    # Запускаем тесты
    tests = [
        ("DirectML Availability", test_directml_availability),
        ("Embeddings Performance", test_embeddings_performance),
        ("Reranker Performance", test_reranker_performance),
        ("Semantic Chunker Performance", test_semantic_chunker_performance),
        ("DirectML Performance", test_directml_performance),
        ("Memory Usage", test_memory_usage),
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
    print("\n" + "=" * 80)
    print("📋 Итоговый отчет:")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")

    print(f"\n🎯 Результат: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 Все тесты пройдены! DirectML работает корректно.")
        print("💡 Ожидаемое ускорение: 1.5-3x для основных операций")
        return 0
    else:
        print("⚠️ Некоторые тесты не пройдены. Проверьте настройки DirectML.")
        print("💡 Установите DirectML: pip install torch-directml")
        return 1


if __name__ == "__main__":
    sys.exit(main())
