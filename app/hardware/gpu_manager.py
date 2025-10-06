"""
Unified GPU Manager for cross-platform hardware acceleration.
Supports DirectML (Windows), ROCm (Linux), and CPU fallback.
"""

from __future__ import annotations

import os
import platform
import time
from typing import Optional, Union, Dict, Any
import torch
from loguru import logger
from app.config import CONFIG


class GPUManager:
    """
    Unified GPU manager that handles hardware acceleration across platforms.
    """

    def __init__(self):
        self.platform = platform.system()
        self.directml_available = False
        self.cuda_available = False
        self.device_info = {}

        # Initialize platform-specific capabilities
        self._detect_hardware()

    def _detect_hardware(self) -> None:
        """Detect available hardware capabilities."""
        logger.info(f"Detecting hardware on {self.platform}")

        # Check DirectML (Windows)
        if self.platform == "Windows":
            try:
                import torch_directml
                self.directml_available = torch_directml.is_available()
                if self.directml_available:
                    device_count = torch_directml.device_count()
                    if device_count > 0:
                        device_id = min(CONFIG.gpu_device, device_count - 1)
                        device_name = torch_directml.device_name(device_id)
                        self.device_info = {
                            'type': 'directml',
                            'device_id': device_id,
                            'device_name': device_name,
                            'device_count': device_count
                        }
                        logger.info(f"DirectML available: {device_name} (device {device_id})")
                    else:
                        logger.warning("DirectML devices not found")
                        self.directml_available = False
            except ImportError:
                logger.warning("DirectML not installed. Install with: pip install torch-directml")

        # Check CUDA/ROCm (Linux/Windows)
        try:
            self.cuda_available = torch.cuda.is_available()
            if self.cuda_available:
                device_count = torch.cuda.device_count()
                if device_count > 0:
                    device_id = min(CONFIG.gpu_device, device_count - 1)
                    device_name = torch.cuda.get_device_name(device_id)
                    self.device_info = {
                        'type': 'cuda',
                        'device_id': device_id,
                        'device_name': device_name,
                        'device_count': device_count
                    }
                    logger.info(f"CUDA/ROCm available: {device_name} (device {device_id})")
        except Exception as e:
            logger.warning(f"CUDA/ROCm check failed: {e}")

    def get_device(self) -> str:
        """
        Get the best available device for computations.

        Returns:
            Device string: 'dml', 'cuda', or 'cpu'
        """
        if not CONFIG.gpu_enabled:
            return "cpu"

        # Windows: Prefer DirectML
        if self.platform == "Windows" and self.directml_available:
            return "dml"

        # Linux/Windows: Use CUDA/ROCm if available
        if self.cuda_available:
            return "cuda"

        # Fallback to CPU
        logger.info("No GPU acceleration available, using CPU")
        return "cpu"

    def optimize_for_gpu(self, model: torch.nn.Module, device: str) -> torch.nn.Module:
        """
        Optimize model for the specified device.

        Args:
            model: PyTorch model to optimize
            device: Target device ('dml', 'cuda', 'cpu')

        Returns:
            Optimized model
        """
        try:
            if device == "dml" and self.directml_available:
                return self._optimize_for_directml(model)
            elif device == "cuda" and self.cuda_available:
                return self._optimize_for_cuda(model)
            else:
                return self._optimize_for_cpu(model)
        except Exception as e:
            logger.error(f"GPU optimization failed: {e}, falling back to CPU")
            return self._optimize_for_cpu(model)

    def _optimize_for_directml(self, model: torch.nn.Module) -> torch.nn.Module:
        """Optimize model for DirectML."""
        try:
            import torch_directml
            device = torch_directml.device()
            model = model.to(device)

            # Enable optimizations
            if hasattr(model, 'eval'):
                model.eval()

            # Enable mixed precision if supported
            if CONFIG.embedding_use_fp16:
                try:
                    model = model.half()
                    logger.info("DirectML model optimized with FP16")
                except Exception as e:
                    logger.warning(f"FP16 optimization failed: {e}")

            logger.info("Model optimized for DirectML")
            return model

        except Exception as e:
            logger.error(f"DirectML optimization failed: {e}")
            return self._optimize_for_cpu(model)

    def _optimize_for_cuda(self, model: torch.nn.Module) -> torch.nn.Module:
        """Optimize model for CUDA/ROCm."""
        try:
            device_id = self.device_info.get('device_id', 0)
            device = torch.device(f'cuda:{device_id}')
            model = model.to(device)

            # Enable optimizations
            if hasattr(model, 'eval'):
                model.eval()

            # Enable mixed precision if supported
            if CONFIG.embedding_use_fp16:
                try:
                    model = model.half()
                    logger.info("CUDA model optimized with FP16")
                except Exception as e:
                    logger.warning(f"FP16 optimization failed: {e}")

            # Enable cuDNN optimizations
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False

            logger.info("Model optimized for CUDA/ROCm")
            return model

        except Exception as e:
            logger.error(f"CUDA optimization failed: {e}")
            return self._optimize_for_cpu(model)

    def _optimize_for_cpu(self, model: torch.nn.Module) -> torch.nn.Module:
        """Optimize model for CPU."""
        try:
            model = model.to('cpu')

            # Enable optimizations
            if hasattr(model, 'eval'):
                model.eval()

            # Enable CPU optimizations
            torch.set_num_threads(CONFIG.embedding_batch_size)

            # Enable MKL optimizations if available
            try:
                torch.backends.mkldnn.enabled = True
            except:
                pass

            logger.info("Model optimized for CPU")
            return model

        except Exception as e:
            logger.error(f"CPU optimization failed: {e}")
            return model

    def get_gpu_memory_info(self) -> Dict[str, Any]:
        """Get GPU memory information."""
        info = {
            'platform': self.platform,
            'device_type': self.device_info.get('type', 'cpu'),
            'device_name': self.device_info.get('device_name', 'CPU'),
            'memory_total': 0,
            'memory_used': 0,
            'memory_free': 0
        }

        try:
            if self.device_info.get('type') == 'cuda':
                device_id = self.device_info.get('device_id', 0)
                memory_total = torch.cuda.get_device_properties(device_id).total_memory
                memory_allocated = torch.cuda.memory_allocated(device_id)
                memory_cached = torch.cuda.memory_reserved(device_id)

                info.update({
                    'memory_total': memory_total,
                    'memory_used': memory_allocated,
                    'memory_cached': memory_cached,
                    'memory_free': memory_total - memory_cached
                })
            elif self.device_info.get('type') == 'directml':
                # DirectML doesn't provide memory info directly
                info['memory_total'] = 0  # Unknown
                info['memory_used'] = 0
                info['memory_free'] = 0
        except Exception as e:
            logger.warning(f"Failed to get GPU memory info: {e}")

        return info

    def clear_gpu_cache(self) -> None:
        """Clear GPU memory cache."""
        try:
            if self.cuda_available:
                torch.cuda.empty_cache()
                logger.debug("CUDA cache cleared")
            # DirectML doesn't have explicit cache clearing
        except Exception as e:
            logger.warning(f"Failed to clear GPU cache: {e}")

    def get_optimal_batch_size(self, model_type: str = "embedding") -> int:
        """
        Get optimal batch size for the current hardware.

        Args:
            model_type: Type of model ('embedding', 'reranker', etc.)

        Returns:
            Optimal batch size
        """
        base_batch_size = CONFIG.embedding_batch_size

        # Adjust based on device type
        if self.device_info.get('type') == 'cuda':
            # CUDA can handle larger batches
            return min(base_batch_size * 2, 32)
        elif self.device_info.get('type') == 'directml':
            # DirectML is more conservative
            return min(base_batch_size, 16)
        else:
            # CPU is most conservative
            return min(base_batch_size // 2, 8)

    def benchmark_gpu_vs_cpu(self, model: torch.nn.Module, test_data: torch.Tensor) -> Dict[str, float]:
        """
        Benchmark GPU vs CPU performance.

        Args:
            model: Model to benchmark
            test_data: Test input data

        Returns:
            Dictionary with benchmark results
        """
        results = {}

        # CPU benchmark
        try:
            cpu_model = self._optimize_for_cpu(model)
            start_time = time.time()
            with torch.no_grad():
                _ = cpu_model(test_data)
            cpu_time = time.time() - start_time
            results['cpu_time'] = cpu_time
        except Exception as e:
            logger.warning(f"CPU benchmark failed: {e}")
            results['cpu_time'] = float('inf')

        # GPU benchmark
        device = self.get_device()
        if device != 'cpu':
            try:
                gpu_model = self.optimize_for_gpu(model, device)
                start_time = time.time()
                with torch.no_grad():
                    _ = gpu_model(test_data)
                gpu_time = time.time() - start_time
                results['gpu_time'] = gpu_time
                results['speedup'] = cpu_time / gpu_time if gpu_time > 0 else 0
            except Exception as e:
                logger.warning(f"GPU benchmark failed: {e}")
                results['gpu_time'] = float('inf')
                results['speedup'] = 0
        else:
            results['gpu_time'] = float('inf')
            results['speedup'] = 1.0

        return results

    def check_installation(self) -> bool:
        """
        Check if GPU acceleration is properly installed.

        Returns:
            True if GPU acceleration is available
        """
        if self.platform == "Windows":
            return self.directml_available
        else:
            return self.cuda_available

    def get_device_info(self) -> Dict[str, Any]:
        """Get comprehensive device information."""
        return {
            'platform': self.platform,
            'gpu_enabled': CONFIG.gpu_enabled,
            'device_info': self.device_info,
            'directml_available': self.directml_available,
            'cuda_available': self.cuda_available,
            'memory_info': self.get_gpu_memory_info()
        }


# Global GPU manager instance
_gpu_manager = None


def get_gpu_manager() -> GPUManager:
    """Get global GPU manager instance."""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUManager()
    return _gpu_manager


# Convenience functions for backward compatibility
def get_device() -> str:
    """Get the best available device."""
    return get_gpu_manager().get_device()


def optimize_for_gpu(model: torch.nn.Module, device: str) -> torch.nn.Module:
    """Optimize model for GPU."""
    return get_gpu_manager().optimize_for_gpu(model, device)


def get_gpu_memory_info() -> Dict[str, Any]:
    """Get GPU memory information."""
    return get_gpu_manager().get_gpu_memory_info()


def clear_gpu_cache() -> None:
    """Clear GPU memory cache."""
    get_gpu_manager().clear_gpu_cache()


def get_optimal_batch_size(model_type: str = "embedding") -> int:
    """Get optimal batch size."""
    return get_gpu_manager().get_optimal_batch_size(model_type)


def benchmark_gpu_vs_cpu(model: torch.nn.Module, test_data: torch.Tensor) -> Dict[str, float]:
    """Benchmark GPU vs CPU performance."""
    return get_gpu_manager().benchmark_gpu_vs_cpu(model, test_data)


def check_gpu_installation() -> bool:
    """Check GPU installation."""
    return get_gpu_manager().check_installation()


def get_gpu_info() -> Dict[str, Any]:
    """Get GPU information."""
    return get_gpu_manager().get_device_info()
