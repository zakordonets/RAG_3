"""
Тесты для единого QdrantWriter и индексации
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from ingestion.pipeline.indexers.qdrant_writer import QdrantWriter
from ingestion.pipeline.chunker import UnifiedChunkerStep
from ingestion.pipeline.embedder import Embedder
from ingestion.adapters.base import ParsedDoc


class TestQdrantWriter:
    """Тесты для единого QdrantWriter"""

    @patch('ingestion.pipeline.indexers.qdrant_writer.QdrantClient')
    @patch('ingestion.pipeline.indexers.qdrant_writer.embed_batch_optimized')
    def test_qdrant_writer_creation(self, mock_embed, mock_qdrant):
        """Тест создания QdrantWriter"""
        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance

        writer = QdrantWriter(collection_name="test_collection")

        assert writer.collection_name == "test_collection"
        assert writer.batch_size == 32  # Default from CONFIG (может быть изменен в тестовой среде)
        assert isinstance(writer.stats, dict)

    @patch('ingestion.pipeline.indexers.qdrant_writer.QdrantClient')
    @patch('ingestion.pipeline.indexers.qdrant_writer.embed_batch_optimized')
    def test_qdrant_writer_process_batch(self, mock_embed, mock_qdrant):
        """Тест обработки батча чанков"""
        # Настраиваем моки
        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance
        mock_qdrant_instance.upsert.return_value = None

        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024, [0.2] * 1024],
            'lexical_weights': [{"1": 0.5, "2": 0.3}, {"3": 0.7}]
        }

        writer = QdrantWriter(collection_name="test_collection")

        # Создаем тестовые чанки
        chunks = [
            {
                "text": "Test content 1",
                "payload": {
                    "chunk_id": "doc1#0",
                    "title": "Test 1",
                    "category": "АРМ_adm"
                }
            },
            {
                "text": "Test content 2",
                "payload": {
                    "chunk_id": "doc2#0",
                    "title": "Test 2",
                    "category": "АРМ_sv"
                }
            }
        ]

        # Обрабатываем батч
        result = writer._process_batch(chunks)

        # Проверяем результат
        assert result == 2  # Обработано 2 чанка

        # Проверяем, что были созданы эмбеддинги
        mock_embed.assert_called_once()

        # Проверяем, что были записаны в Qdrant
        mock_qdrant_instance.upsert.assert_called_once()

        # Проверяем структуру записанных точек
        call_args = mock_qdrant_instance.upsert.call_args
        points = call_args[1]["points"]

        assert len(points) == 2
        for point in points:
            assert hasattr(point, 'id')
            assert hasattr(point, 'vector')
            assert hasattr(point, 'payload')
            assert 'dense' in point.vector
            assert 'sparse' in point.vector

    @patch('ingestion.pipeline.indexers.qdrant_writer.QdrantClient')
    def test_qdrant_writer_create_payload_indexes(self, mock_qdrant):
        """Тест создания индексов payload"""
        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance
        mock_qdrant_instance.create_payload_index.return_value = None

        writer = QdrantWriter(collection_name="test_collection")
        writer.create_payload_indexes()

        # Проверяем, что были созданы индексы
        assert mock_qdrant_instance.create_payload_index.call_count >= 5

        # Проверяем, что были созданы индексы для ключевых полей
        called_fields = [call[1]['field_name'] for call in mock_qdrant_instance.create_payload_index.call_args_list]
        expected_fields = ["category", "groups_path", "title", "source", "content_type"]

        for field in expected_fields:
            assert field in called_fields

    def test_qdrant_writer_generate_point_id(self):
        """Тест генерации ID точек"""
        writer = QdrantWriter()

        # Тест с chunk_id
        chunk_with_id = {
            "payload": {"chunk_id": "doc1#0"}
        }
        point_id = writer._generate_point_id(chunk_with_id, "test text")

        # Проверяем, что ID в формате UUID
        try:
            uuid.UUID(point_id)
            assert True
        except ValueError:
            pytest.fail(f"Generated ID is not a valid UUID: {point_id}")

        # Тест без chunk_id
        chunk_without_id = {"text": "test text"}
        point_id2 = writer._generate_point_id(chunk_without_id, "test text")

        # ID должен быть детерминистическим
        point_id3 = writer._generate_point_id(chunk_without_id, "test text")
        assert point_id2 == point_id3

    def test_qdrant_writer_convert_sparse_data(self):
        """Тест преобразования sparse данных"""
        writer = QdrantWriter()

        # Тест с валидными данными
        sparse_data = {"1": 0.5, "2": 0.3, "3": 0.7}
        indices, values = writer._convert_sparse_data(sparse_data)

        assert len(indices) == 3
        assert len(values) == 3
        assert indices == [3, 1, 2]  # Отсортированы по убыванию весов
        assert values == [0.7, 0.5, 0.3]

        # Тест с пустыми данными
        indices_empty, values_empty = writer._convert_sparse_data({})
        assert indices_empty == []
        assert values_empty == []

    def test_qdrant_writer_create_payload(self):
        """Тест создания payload"""
        writer = QdrantWriter()

        chunk = {
            "text": "Test content",
            "payload": {
                "title": "Test Title",
                "category": "АРМ_adm",
                "content": "Heavy content to be removed"
            }
        }

        payload = writer._create_payload(chunk, "Test content", chunk["payload"])

        # Проверяем обязательные поля
        assert payload["text"] == "Test content"
        assert "indexed_at" in payload
        assert payload["indexed_via"] == "unified_pipeline"

        # Проверяем, что тяжелые поля удалены
        assert "content" not in payload
        assert "html" not in payload

        # Проверяем, что полезные поля сохранены
        assert payload["title"] == "Test Title"
        assert payload["category"] == "АРМ_adm"


class TestUnifiedChunkerStep:
    """Тесты для UnifiedChunkerStep"""

    def test_chunker_creation(self):
        """Тест создания чанкера"""
        chunker = UnifiedChunkerStep(
            max_tokens=300,
            overlap_tokens=60,
            strategy="simple"
        )

        assert chunker.max_tokens == 300
        assert chunker.overlap_tokens == 60
        assert chunker.get_step_name() == "unified_chunker"

    def test_chunker_process_document(self):
        """Тест обработки документа"""
        chunker = UnifiedChunkerStep(max_tokens=100, overlap_tokens=20)

        # Создаем тестовый документ
        parsed_doc = ParsedDoc(
            text="This is a test document with some content that should be chunked properly.",
            format="markdown",
            metadata={
                "canonical_url": "https://test.com/doc",
                "source": "test"
            }
        )

        chunks = chunker.process(parsed_doc)

        assert len(chunks) > 0
        assert all(isinstance(chunk, dict) for chunk in chunks)
        assert all("text" in chunk for chunk in chunks)
        assert all("payload" in chunk for chunk in chunks)

        # Проверяем payload
        for i, chunk in enumerate(chunks):
            payload = chunk["payload"]
            assert "chunk_id" in payload
            assert "chunk_index" in payload
            assert "total_chunks" in payload
            assert payload["chunk_index"] == i
            assert payload["total_chunks"] == len(chunks)

    def test_chunker_empty_document(self):
        """Тест обработки пустого документа"""
        chunker = UnifiedChunkerStep()

        parsed_doc = ParsedDoc(text="", format="text")
        chunks = chunker.process(parsed_doc)

        assert len(chunks) == 0

    def test_chunker_error_handling(self):
        """Тест обработки ошибок в чанкере"""
        chunker = UnifiedChunkerStep()

        # Тест с невалидными данными
        chunks = chunker.process("not a ParsedDoc")
        assert chunks == []

        # Тест с None
        chunks = chunker.process(None)
        assert chunks == []


class TestEmbedder:
    """Тесты для Embedder"""

    @patch('ingestion.pipeline.embedder.embed_batch_optimized')
    def test_embedder_creation(self, mock_embed):
        """Тест создания эмбеддера"""
        embedder = Embedder(batch_size=8)

        assert embedder.batch_size == 8
        assert embedder.get_step_name() == "embedder"
        assert isinstance(embedder.stats, dict)

    @patch('ingestion.pipeline.embedder.embed_batch_optimized')
    def test_embedder_process_chunks(self, mock_embed):
        """Тест обработки чанков"""
        # Настраиваем мок
        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024, [0.2] * 1024],
            'lexical_weights': [{"1": 0.5}, {"2": 0.3}]
        }

        embedder = Embedder(batch_size=2)

        # Создаем тестовые чанки
        chunks = [
            {"text": "Test content 1", "payload": {"chunk_id": "doc1#0"}},
            {"text": "Test content 2", "payload": {"chunk_id": "doc2#0"}}
        ]

        # Обрабатываем чанки
        embedded_chunks = embedder.process(chunks)

        # Проверяем результат
        assert len(embedded_chunks) == 2

        for chunk in embedded_chunks:
            assert "payload" in chunk
            assert "dense_vector" in chunk["payload"]
            assert "sparse_data" in chunk["payload"]
            assert chunk["payload"]["embedded"] is True

        # Проверяем, что эмбеддинги были созданы
        mock_embed.assert_called_once()

    @patch('ingestion.pipeline.embedder.embed_batch_optimized')
    def test_embedder_error_handling(self, mock_embed):
        """Тест обработки ошибок в эмбеддере"""
        # Настраиваем мок для ошибки
        mock_embed.side_effect = Exception("Embedding error")

        embedder = Embedder(batch_size=2)

        chunks = [
            {"text": "Test content", "payload": {"chunk_id": "doc1#0"}}
        ]

        # Обрабатываем чанки (должны получить fallback векторы)
        embedded_chunks = embedder.process(chunks)

        # Проверяем, что получили fallback векторы
        assert len(embedded_chunks) == 1
        assert embedded_chunks[0]["payload"]["dense_vector"] == [0.0] * 1024
        assert embedded_chunks[0]["payload"]["sparse_data"] == {}


if __name__ == "__main__":
    pytest.main([__file__])
