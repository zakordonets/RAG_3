#!/usr/bin/env python3
"""
Comprehensive benchmark for BGE-M3 embedding strategies
Compares ONNX, BGE, and Hybrid backends on different scenarios
"""
import sys
import os
sys.path.append(os.getcwd())

import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass
from loguru import logger

from app.services.bge_embeddings import embed_unified, embed_batch_optimized
from app.config import CONFIG

@dataclass
class BenchmarkResult:
    backend: str
    scenario: str
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float
    success_rate: float
    dense_shape: int
    sparse_tokens: int
    error_msg: str = ""

class EmbeddingsBenchmark:
    def __init__(self):
        self.results: List[BenchmarkResult] = []

        # Test scenarios
        self.test_texts = {
            "short_query": "Как настроить маршрутизацию?",
            "medium_query": "Как настроить маршрутизацию чатов из веб-виджета на отдел продаж в edna Chat Center?",
            "long_query": "Подробно объясните процесс настройки автоматической маршрутизации входящих чатов из веб-виджета на конкретный отдел продаж с учетом рабочего времени операторов и приоритетов обслуживания клиентов в системе edna Chat Center",
            "doc_chunk": """
            Маршрутизация чатов в edna Chat Center

            Система маршрутизации позволяет автоматически направлять входящие чаты операторам на основе заданных правил и условий. Основные возможности:

            1. Маршрутизация по навыкам операторов
            2. Распределение по группам и отделам
            3. Учет рабочего времени и доступности
            4. Приоритизация VIP-клиентов
            5. Балансировка нагрузки между операторами

            Настройка производится через панель администратора в разделе "Маршрутизация".
            """
        }

        self.batch_texts = [
            "Как добавить оператора?",
            "Настройка веб-виджета",
            "Интеграция с CRM системой",
            "Отчеты по операторам",
            "Управление очередями чатов"
        ]

    def benchmark_single_embedding(self, backend: str, text: str, scenario: str, runs: int = 5) -> BenchmarkResult:
        """Benchmark single text embedding."""
        logger.info(f"Benchmarking {backend} backend: {scenario}")

        # Temporarily override backend
        original_backend = CONFIG.embeddings_backend
        CONFIG.__dict__['embeddings_backend'] = backend

        times = []
        successes = 0
        dense_shape = 0
        sparse_tokens = 0
        error_msg = ""

        for i in range(runs):
            try:
                start = time.time()
                result = embed_unified(
                    text,
                    return_dense=True,
                    return_sparse=CONFIG.use_sparse,
                    context="query" if "query" in scenario else "document"
                )
                duration = time.time() - start
                times.append(duration)
                successes += 1

                # Extract metrics from first successful run
                if successes == 1:
                    if result.get('dense_vecs'):
                        dense_shape = len(result['dense_vecs'][0])
                    if result.get('lexical_weights') and result['lexical_weights'][0]:
                        sparse_tokens = len(result['lexical_weights'][0])

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Run {i+1} failed: {e}")

        # Restore original backend
        CONFIG.__dict__['embeddings_backend'] = original_backend

        if times:
            return BenchmarkResult(
                backend=backend,
                scenario=scenario,
                avg_time=statistics.mean(times),
                min_time=min(times),
                max_time=max(times),
                std_dev=statistics.stdev(times) if len(times) > 1 else 0.0,
                success_rate=successes / runs,
                dense_shape=dense_shape,
                sparse_tokens=sparse_tokens,
                error_msg=error_msg
            )
        else:
            return BenchmarkResult(
                backend=backend,
                scenario=scenario,
                avg_time=0.0,
                min_time=0.0,
                max_time=0.0,
                std_dev=0.0,
                success_rate=0.0,
                dense_shape=0,
                sparse_tokens=0,
                error_msg=error_msg
            )

    def benchmark_batch_embedding(self, backend: str, runs: int = 3) -> BenchmarkResult:
        """Benchmark batch text embedding."""
        logger.info(f"Benchmarking {backend} backend: batch_processing")

        # Temporarily override backend
        original_backend = CONFIG.embeddings_backend
        CONFIG.__dict__['embeddings_backend'] = backend

        times = []
        successes = 0
        dense_shape = 0
        sparse_tokens = 0
        error_msg = ""

        for i in range(runs):
            try:
                start = time.time()
                result = embed_batch_optimized(
                    self.batch_texts,
                    return_dense=True,
                    return_sparse=CONFIG.use_sparse,
                    context="document"
                )
                duration = time.time() - start
                times.append(duration)
                successes += 1

                # Extract metrics from first successful run
                if successes == 1:
                    if result.get('dense_vecs'):
                        dense_shape = len(result['dense_vecs'][0])
                    if result.get('lexical_weights'):
                        # Average sparse tokens across batch
                        sparse_counts = [len(lex) for lex in result['lexical_weights'] if lex]
                        sparse_tokens = int(statistics.mean(sparse_counts)) if sparse_counts else 0

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Batch run {i+1} failed: {e}")

        # Restore original backend
        CONFIG.__dict__['embeddings_backend'] = original_backend

        if times:
            return BenchmarkResult(
                backend=backend,
                scenario="batch_processing",
                avg_time=statistics.mean(times),
                min_time=min(times),
                max_time=max(times),
                std_dev=statistics.stdev(times) if len(times) > 1 else 0.0,
                success_rate=successes / runs,
                dense_shape=dense_shape,
                sparse_tokens=sparse_tokens,
                error_msg=error_msg
            )
        else:
            return BenchmarkResult(
                backend=backend,
                scenario="batch_processing",
                avg_time=0.0,
                min_time=0.0,
                max_time=0.0,
                std_dev=0.0,
                success_rate=0.0,
                dense_shape=0,
                sparse_tokens=0,
                error_msg=error_msg
            )

    def run_comprehensive_benchmark(self):
        """Run comprehensive benchmark across all backends and scenarios."""
        backends = ["onnx", "bge", "hybrid"]

        logger.info("🚀 Starting comprehensive embeddings benchmark")
        logger.info(f"Testing backends: {backends}")
        logger.info(f"Use sparse: {CONFIG.use_sparse}")

        # Single text benchmarks
        for backend in backends:
            for scenario, text in self.test_texts.items():
                result = self.benchmark_single_embedding(backend, text, scenario)
                self.results.append(result)

        # Batch processing benchmarks
        for backend in backends:
            result = self.benchmark_batch_embedding(backend)
            self.results.append(result)

    def print_results(self):
        """Print formatted benchmark results."""
        print("\n" + "="*100)
        print("🎯 EMBEDDINGS BENCHMARK RESULTS")
        print("="*100)

        # Group results by scenario
        scenarios = {}
        for result in self.results:
            if result.scenario not in scenarios:
                scenarios[result.scenario] = []
            scenarios[result.scenario].append(result)

        for scenario, results in scenarios.items():
            print(f"\n📊 {scenario.upper().replace('_', ' ')}")
            print("-" * 80)
            print(f"{'Backend':<10} {'Time (s)':<12} {'Success':<8} {'Dense':<8} {'Sparse':<8} {'Error'}")
            print("-" * 80)

            for result in results:
                time_str = f"{result.avg_time:.3f}±{result.std_dev:.3f}" if result.avg_time > 0 else "FAILED"
                success_str = f"{result.success_rate:.1%}"
                dense_str = str(result.dense_shape) if result.dense_shape > 0 else "-"
                sparse_str = str(result.sparse_tokens) if result.sparse_tokens > 0 else "-"
                error_str = result.error_msg[:30] + "..." if len(result.error_msg) > 30 else result.error_msg

                print(f"{result.backend:<10} {time_str:<12} {success_str:<8} {dense_str:<8} {sparse_str:<8} {error_str}")

    def get_performance_summary(self):
        """Generate performance summary and recommendations."""
        print("\n" + "="*100)
        print("🏆 PERFORMANCE SUMMARY & RECOMMENDATIONS")
        print("="*100)

        # Calculate average performance by backend
        backend_stats = {}
        for result in self.results:
            if result.success_rate > 0:  # Only consider successful runs
                if result.backend not in backend_stats:
                    backend_stats[result.backend] = []
                backend_stats[result.backend].append(result.avg_time)

        print("\n📈 Average Performance (successful runs only):")
        print("-" * 50)
        for backend, times in backend_stats.items():
            avg_time = statistics.mean(times)
            print(f"{backend.upper():<10}: {avg_time:.3f}s average")

        # Find best backend for each scenario type
        print("\n🎯 Best Backend by Scenario:")
        print("-" * 50)

        # Group results by scenario again for this function
        scenarios = {}
        for result in self.results:
            if result.scenario not in scenarios:
                scenarios[result.scenario] = []
            scenarios[result.scenario].append(result)

        scenario_winners = {}
        for scenario, results in scenarios.items():
            successful_results = [r for r in results if r.success_rate > 0]
            if successful_results:
                best = min(successful_results, key=lambda x: x.avg_time)
                scenario_winners[scenario] = best
                print(f"{scenario.replace('_', ' ').title():<20}: {best.backend.upper()} ({best.avg_time:.3f}s)")

        # Overall recommendation
        print("\n💡 RECOMMENDATIONS:")
        print("-" * 50)

        # Check system capabilities
        has_cuda = False
        has_directml = False

        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except ImportError:
            pass

        try:
            import onnxruntime as ort
            has_directml = "DmlExecutionProvider" in ort.get_available_providers()
        except ImportError:
            pass

        if has_cuda:
            print("✅ NVIDIA GPU detected → Use EMBEDDINGS_BACKEND=bge for best performance")
        elif has_directml:
            print("✅ AMD GPU detected → Use EMBEDDINGS_BACKEND=hybrid for optimal Windows/AMD setup")
        else:
            print("✅ CPU only → Use EMBEDDINGS_BACKEND=onnx for consistency")

        print(f"✅ Set EMBEDDINGS_BACKEND=auto for automatic optimal selection")

if __name__ == "__main__":
    benchmark = EmbeddingsBenchmark()

    logger.info("Configuration:")
    logger.info(f"  EMBEDDINGS_BACKEND: {CONFIG.embeddings_backend}")
    logger.info(f"  EMBEDDING_DEVICE: {CONFIG.embedding_device}")
    logger.info(f"  USE_SPARSE: {CONFIG.use_sparse}")
    logger.info(f"  MAX_LENGTH_QUERY: {CONFIG.embedding_max_length_query}")
    logger.info(f"  MAX_LENGTH_DOC: {CONFIG.embedding_max_length_doc}")

    benchmark.run_comprehensive_benchmark()
    benchmark.print_results()
    benchmark.get_performance_summary()

    logger.info("🎉 Comprehensive embeddings benchmark completed!")
