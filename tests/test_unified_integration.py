"""
Интеграционные тесты единого пайплайна
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from ingestion.run import run_unified_indexing, create_docusaurus_dag, create_website_dag
from ingestion.adapters.docusaurus import DocusaurusAdapter
from ingestion.adapters.website import WebsiteAdapter
from ingestion.pipeline.dag import PipelineDAG
from ingestion.state.state_manager import StateManager, DocumentState

pytestmark = pytest.mark.integration


class TestUnifiedPipelineIntegration:
    """Интеграционные тесты единого пайплайна"""

    def test_docusaurus_dag_creation(self):
        """Тест создания DAG для Docusaurus"""
        config = {
            "site_base_url": "https://test.com",
            "site_docs_prefix": "/docs",
            "chunk_max_tokens": 300,
            "chunk_overlap_tokens": 60,
            "batch_size": 8
        }

        dag = create_docusaurus_dag(config)

        assert isinstance(dag, PipelineDAG)
        assert len(dag.steps) == 6

        step_names = dag.get_step_names()
        expected_steps = ["parser", "docusaurus_normalizer", "url_mapper", "unified_chunker", "embedder", "qdrant_writer"]
        assert step_names == expected_steps

    def test_website_dag_creation(self):
        """Тест создания DAG для веб-сайтов"""
        config = {
            "chunk_max_tokens": 300,
            "chunk_overlap_tokens": 60,
            "batch_size": 8
        }

        dag = create_website_dag(config)

        assert isinstance(dag, PipelineDAG)
        assert len(dag.steps) == 7

        step_names = dag.get_step_names()
        expected_steps = ["parser", "html_normalizer", "content_extractor", "base_normalizer", "unified_chunker", "embedder", "qdrant_writer"]
        assert step_names == expected_steps

    @patch('ingestion.pipeline.indexers.qdrant_writer.QdrantClient')
    @patch('ingestion.pipeline.embedder.embed_batch_optimized')
    def test_docusaurus_end_to_end(self, mock_embed, mock_qdrant):
        """Тест полного пайплайна для Docusaurus"""
        # Настраиваем моки
        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance
        mock_qdrant_instance.upsert.return_value = None

        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024, [0.2] * 1024],
            'lexical_weights': [{}, {}]
        }

        # Создаем тестовую структуру Docusaurus
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()

            # Создаем тестовые файлы
            (docs_dir / "test1.md").write_text("""---
title: Test Document 1
category: АРМ_adm
---

# Test Document 1

This is a test document with some content.

<ContentRef url="/docs/test2">See also test2</ContentRef>
""")

            (docs_dir / "test2.md").write_text("""---
title: Test Document 2
category: АРМ_sv
---

# Test Document 2

Another test document.
""")

            # Создаем _category_.json
            (docs_dir / "_category_.json").write_text('{"label": "Test Category"}')

            # Конфигурация
            config = {
                "docs_root": str(docs_dir),
                "site_base_url": "https://test.com",
                "site_docs_prefix": "/docs",
                "collection_name": "test_collection",
                "chunk_max_tokens": 300,
                "chunk_overlap_tokens": 60,
                "batch_size": 8
            }

            # Запускаем индексацию
            result = run_unified_indexing("docusaurus", config, "full")

            # Проверяем результат
            assert result["success"] is True
            assert result["source_type"] == "docusaurus"
            assert "stats" in result

            # Проверяем, что были созданы эмбеддинги
            assert mock_embed.called

            # Проверяем, что были записаны в Qdrant
            assert mock_qdrant_instance.upsert.called

    @patch('ingestion.adapters.website.requests.get')
    @patch('ingestion.pipeline.indexers.qdrant_writer.QdrantClient')
    @patch('ingestion.pipeline.embedder.embed_batch_optimized')
    def test_website_end_to_end(self, mock_embed, mock_qdrant, mock_requests):
        """Тест полного пайплайна для веб-сайтов"""
        # Настраиваем моки
        mock_response = Mock()
        mock_response.content = b"""<html>
        <head><title>Test Page</title></head>
        <body>
            <main>
                <h1>Test Page</h1>
                <p>This is a test page with some content.</p>
            </main>
        </body>
        </html>"""
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response

        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance
        mock_qdrant_instance.upsert.return_value = None

        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024],
            'lexical_weights': [{}]
        }

        # Конфигурация
        config = {
            "seed_urls": ["https://test.com"],
            "base_url": "https://test.com",
            "collection_name": "test_collection",
            "chunk_max_tokens": 300,
            "chunk_overlap_tokens": 60,
            "batch_size": 8,
            "max_pages": 1
        }

        # Запускаем индексацию
        result = run_unified_indexing("website", config, "full")

        # Проверяем результат
        assert result["success"] is True
        assert result["source_type"] == "website"
        assert "stats" in result

        # Проверяем, что был сделан HTTP запрос
        mock_requests.assert_called()

        # Проверяем, что были созданы эмбеддинги
        assert mock_embed.called

        # Проверяем, что были записаны в Qdrant
        assert mock_qdrant_instance.upsert.called

    def test_state_manager_integration(self):
        """Тест интеграции с StateManager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "test_state.json"

            # Создаем менеджер состояния
            with StateManager(str(state_file)) as state_manager:
                # Тестируем создание ID
                doc_id = state_manager.get_doc_id("https://test.com/page", "website")
                assert len(doc_id) == 40  # SHA1 hash length

                # Тестируем проверку изменений
                content = b"Test content"
                content_hash = state_manager.get_content_hash(content)
                assert len(content_hash) == 40

                # Новый документ должен быть изменен
                assert state_manager.is_document_changed("https://test.com/page", "website", content, 1234567890)

                # Обновляем состояние
                state_manager.update_document_state("https://test.com/page", "website", content, 1234567890)

                # Теперь документ не должен быть изменен
                assert not state_manager.is_document_changed("https://test.com/page", "website", content, 1234567890)

                # Получаем статистику
                stats = state_manager.get_stats()
                assert stats["total_documents"] == 1
                assert "website" in stats["sources"]

            # Проверяем, что состояние сохранилось
            assert state_file.exists()

            # Загружаем заново
            with StateManager(str(state_file)) as state_manager2:
                stats2 = state_manager2.get_stats()
                assert stats2["total_documents"] == 1

    def test_dag_error_handling(self):
        """Тест обработки ошибок в DAG"""

        class FailingStep:
            def process(self, data):
                raise ValueError("Test error")

            def get_step_name(self):
                return "failing_step"

        # Создаем DAG с падающим шагом
        dag = PipelineDAG([FailingStep()])

        # Создаем тестовые данные
        from ingestion.adapters.base import RawDoc
        raw_docs = [RawDoc(uri="test://1", bytes=b"content")]

        # Запускаем DAG
        stats = dag.run(raw_docs)

        # Проверяем, что ошибки обработаны
        assert stats["total_docs"] == 1
        assert stats["processed_docs"] == 0
        assert stats["failed_docs"] == 1

    def test_batch_processing(self):
        """Тест батчевой обработки"""

        class CountingStep:
            def __init__(self, name):
                self.name = name
                self.processed_count = 0

            def process(self, data):
                self.processed_count += 1
                return data

            def get_step_name(self):
                return self.name

        # Создаем DAG
        step = CountingStep("counter")
        dag = PipelineDAG([step])

        # Создаем много документов
        from ingestion.adapters.base import RawDoc
        raw_docs = [RawDoc(uri=f"test://{i}", bytes=b"content") for i in range(100)]

        # Запускаем DAG
        stats = dag.run(raw_docs)

        # Проверяем, что все документы обработаны
        assert stats["total_docs"] == 100
        assert stats["processed_docs"] == 100
        assert stats["failed_docs"] == 0
        assert step.processed_count == 100


class TestUnifiedPipelinePerformance:
    """Тесты производительности единого пайплайна"""

    def test_dag_performance(self):
        """Тест производительности DAG"""
        import time

        class FastStep:
            def __init__(self, name, delay=0.001):
                self.name = name
                self.delay = delay

            def process(self, data):
                time.sleep(self.delay)
                return data

            def get_step_name(self):
                return self.name

        # Создаем DAG с быстрыми шагами
        steps = [FastStep(f"step_{i}") for i in range(5)]
        dag = PipelineDAG(steps)

        # Создаем тестовые данные
        from ingestion.adapters.base import RawDoc
        raw_docs = [RawDoc(uri=f"test://{i}", bytes=b"content") for i in range(10)]

        # Запускаем и измеряем время
        start_time = time.time()
        stats = dag.run(raw_docs)
        elapsed = time.time() - start_time

        # Проверяем производительность
        assert stats["total_docs"] == 10
        assert stats["processed_docs"] == 10
        assert elapsed < 1.0  # Должно быть быстро

        # Проверяем время по шагам
        total_step_time = sum(stats["step_times"].values())
        assert total_step_time > 0
        assert total_step_time < elapsed  # Время шагов меньше общего времени


if __name__ == "__main__":
    pytest.main([__file__])
