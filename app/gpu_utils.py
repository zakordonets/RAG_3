"""
Утилиты для работы с GPU (AMD Radeon RX 6700 XT).
Поддерживает как ROCm (Linux) так и DirectML (Windows).
"""
from __future__ import annotations

import os
import platform
import torch
from typing import Optional, Union
from loguru import logger
from app.config import CONFIG

# Определяем платформу и импортируем соответствующие утилиты
if platform.system() == "Windows":
    try:
        from app.gpu_utils_windows import (
            get_device as get_device_windows,
            optimize_for_gpu as optimize_for_gpu_windows,
            get_gpu_memory_info as get_gpu_memory_info_windows,
            clear_gpu_cache as clear_gpu_cache_windows,
            set_gpu_memory_growth as set_gpu_memory_growth_windows,
            benchmark_gpu_vs_cpu as benchmark_gpu_vs_cpu_windows,
            check_directml_installation as check_gpu_installation,
            get_optimal_batch_size as get_optimal_batch_size_windows,
            get_windows_gpu_info as get_gpu_info
        )
    except ImportError:
        # Fallback на CPU-оптимизированную версию
        from app.gpu_utils_windows_fallback import (
            get_device as get_device_windows,
            optimize_for_gpu as optimize_for_gpu_windows,
            get_gpu_memory_info as get_gpu_memory_info_windows,
            clear_gpu_cache as clear_gpu_cache_windows,
            set_gpu_memory_growth as set_gpu_memory_growth_windows,
            benchmark_gpu_vs_cpu as benchmark_gpu_vs_cpu_windows,
            check_gpu_installation,
            get_optimal_batch_size as get_optimal_batch_size_windows,
            get_gpu_info
        )
else:
    # Linux/ROCm функции
    def check_gpu_installation():
        """Проверяет установку ROCm."""
        try:
            if not torch.cuda.is_available():
                logger.error("CUDA/ROCm недоступен")
                return False

            device_count = torch.cuda.device_count()
            if device_count == 0:
                logger.error("GPU устройства не обнаружены")
                return False

            device_name = torch.cuda.get_device_name(0)
            if "AMD" in device_name or "Radeon" in device_name:
                logger.info(f"AMD GPU обнаружен: {device_name}")
                return True
            else:
                logger.warning(f"Неожиданное GPU устройство: {device_name}")
                return True
        except Exception as e:
            logger.error(f"Ошибка проверки ROCm: {e}")
            return False

    def get_gpu_info():
        """Получает информацию о GPU."""
        if not torch.cuda.is_available():
            return {"available": False}

        device_count = torch.cuda.device_count()
        devices = []
        for i in range(device_count):
            devices.append({
                "id": i,
                "name": torch.cuda.get_device_name(i),
                "available": True
            })

        return {"available": True, "devices": devices}


def get_device() -> str:
    """
    Возвращает доступное устройство для вычислений.

    Returns:
        'cuda'/'dml' если GPU доступен, иначе 'cpu'
    """
    if platform.system() == "Windows":
        return get_device_windows()
    else:
        # Linux/ROCm
        if not CONFIG.gpu_enabled:
            return "cpu"

        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            if device_count > 0:
                device_id = min(CONFIG.gpu_device, device_count - 1)
                device_name = torch.cuda.get_device_name(device_id)
                logger.info(f"GPU доступен: {device_name} (устройство {device_id})")
                return f"cuda:{device_id}"
            else:
                logger.warning("GPU не обнаружен")
                return "cpu"
        else:
            logger.warning("CUDA недоступен, используем CPU")
            return "cpu"


def optimize_for_gpu(model: torch.nn.Module, device: str) -> torch.nn.Module:
    """
    Оптимизирует модель для GPU.

    Args:
        model: PyTorch модель
        device: Устройство для размещения модели

    Returns:
        Оптимизированная модель
    """
    if device.startswith("cuda"):
        # Перемещаем модель на GPU
        model = model.to(device)

        # Оптимизируем для инференса
        model.eval()

        # Включаем оптимизации
        if hasattr(torch, 'compile'):
            try:
                model = torch.compile(model, mode="reduce-overhead")
                logger.info("Модель скомпилирована с torch.compile")
            except Exception as e:
                logger.warning(f"Не удалось скомпилировать модель: {e}")

        # Настраиваем память GPU
        if CONFIG.gpu_memory_fraction < 1.0:
            torch.cuda.set_per_process_memory_fraction(CONFIG.gpu_memory_fraction)
            logger.info(f"Ограничена память GPU до {CONFIG.gpu_memory_fraction * 100}%")

    return model


def get_gpu_memory_info() -> dict:
    """
    Возвращает информацию о памяти GPU.

    Returns:
        Словарь с информацией о памяти
    """
    if not torch.cuda.is_available():
        return {"available": False}

    device = get_device()
    if not device.startswith("cuda"):
        return {"available": False}

    device_id = int(device.split(":")[1]) if ":" in device else 0

    memory_allocated = torch.cuda.memory_allocated(device_id) / 1024**3  # GB
    memory_reserved = torch.cuda.memory_reserved(device_id) / 1024**3    # GB
    memory_total = torch.cuda.get_device_properties(device_id).total_memory / 1024**3  # GB

    return {
        "available": True,
        "device_id": device_id,
        "device_name": torch.cuda.get_device_name(device_id),
        "memory_allocated_gb": round(memory_allocated, 2),
        "memory_reserved_gb": round(memory_reserved, 2),
        "memory_total_gb": round(memory_total, 2),
        "memory_free_gb": round(memory_total - memory_reserved, 2),
        "memory_usage_percent": round((memory_reserved / memory_total) * 100, 1)
    }


def clear_gpu_cache():
    """Очищает кэш GPU."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.debug("Кэш GPU очищен")


def set_gpu_memory_growth():
    """Включает динамическое выделение памяти GPU."""
    if torch.cuda.is_available():
        # Для PyTorch это делается автоматически
        logger.info("Динамическое выделение памяти GPU включено")


def benchmark_gpu_vs_cpu(model, input_data, device: str, iterations: int = 10) -> dict:
    """
    Сравнивает производительность GPU и CPU.

    Args:
        model: Модель для тестирования
        input_data: Входные данные
        device: Устройство для тестирования
        iterations: Количество итераций

    Returns:
        Словарь с результатами бенчмарка
    """
    import time

    model = model.to(device)
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
            torch.cuda.synchronize() if device.startswith("cuda") else None
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


def check_rocm_installation() -> bool:
    """
    Проверяет установку ROCm.

    Returns:
        True если ROCm установлен корректно
    """
    try:
        # Проверяем доступность CUDA (ROCm предоставляет CUDA API)
        if not torch.cuda.is_available():
            logger.error("CUDA/ROCm недоступен")
            return False

        # Проверяем количество устройств
        device_count = torch.cuda.device_count()
        if device_count == 0:
            logger.error("GPU устройства не обнаружены")
            return False

        # Проверяем имя устройства
        device_name = torch.cuda.get_device_name(0)
        if "AMD" in device_name or "Radeon" in device_name:
            logger.info(f"AMD GPU обнаружен: {device_name}")
            return True
        else:
            logger.warning(f"Неожиданное GPU устройство: {device_name}")
            return True  # Все равно может работать

    except Exception as e:
        logger.error(f"Ошибка проверки ROCm: {e}")
        return False


def get_optimal_batch_size(model, input_shape, device: str, max_memory_gb: float = 8.0) -> int:
    """
    Определяет оптимальный размер батча для GPU.

    Args:
        model: Модель для тестирования
        input_shape: Форма входных данных
        device: Устройство
        max_memory_gb: Максимальное использование памяти в GB

    Returns:
        Оптимальный размер батча
    """
    if not device.startswith("cuda"):
        return 1  # Для CPU используем размер 1

    model = model.to(device)
    model.eval()

    batch_size = 1
    max_batch_size = 1

    try:
        while True:
            try:
                # Создаем тестовый батч
                test_input = torch.randn(batch_size, *input_shape).to(device)

                # Тестируем forward pass
                with torch.no_grad():
                    _ = model(test_input)

                # Если успешно, увеличиваем размер батча
                max_batch_size = batch_size
                batch_size *= 2

                # Проверяем использование памяти
                memory_used = torch.cuda.memory_allocated() / 1024**3
                if memory_used > max_memory_gb:
                    break

            except RuntimeError as e:
                if "out of memory" in str(e):
                    break
                else:
                    raise e

    except Exception as e:
        logger.warning(f"Ошибка определения размера батча: {e}")

    # Очищаем память
    torch.cuda.empty_cache()

    logger.info(f"Оптимальный размер батча для {device}: {max_batch_size}")
    return max_batch_size
