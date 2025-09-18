"""
Утилиты для работы с GPU на Windows (DirectML + AMD Radeon RX 6700 XT).
"""
from __future__ import annotations

import os
import torch
from typing import Optional, Union
from loguru import logger
from app.config import CONFIG

# Пытаемся импортировать DirectML
try:
    import torch_directml
    DIRECTML_AVAILABLE = True
except ImportError:
    DIRECTML_AVAILABLE = False
    logger.warning("DirectML не установлен. Установите: pip install torch-directml")


def get_device() -> str:
    """
    Возвращает доступное устройство для вычислений на Windows.

    Returns:
        'dml' если DirectML доступен, иначе 'cpu'
    """
    if not CONFIG.gpu_enabled:
        return "cpu"

    if DIRECTML_AVAILABLE and torch_directml.is_available():
        device_count = torch_directml.device_count()
        if device_count > 0:
            device_id = min(CONFIG.gpu_device, device_count - 1)
            device_name = torch_directml.device_name(device_id)
            logger.info(f"DirectML доступен: {device_name} (устройство {device_id})")
            return "dml"  # Возвращаем просто 'dml' без ID
        else:
            logger.warning("DirectML устройства не обнаружены")
            return "cpu"
    else:
        logger.warning("DirectML недоступен, используем CPU")
        return "cpu"


def optimize_for_gpu(model: torch.nn.Module, device: str) -> torch.nn.Module:
    """
    Оптимизирует модель для GPU на Windows.

    Args:
        model: PyTorch модель
        device: Устройство для размещения модели

    Returns:
        Оптимизированная модель
    """
    if device == "dml":
        # Перемещаем модель на DirectML
        dml_device = torch_directml.device()
        model = model.to(dml_device)

        # Оптимизируем для инференса
        model.eval()

        # Включаем оптимизации DirectML
        try:
            if hasattr(torch, 'compile'):
                model = torch.compile(model, mode="reduce-overhead")
                logger.info("Модель скомпилирована с torch.compile")
        except Exception as e:
            logger.warning(f"Не удалось скомпилировать модель: {e}")

        logger.info(f"Модель оптимизирована для DirectML: {dml_device}")

    return model


def get_gpu_memory_info() -> dict:
    """
    Возвращает информацию о памяти GPU на Windows.

    Returns:
        Словарь с информацией о памяти
    """
    if not DIRECTML_AVAILABLE or not torch_directml.is_available():
        return {"available": False}

    device = get_device()
    if device != "dml":
        return {"available": False}

    try:
        device_id = CONFIG.gpu_device

        # DirectML не предоставляет детальную информацию о памяти
        # Используем базовую информацию
        device_name = torch_directml.device_name(device_id)

        return {
            "available": True,
            "device_id": device_id,
            "device_name": device_name,
            "memory_allocated_gb": 0.0,  # DirectML не предоставляет эту информацию
            "memory_reserved_gb": 0.0,
            "memory_total_gb": 0.0,
            "memory_free_gb": 0.0,
            "memory_usage_percent": 0.0,
            "note": "DirectML не предоставляет детальную информацию о памяти"
        }
    except Exception as e:
        logger.warning(f"Ошибка получения информации о GPU: {e}")
        return {"available": False}


def clear_gpu_cache():
    """Очищает кэш GPU."""
    if DIRECTML_AVAILABLE and torch_directml.is_available():
        # DirectML автоматически управляет памятью
        logger.debug("DirectML автоматически управляет памятью")
    else:
        logger.debug("DirectML недоступен, кэш не очищается")


def set_gpu_memory_growth():
    """Включает динамическое выделение памяти GPU."""
    if DIRECTML_AVAILABLE and torch_directml.is_available():
        # DirectML автоматически управляет памятью
        logger.info("DirectML автоматически управляет памятью GPU")
    else:
        logger.info("DirectML недоступен")


def benchmark_gpu_vs_cpu(model, input_data, device: str, iterations: int = 10) -> dict:
    """
    Сравнивает производительность GPU и CPU на Windows.

    Args:
        model: Модель для тестирования
        input_data: Входные данные
        device: Устройство для тестирования
        iterations: Количество итераций

    Returns:
        Словарь с результатами бенчмарка
    """
    import time

    if device == "dml":
        # Используем DirectML устройство
        dml_device = torch_directml.device()
        model = model.to(dml_device)
        input_data = input_data.to(dml_device)
    else:
        model = model.to(device)
        input_data = input_data.to(device)

    model.eval()

    # Прогрев
    with torch.no_grad():
        for _ in range(3):
            _ = model(input_data)

    # Бенчмарк
    times = []
    with torch.no_grad():
        for _ in range(iterations):
            start = time.time()
            _ = model(input_data)
            # DirectML не требует синхронизации
            end = time.time()
            times.append(end - start)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    return {
        "device": device,
        "iterations": iterations,
        "avg_time_ms": round(avg_time * 1000, 2),
        "min_time_ms": round(min_time * 1000, 2),
        "max_time_ms": round(max_time * 1000, 2),
        "throughput_per_sec": round(1 / avg_time, 2)
    }


def check_directml_installation() -> bool:
    """
    Проверяет установку DirectML.

    Returns:
        True если DirectML установлен корректно
    """
    try:
        if not DIRECTML_AVAILABLE:
            logger.error("DirectML не установлен")
            return False

        if not torch_directml.is_available():
            logger.error("DirectML недоступен")
            return False

        # Проверяем количество устройств
        device_count = torch_directml.device_count()
        if device_count == 0:
            logger.error("DirectML устройства не обнаружены")
            return False

        # Проверяем имя устройства
        device_name = torch_directml.device_name(0)
        if "AMD" in device_name or "Radeon" in device_name:
            logger.info(f"AMD GPU обнаружен: {device_name}")
            return True
        else:
            logger.warning(f"Неожиданное GPU устройство: {device_name}")
            return True  # Все равно может работать

    except Exception as e:
        logger.error(f"Ошибка проверки DirectML: {e}")
        return False


def get_optimal_batch_size(model, input_shape, device: str, max_memory_gb: float = 8.0) -> int:
    """
    Определяет оптимальный размер батча для DirectML.

    Args:
        model: Модель для тестирования
        input_shape: Форма входных данных
        device: Устройство
        max_memory_gb: Максимальное использование памяти в GB

    Returns:
        Оптимальный размер батча
    """
    if device != "dml":
        return 1  # Для CPU используем размер 1

    dml_device = torch_directml.device()
    model = model.to(dml_device)
    model.eval()

    batch_size = 1
    max_batch_size = 1

    try:
        while True:
            try:
                # Создаем тестовый батч
                test_input = torch.randn(batch_size, *input_shape).to(dml_device)

                # Тестируем forward pass
                with torch.no_grad():
                    _ = model(test_input)

                # Если успешно, увеличиваем размер батча
                max_batch_size = batch_size
                batch_size *= 2

                # DirectML не предоставляет информацию о памяти
                # Используем эвристику
                if batch_size > 64:  # Разумный лимит
                    break

            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    break
                else:
                    raise e

    except Exception as e:
        logger.warning(f"Ошибка определения размера батча: {e}")

    logger.info(f"Оптимальный размер батча для {device}: {max_batch_size}")
    return max_batch_size


def get_windows_gpu_info() -> dict:
    """
    Получает информацию о GPU на Windows.

    Returns:
        Словарь с информацией о GPU
    """
    info = {
        "directml_available": DIRECTML_AVAILABLE,
        "devices": []
    }

    if DIRECTML_AVAILABLE and torch_directml.is_available():
        device_count = torch_directml.device_count()
        for i in range(device_count):
            device_info = {
                "id": i,
                "name": torch_directml.device_name(i),
                "available": True
            }
            info["devices"].append(device_info)

    return info
