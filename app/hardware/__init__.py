"""
Hardware management utilities for RAG system.
Provides unified interface for GPU/CPU operations across platforms.
"""

from .gpu_manager import (
    GPUManager,
    get_device,
    optimize_for_gpu,
    get_gpu_info,
    clear_gpu_cache,
    get_optimal_batch_size
)

__all__ = [
    'GPUManager',
    'get_device',
    'optimize_for_gpu',
    'get_gpu_info',
    'clear_gpu_cache',
    'get_optimal_batch_size'
]
