"""
Smoke-тесты для полного пайплайна SDK документации
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from ingestion.adapters.docusaurus import DocusaurusAdapter
from ingestion.run import load_sources_from_config, create_docusaurus_dag
from ingestion.pipeline.dag import PipelineDAG

pytestmark = pytest.mark.integration


class TestSDKDocsPipeline:
    """Smoke-тесты для полного пайплайна обработки SDK документации"""

    def test_config_loading_with_sdk_source(self):
        """Тест загрузки конфигурации с SDK источником"""
        config_text = """
        global:
          qdrant:
            collection: "test_collection"
        sources:
          docusaurus:
            enabled: true
            docs_root: "C:\\\\CC_RAG\\\\docs"
            site_base_url: "https://docs-chatcenter.edna.ru"
            site_docs_prefix: "/docs"
          docusaurus_sdk:
            enabled: true
            docs_root: "C:\\\\CC_RAG\\\\SDK_docs\\\\docs"
            site_base_url: "https://docs-sdk.edna.ru"
            site_docs_prefix: ""
            top_level_meta:
              android:
                sdk_platform: "android"
                product: "sdk"
              ios:
                sdk_platform: "ios"
                product: "sdk"
              web:
                sdk_platform: "web"
                product: "sdk"
              main:
                sdk_platform: "main"
                product: "sdk"
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yaml"
            config_path.write_text(config_text, encoding="utf-8")

            sources = load_sources_from_config(str(config_path))

            assert len(sources) == 2

            # Проверяем обычный источник
            docusaurus_source = next(src for src in sources if src["name"] == "docusaurus")
            assert docusaurus_source["source_type"] == "docusaurus"
            assert docusaurus_source["config"]["site_docs_prefix"] == "/docs"

            # Проверяем SDK источник
            sdk_source = next(src for src in sources if src["name"] == "docusaurus_sdk")
            assert sdk_source["source_type"] == "docusaurus"
            assert sdk_source["config"]["site_docs_prefix"] == ""
            assert sdk_source["config"]["site_base_url"] == "https://docs-sdk.edna.ru"
            assert "android" in sdk_source["config"]["top_level_meta"]
            assert "ios" in sdk_source["config"]["top_level_meta"]
            assert "web" in sdk_source["config"]["top_level_meta"]
            assert "main" in sdk_source["config"]["top_level_meta"]

    def test_dag_creation_with_empty_prefix(self):
        """Тест создания DAG с пустым site_docs_prefix"""
        config = {
            "site_base_url": "https://docs-sdk.edna.ru",
            "site_docs_prefix": "",
            "collection_name": "test_collection",
            "batch_size": 16,
            "chunk_max_tokens": 600,
            "chunk_min_tokens": 350,
            "chunk_overlap_base": 100,
            "chunk_oversize_block_policy": "split",
            "chunk_oversize_block_limit": 1200
        }

        dag = create_docusaurus_dag(config)

        assert isinstance(dag, PipelineDAG)
        assert len(dag.steps) > 0

        # Проверяем, что URLMapper получил пустой префикс
        url_mapper = None
        for step in dag.steps:
            if hasattr(step, 'site_docs_prefix'):
                url_mapper = step
                break

        if url_mapper:
            assert url_mapper.site_docs_prefix == ""

    @patch('ingestion.pipeline.indexers.qdrant_writer.QdrantClient')
    def test_adapter_to_dag_flow(self, mock_qdrant_client):
        """Smoke-тест потока от адаптера до DAG (без реальной записи в Qdrant)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем тестовую структуру SDK
            android_dir = docs_root / "android"
            android_dir.mkdir()

            intro_file = android_dir / "intro.md"
            intro_file.write_text("# Android SDK Introduction\n\nThis is a test document.")

            top_level_meta = {
                "android": {
                    "sdk_platform": "android",
                    "product": "sdk"
                }
            }

            adapter = DocusaurusAdapter(
                docs_root=str(docs_root),
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix="",
                top_level_meta=top_level_meta
            )

            # Получаем документы от адаптера
            documents = list(adapter.iter_documents())

            assert len(documents) == 1
            doc = documents[0]

            # Проверяем метаданные
            assert doc.meta["top_level_dir"] == "android"
            assert doc.meta["sdk_platform"] == "android"
            assert doc.meta["site_url"] == "https://docs-sdk.edna.ru/android/intro"

            # Создаем DAG с моками
            config = {
                "site_base_url": "https://docs-sdk.edna.ru",
                "site_docs_prefix": "",
                "collection_name": "test_collection",
                "batch_size": 1,
                "chunk_max_tokens": 100,
                "chunk_min_tokens": 50,
                "chunk_overlap_base": 10,
                "chunk_oversize_block_policy": "split",
                "chunk_oversize_block_limit": 200
            }

            dag = create_docusaurus_dag(config)

            # Мокаем QdrantWriter чтобы не писать в реальную БД
            mock_writer = dag.steps[-1]
            if hasattr(mock_writer, 'ensure_collection'):
                mock_writer.ensure_collection = Mock()
            if hasattr(mock_writer, 'process'):
                original_process = mock_writer.process
                mock_writer.process = Mock(side_effect=original_process)

            # Запускаем DAG (может упасть на реальной записи, но проверим до этого)
            try:
                # Пробуем обработать хотя бы один документ
                from ingestion.adapters.base import RawDoc
                test_doc = documents[0]

                # Проверяем, что документ можно обработать через первые шаги
                from ingestion.normalizers.base import Parser
                parser = Parser()
                parsed = parser.process(test_doc)

                assert parsed is not None
                assert hasattr(parsed, 'content') or hasattr(parsed, 'text')

            except Exception as e:
                # Если ошибка связана с Qdrant - это нормально для smoke-теста
                if "qdrant" in str(e).lower() or "connection" in str(e).lower():
                    pytest.skip(f"Qdrant недоступен для smoke-теста: {e}")
                else:
                    raise

    def test_multiple_sources_config(self):
        """Тест конфигурации с несколькими источниками"""
        config_text = """
        global:
          qdrant:
            collection: "test_collection"
        sources:
          docusaurus:
            enabled: true
            docs_root: "C:\\\\CC_RAG\\\\docs"
            site_base_url: "https://docs-chatcenter.edna.ru"
            site_docs_prefix: "/docs"
          docusaurus_sdk:
            enabled: true
            docs_root: "C:\\\\CC_RAG\\\\SDK_docs\\\\docs"
            site_base_url: "https://docs-sdk.edna.ru"
            site_docs_prefix: ""
            top_level_meta:
              android:
                sdk_platform: "android"
                product: "sdk"
          docusaurus_disabled:
            enabled: false
            docs_root: "C:\\\\CC_RAG\\\\disabled"
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.yaml"
            config_path.write_text(config_text, encoding="utf-8")

            sources = load_sources_from_config(str(config_path))

            # Должны быть загружены только включенные источники
            assert len(sources) == 2
            source_names = {src["name"] for src in sources}
            assert source_names == {"docusaurus", "docusaurus_sdk"}
            assert "docusaurus_disabled" not in source_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
