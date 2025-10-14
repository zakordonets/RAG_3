"""
Тесты для контрактов единой архитектуры
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import time

from ingestion.adapters.base import RawDoc, ParsedDoc, SourceAdapter, PipelineStep
from ingestion.adapters.docusaurus import DocusaurusAdapter
from ingestion.adapters.website import WebsiteAdapter
from ingestion.pipeline.dag import PipelineDAG

pytestmark = pytest.mark.unit


class TestRawDoc:
    """Тесты для RawDoc dataclass"""

    def test_raw_doc_creation(self):
        """Тест создания RawDoc"""
        raw_doc = RawDoc(
            uri="file://test.md",
            bytes=b"# Test content",
            meta={"source": "test"}
        )

        assert raw_doc.uri == "file://test.md"
        assert raw_doc.bytes == b"# Test content"
        assert raw_doc.meta["source"] == "test"
        assert isinstance(raw_doc.fetched_at, float)
        assert raw_doc.fetched_at > 0

    def test_raw_doc_defaults(self):
        """Тест значений по умолчанию"""
        raw_doc = RawDoc(uri="test://example")

        assert raw_doc.abs_path is None
        assert raw_doc.bytes == b""
        assert raw_doc.meta == {}
        assert isinstance(raw_doc.fetched_at, float)


class TestParsedDoc:
    """Тесты для ParsedDoc dataclass"""

    def test_parsed_doc_creation(self):
        """Тест создания ParsedDoc"""
        parsed_doc = ParsedDoc(
            text="Parsed text content",
            format="markdown",
            frontmatter={"title": "Test"},
            metadata={"source": "test"}
        )

        assert parsed_doc.text == "Parsed text content"
        assert parsed_doc.format == "markdown"
        assert parsed_doc.frontmatter["title"] == "Test"
        assert parsed_doc.metadata["source"] == "test"
        assert parsed_doc.dom is None

    def test_parsed_doc_defaults(self):
        """Тест значений по умолчанию"""
        parsed_doc = ParsedDoc(text="test", format="text")

        assert parsed_doc.frontmatter is None
        assert parsed_doc.dom is None
        assert parsed_doc.metadata == {}


class TestSourceAdapter:
    """Тесты для SourceAdapter интерфейса"""

    def test_source_adapter_interface(self):
        """Тест, что SourceAdapter является абстрактным классом"""
        with pytest.raises(TypeError):
            SourceAdapter()  # Нельзя создать экземпляр абстрактного класса

    def test_docusaurus_adapter_implements_interface(self):
        """Тест, что DocusaurusAdapter реализует SourceAdapter"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем тестовую структуру
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()

            # Создаем тестовый файл
            test_file = docs_dir / "test.md"
            test_file.write_text("# Test Document")

            adapter = DocusaurusAdapter(str(docs_dir))

            # Проверяем, что это SourceAdapter
            assert isinstance(adapter, SourceAdapter)
            assert adapter.get_source_name() == "docusaurus"

    def test_website_adapter_implements_interface(self):
        """Тест, что WebsiteAdapter реализует SourceAdapter"""
        adapter = WebsiteAdapter(seed_urls=["https://example.com"])

        # Проверяем, что это SourceAdapter
        assert isinstance(adapter, SourceAdapter)
        assert adapter.get_source_name() == "website"


class TestPipelineStep:
    """Тесты для PipelineStep интерфейса"""

    def test_pipeline_step_interface(self):
        """Тест, что PipelineStep является абстрактным классом"""
        with pytest.raises(TypeError):
            PipelineStep()  # Нельзя создать экземпляр абстрактного класса

    def test_concrete_pipeline_step(self):
        """Тест конкретной реализации PipelineStep"""

        class TestStep(PipelineStep):
            def process(self, data):
                return f"processed_{data}"

            def get_step_name(self):
                return "test_step"

        step = TestStep()
        assert isinstance(step, PipelineStep)
        assert step.get_step_name() == "test_step"
        assert step.process("input") == "processed_input"


class TestPipelineDAG:
    """Тесты для PipelineDAG"""

    def test_dag_creation(self):
        """Тест создания DAG"""

        class TestStep(PipelineStep):
            def __init__(self, name, transform):
                self.name = name
                self.transform = transform

            def process(self, data):
                return self.transform(data)

            def get_step_name(self):
                return self.name

        steps = [
            TestStep("step1", lambda x: f"step1_{x}"),
            TestStep("step2", lambda x: f"step2_{x}")
        ]

        dag = PipelineDAG(steps)
        assert len(dag.steps) == 2
        assert dag.get_step_names() == ["step1", "step2"]

    def test_dag_run_empty(self):
        """Тест запуска DAG с пустым потоком"""

        class TestStep(PipelineStep):
            def process(self, data):
                return data

            def get_step_name(self):
                return "test"

        dag = PipelineDAG([TestStep()])
        stats = dag.run([])

        assert stats["total_docs"] == 0
        assert stats["processed_docs"] == 0
        assert stats["failed_docs"] == 0

    def test_dag_run_with_data(self):
        """Тест запуска DAG с данными"""

        class TransformStep(PipelineStep):
            def __init__(self, name, transform):
                self.name = name
                self.transform = transform

            def process(self, data):
                return self.transform(data)

            def get_step_name(self):
                return self.name

        # Создаем тестовые RawDoc
        raw_docs = [
            RawDoc(uri="test1", bytes=b"content1"),
            RawDoc(uri="test2", bytes=b"content2")
        ]

        # Создаем DAG с простыми трансформациями
        steps = [
            TransformStep("add_prefix", lambda x: f"prefix_{x.uri}"),
            TransformStep("add_suffix", lambda x: f"{x}_suffix")
        ]

        dag = PipelineDAG(steps)
        stats = dag.run(raw_docs)

        assert stats["total_docs"] == 2
        assert stats["processed_docs"] == 2
        assert stats["failed_docs"] == 0

    def test_dag_error_handling(self):
        """Тест обработки ошибок в DAG"""

        class FailingStep(PipelineStep):
            def process(self, data):
                if "fail" in data.uri:
                    raise ValueError("Test error")
                return data

            def get_step_name(self):
                return "failing_step"

        raw_docs = [
            RawDoc(uri="success", bytes=b"content"),
            RawDoc(uri="fail", bytes=b"content")
        ]

        dag = PipelineDAG([FailingStep()])
        stats = dag.run(raw_docs)

        assert stats["total_docs"] == 2
        assert stats["processed_docs"] == 1
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

        dag.add_step(TestStep("step2"))
        assert len(dag.steps) == 2
        assert dag.get_step_names() == ["step1", "step2"]

        dag.add_step(TestStep("step3"), position=1)
        assert dag.get_step_names() == ["step1", "step3", "step2"]


if __name__ == "__main__":
    pytest.main([__file__])
