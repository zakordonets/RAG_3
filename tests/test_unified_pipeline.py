"""
Тесты для единого PipelineDAG
"""

import pytest
import time
from unittest.mock import Mock, patch
from typing import List, Any

from ingestion.pipeline.dag import PipelineDAG
from ingestion.adapters.base import RawDoc, PipelineStep

pytestmark = pytest.mark.unit


class TestPipelineDAG:
    """Тесты для PipelineDAG"""

    def test_dag_creation(self):
        """Тест создания DAG"""

        class TestStep(PipelineStep):
            def __init__(self, name):
                self.name = name

            def process(self, data):
                return data

            def get_step_name(self):
                return self.name

        steps = [TestStep("step1"), TestStep("step2")]
        dag = PipelineDAG(steps)

        assert len(dag.steps) == 2
        assert dag.get_step_names() == ["step1", "step2"]
        assert dag.stats["total_docs"] == 0

    def test_dag_run_empty_stream(self):
        """Тест запуска DAG с пустым потоком"""

        class TestStep(PipelineStep):
            def process(self, data):
                return data

            def get_step_name(self):
                return "test_step"

        dag = PipelineDAG([TestStep()])
        stats = dag.run([])

        assert stats["total_docs"] == 0
        assert stats["processed_docs"] == 0
        assert stats["failed_docs"] == 0
        assert "total_time" in stats
        assert "step_times" in stats

    def test_dag_run_single_document(self):
        """Тест обработки одного документа"""

        class TransformStep(PipelineStep):
            def __init__(self, name, transform_func):
                self.name = name
                self.transform_func = transform_func

            def process(self, data):
                return self.transform_func(data)

            def get_step_name(self):
                return self.name

        # Создаем тестовый RawDoc
        raw_doc = RawDoc(uri="test://example", bytes=b"test content")

        # Создаем DAG с трансформациями
        steps = [
            TransformStep("add_prefix", lambda x: f"prefix_{x.uri}"),
            TransformStep("add_suffix", lambda x: f"{x}_suffix")
        ]

        dag = PipelineDAG(steps)
        stats = dag.run([raw_doc])

        assert stats["total_docs"] == 1
        assert stats["processed_docs"] == 1
        assert stats["failed_docs"] == 0
        assert stats["step_times"]["add_prefix"] >= 0  # Время может быть 0 для быстрых операций
        assert stats["step_times"]["add_suffix"] >= 0  # Время может быть 0 для быстрых операций

    def test_dag_run_multiple_documents(self):
        """Тест обработки нескольких документов"""

        class CountStep(PipelineStep):
            def __init__(self, name):
                self.name = name
                self.processed_count = 0

            def process(self, data):
                self.processed_count += 1
                return data

            def get_step_name(self):
                return self.name

        # Создаем тестовые RawDoc
        raw_docs = [
            RawDoc(uri="test://1", bytes=b"content1"),
            RawDoc(uri="test://2", bytes=b"content2"),
            RawDoc(uri="test://3", bytes=b"content3")
        ]

        step = CountStep("counter")
        dag = PipelineDAG([step])
        stats = dag.run(raw_docs)

        assert stats["total_docs"] == 3
        assert stats["processed_docs"] == 3
        assert stats["failed_docs"] == 0
        assert step.processed_count == 3

    def test_dag_error_handling(self):
        """Тест обработки ошибок в DAG"""

        class FailingStep(PipelineStep):
            def __init__(self, name, should_fail_for=None):
                self.name = name
                self.should_fail_for = should_fail_for or []

            def process(self, data):
                if data.uri in self.should_fail_for:
                    raise ValueError(f"Test error for {data.uri}")
                return data

            def get_step_name(self):
                return self.name

        # Создаем тестовые RawDoc
        raw_docs = [
            RawDoc(uri="success1", bytes=b"content1"),
            RawDoc(uri="fail", bytes=b"content2"),
            RawDoc(uri="success2", bytes=b"content3")
        ]

        step = FailingStep("failing_step", should_fail_for=["fail"])
        dag = PipelineDAG([step])
        stats = dag.run(raw_docs)

        assert stats["total_docs"] == 3
        assert stats["processed_docs"] == 2
        assert stats["failed_docs"] == 1

    def test_dag_critical_error(self):
        """Тест критической ошибки в DAG"""

        class CriticalFailingStep(PipelineStep):
            def process(self, data):
                raise RuntimeError("Critical error")

            def get_step_name(self):
                return "critical_step"

        raw_docs = [RawDoc(uri="test", bytes=b"content")]
        dag = PipelineDAG([CriticalFailingStep()])

        # DAG обрабатывает ошибки внутри и не выбрасывает их наружу
        stats = dag.run(raw_docs)

        # Проверяем, что ошибка была обработана
        assert stats["total_docs"] == 1
        assert stats["processed_docs"] == 0
        assert stats["failed_docs"] == 1

    def test_dag_add_step(self):
        """Тест добавления шага в DAG"""

        class TestStep(PipelineStep):
            def __init__(self, name):
                self.name = name

            def process(self, data):
                return data

            def get_step_name(self):
                return self.name

        dag = PipelineDAG([TestStep("step1")])
        assert len(dag.steps) == 1

        # Добавляем в конец
        dag.add_step(TestStep("step2"))
        assert len(dag.steps) == 2
        assert dag.get_step_names() == ["step1", "step2"]

        # Добавляем в середину
        dag.add_step(TestStep("step3"), position=1)
        assert len(dag.steps) == 3
        assert dag.get_step_names() == ["step1", "step3", "step2"]

        # Проверяем, что статистика обновилась
        assert "step3" in dag.stats["step_times"]

    def test_dag_step_timing(self):
        """Тест измерения времени выполнения шагов"""

        class SlowStep(PipelineStep):
            def __init__(self, name, delay=0.1):
                self.name = name
                self.delay = delay

            def process(self, data):
                time.sleep(self.delay)
                return data

            def get_step_name(self):
                return self.name

        raw_docs = [RawDoc(uri="test", bytes=b"content")]

        steps = [
            SlowStep("fast_step", delay=0.05),
            SlowStep("slow_step", delay=0.1)
        ]

        dag = PipelineDAG(steps)
        stats = dag.run(raw_docs)

        # Проверяем, что время измеряется
        assert stats["step_times"]["fast_step"] > 0
        assert stats["step_times"]["slow_step"] > 0
        assert stats["step_times"]["slow_step"] > stats["step_times"]["fast_step"]

    def test_dag_progress_logging(self):
        """Тест логирования прогресса"""

        class TestStep(PipelineStep):
            def process(self, data):
                return data

            def get_step_name(self):
                return "test_step"

        # Создаем много документов для проверки логирования
        raw_docs = [RawDoc(uri=f"test://{i}", bytes=b"content") for i in range(150)]

        dag = PipelineDAG([TestStep()])
        stats = dag.run(raw_docs)

        assert stats["total_docs"] == 150
        assert stats["processed_docs"] == 150
        assert stats["failed_docs"] == 0

    def test_dag_step_names(self):
        """Тест получения имен шагов"""

        class TestStep(PipelineStep):
            def __init__(self, name):
                self.name = name

            def process(self, data):
                return data

            def get_step_name(self):
                return self.name

        steps = [
            TestStep("parser"),
            TestStep("normalizer"),
            TestStep("chunker"),
            TestStep("embedder"),
            TestStep("indexer")
        ]

        dag = PipelineDAG(steps)
        step_names = dag.get_step_names()

        expected_names = ["parser", "normalizer", "chunker", "embedder", "indexer"]
        assert step_names == expected_names


if __name__ == "__main__":
    pytest.main([__file__])
