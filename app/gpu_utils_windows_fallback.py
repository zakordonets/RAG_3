"""
Fallback утилиты для работы с GPU на Windows без DirectML.
Использует CPU для всех операций, но с оптимизациями.
"""
from __future__ import annotations

import os
import torch
from typing import Optional, Union
from loguru import logger
from app.config import CONFIG


def get_device() -> str:
    """
    Возвращает доступное устройство для вычислений на Windows.

    Returns:
        'cpu' (fallback для Windows без DirectML)
    """
    if not CONFIG.gpu_enabled:
        return "cpu"

    # Проверяем, есть ли DirectML
    try:
        import torch_directml
        if torch_directml.is_available():
            device_count = torch_directml.device_count()
            if device_count > 0:
                device_id = min(CONFIG.gpu_device, device_count - 1)
                device_name = torch_directml.device_name(device_id)
                logger.info(f"DirectML доступен: {device_name} (устройство {device_id})")
                return "dml"
    except ImportError:
        pass

    logger.warning("DirectML недоступен, используем CPU с оптимизациями")
    return "cpu"


def optimize_for_gpu(model: torch.nn.Module, device: str) -> torch.nn.Module:
    """
    Оптимизирует модель для CPU на Windows.

    Args:
        model: PyTorch модель
        device: Устройство для размещения модели

    Returns:
        Оптимизированная модель
    """
    if device == "dml":
        # Пытаемся использовать DirectML
        try:
            import torch_directml
            dml_device = torch_directml.device()
            model = model.to(dml_device)
            model.eval()
            logger.info(f"Модель оптимизирована для DirectML: {dml_device}")
            return model
        except Exception as e:
            logger.warning(f"DirectML недоступен: {e}, используем CPU")

    # CPU оптимизации
    model = model.to("cpu")
    model.eval()

    # Оптимизируем для CPU
    try:
        if hasattr(torch, 'compile'):
            model = torch.compile(model, mode="reduce-overhead")
            logger.info("Модель скомпилирована с torch.compile для CPU")
    except Exception as e:
        logger.warning(f"Не удалось скомпилировать модель: {e}")

    logger.info("Модель оптимизирована для CPU")
    return model


def get_gpu_memory_info() -> dict:
    """
    Возвращает информацию о памяти GPU на Windows.

    Returns:
        Словарь с информацией о памяти
    """
    try:
        import torch_directml
        if torch_directml.is_available():
            device_count = torch_directml.device_count()
            if device_count > 0:
                device_id = CONFIG.gpu_device
                device_name = torch_directml.device_name(device_id)

                return {
                    "available": True,
                    "device_id": device_id,
                    "device_name": device_name,
                    "memory_allocated_gb": 0.0,
                    "memory_reserved_gb": 0.0,
                    "memory_total_gb": 0.0,
                    "memory_free_gb": 0.0,
                    "memory_usage_percent": 0.0,
                    "note": "DirectML не предоставляет детальную информацию о памяти"
                }
    except ImportError:
        pass

    return {"available": False, "note": "DirectML недоступен"}


def clear_gpu_cache():
    """Очищает кэш GPU."""
    try:
        import torch_directml
        if torch_directml.is_available():
            logger.debug("DirectML автоматически управляет памятью")
    except ImportError:
        logger.debug("DirectML недоступен, кэш не очищается")


def set_gpu_memory_growth():
    """Включает динамическое выделение памяти GPU."""
    try:
        import torch_directml
        if torch_directml.is_available():
            logger.info("DirectML автоматически управляет памятью GPU")
    except ImportError:
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
        # Пытаемся использовать DirectML
        try:
            import torch_directml
            dml_device = torch_directml.device()
            model = model.to(dml_device)
            input_data = input_data.to(dml_device)
        except Exception as e:
            logger.warning(f"DirectML недоступен: {e}, используем CPU")
            device = "cpu"
            model = model.to("cpu")
            input_data = input_data.to("cpu")
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


def check_gpu_installation() -> bool:
    """
    Проверяет установку GPU на Windows.

    Returns:
        True если GPU доступен
    """
    try:
        import torch_directml
        if torch_directml.is_available():
            device_count = torch_directml.device_count()
            if device_count > 0:
                device_name = torch_directml.device_name(0)
                if "AMD" in device_name or "Radeon" in device_name:
                    logger.info(f"AMD GPU обнаружен: {device_name}")
                    return True
                else:
                    logger.warning(f"Неожиданное GPU устройство: {device_name}")
                    return True
            else:
                logger.error("GPU устройства не обнаружены")
                return False
        else:
            logger.error("DirectML недоступен")
            return False
    except ImportError:
        logger.error("DirectML не установлен")
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки GPU: {e}")
        return False


def get_optimal_batch_size(model, input_shape, device: str, max_memory_gb: float = 8.0) -> int:
    """
    Определяет оптимальный размер батча для Windows.

    Args:
        model: Модель для тестирования
        input_shape: Форма входных данных
        device: Устройство
        max_memory_gb: Максимальное использование памяти в GB

    Returns:
        Оптимальный размер батча
    """
    if device == "dml":
        # Пытаемся использовать DirectML
        try:
            import torch_directml
            dml_device = torch_directml.device()
            model = model.to(dml_device)
        except Exception as e:
            logger.warning(f"DirectML недоступен: {e}, используем CPU")
            device = "cpu"
            model = model.to("cpu")
    else:
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

                # Разумный лимит
                if batch_size > 64:
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


def get_gpu_info() -> dict:
    """
    Получает информацию о GPU на Windows.

    Returns:
        Словарь с информацией о GPU
    """
    info = {
        "directml_available": False,
        "devices": []
    }

    try:
        import torch_directml
        if torch_directml.is_available():
            info["directml_available"] = True
            device_count = torch_directml.device_count()
            for i in range(device_count):
                device_info = {
                    "id": i,
                    "name": torch_directml.device_name(i),
                    "available": True
                }
                info["devices"].append(device_info)
    except ImportError:
        pass

    return info
