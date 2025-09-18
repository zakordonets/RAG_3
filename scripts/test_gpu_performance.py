#!/usr/bin/env python3
"""
Скрипт для тестирования производительности GPU (Radeon RX 6700 XT).
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
    check_rocm_installation,
    benchmark_gpu_vs_cpu,
    get_optimal_batch_size
)
from app.config import CONFIG


def test_gpu_availability() -> bool:
    """Тестирует доступность GPU."""
    print("🔍 Проверка доступности GPU...")

    # Проверяем ROCm
    if not check_rocm_installation():
        print("❌ ROCm не установлен или работает некорректно")
        return False

    # Проверяем PyTorch
    if not torch.cuda.is_available():
        print("❌ CUDA/ROCm недоступен в PyTorch")
        return False

    # Получаем информацию о GPU
    device = get_device()
    if not device.startswith('cuda'):
        print("❌ GPU не используется")
        return False

    print(f"✅ GPU доступен: {device}")

    # Информация о памяти
    memory_info = get_gpu_memory_info()
    if memory_info['available']:
        print(f"📊 GPU память:")
        print(f"   Устройство: {memory_info['device_name']}")
        print(f"   Всего: {memory_info['memory_total_gb']} GB")
        print(f"   Свободно: {memory_info['memory_free_gb']} GB")
        print(f"   Использовано: {memory_info['memory_usage_percent']}%")

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


def test_memory_usage():
    """Тестирует использование памяти GPU."""
    print("\n💾 Тестирование использования памяти GPU...")

    try:
        device = get_device()
        if not device.startswith('cuda'):
            print("   ⚠️ GPU не используется, пропускаем тест памяти")
            return True

        # Получаем начальную информацию о памяти
        initial_memory = get_gpu_memory_info()
        print(f"   Начальная память: {initial_memory['memory_allocated_gb']:.2f} GB")

        # Создаем тестовые тензоры
        print("   Создание тестовых тензоров...")
        tensors = []
        for i in range(10):
            tensor = torch.randn(1000, 1000).to(device)
            tensors.append(tensor)

        # Проверяем память после создания тензоров
        after_memory = get_gpu_memory_info()
        print(f"   Память после создания тензоров: {after_memory['memory_allocated_gb']:.2f} GB")
        print(f"   Использовано: {after_memory['memory_allocated_gb'] - initial_memory['memory_allocated_gb']:.2f} GB")

        # Очищаем память
        del tensors
        torch.cuda.empty_cache()

        # Проверяем память после очистки
        final_memory = get_gpu_memory_info()
        print(f"   Память после очистки: {final_memory['memory_allocated_gb']:.2f} GB")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка тестирования памяти: {e}")
        return False


def benchmark_components():
    """Сравнивает производительность компонентов."""
    print("\n⚡ Сравнение производительности компонентов...")

    try:
        device = get_device()
        if not device.startswith('cuda'):
            print("   ⚠️ GPU не используется, пропускаем бенчмарк")
            return True

        # Создаем тестовую модель
        model = torch.nn.Sequential(
            torch.nn.Linear(1000, 512),
            torch.nn.ReLU(),
            torch.nn.Linear(512, 256),
            torch.nn.ReLU(),
            torch.nn.Linear(256, 128)
        )

        # Тестовые данные
        input_data = torch.randn(32, 1000)

        # Бенчмарк GPU
        gpu_results = benchmark_gpu_vs_cpu(model, input_data, device, iterations=5)
        print(f"   GPU результаты: {gpu_results}")

        # Бенчмарк CPU
        cpu_results = benchmark_gpu_vs_cpu(model, input_data, "cpu", iterations=5)
        print(f"   CPU результаты: {cpu_results}")

        # Сравнение
        speedup = cpu_results['avg_time_ms'] / gpu_results['avg_time_ms']
        print(f"   🚀 Ускорение GPU: {speedup:.2f}x")

        return True

    except Exception as e:
        print(f"   ❌ Ошибка бенчмарка: {e}")
        return False


def main():
    """Основная функция тестирования."""
    print("🚀 Тестирование производительности GPU (Radeon RX 6700 XT)")
    print("=" * 60)

    # Проверяем конфигурацию
    print(f"🔧 Конфигурация:")
    print(f"   GPU включен: {CONFIG.gpu_enabled}")
    print(f"   GPU устройство: {CONFIG.gpu_device}")
    print(f"   Доля памяти GPU: {CONFIG.gpu_memory_fraction}")
    print(f"   Reranker устройство: {CONFIG.reranker_device}")

    # Запускаем тесты
    tests = [
        ("GPU Availability", test_gpu_availability),
        ("Embeddings Performance", test_embeddings_performance),
        ("Reranker Performance", test_reranker_performance),
        ("Semantic Chunker Performance", test_semantic_chunker_performance),
        ("Memory Usage", test_memory_usage),
        ("Component Benchmark", benchmark_components),
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
    print("\n" + "=" * 60)
    print("📋 Итоговый отчет:")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")

    print(f"\n🎯 Результат: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 Все тесты пройдены! GPU работает корректно.")
        return 0
    else:
        print("⚠️ Некоторые тесты не пройдены. Проверьте настройки GPU.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
