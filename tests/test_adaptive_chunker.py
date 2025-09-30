#!/usr/bin/env python3
"""
Тесты для адаптивного чанкера
"""

import pytest
from unittest.mock import patch, MagicMock
from ingestion.adaptive_chunker import (
    AdaptiveChunker,
    DocumentType,
    ChunkingStrategy
)


class TestAdaptiveChunker:
    """Тесты для класса AdaptiveChunker"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.chunker = AdaptiveChunker()
    
    def test_chunker_initialization(self):
        """Тест инициализации чанкера"""
        chunker = AdaptiveChunker()
        assert chunker is not None
        assert chunker.strategies is not None
        assert DocumentType.SHORT in chunker.strategies
        assert DocumentType.MEDIUM in chunker.strategies
        assert DocumentType.LONG in chunker.strategies
    
    def test_classify_document_type_short(self):
        """Тест классификации коротких документов"""
        short_text = "This is a short text."
        doc_type = self.chunker._classify_document_type(short_text)
        assert doc_type == DocumentType.SHORT
    
    def test_classify_document_type_medium(self):
        """Тест классификации средних документов"""
        # Создаем текст средней длины (больше слов для токенайзера)
        medium_text = " ".join(["word"] * 500)
        doc_type = self.chunker._classify_document_type(medium_text)
        assert doc_type == DocumentType.MEDIUM
    
    def test_classify_document_type_long(self):
        """Тест классификации длинных документов"""
        # Создаем длинный текст
        long_text = " ".join(["word"] * 1000)
        doc_type = self.chunker._classify_document_type(long_text)
        assert doc_type == DocumentType.LONG
    
    def test_chunk_short_document(self):
        """Тест обработки коротких документов"""
        text = "This is a short document."
        metadata = {"source": "test"}
        
        chunks = self.chunker._chunk_short_document(text, metadata)
        
        assert len(chunks) == 1
        assert chunks[0]['content'] == text.strip()
        assert chunks[0]['metadata']['chunk_type'] == 'short_document'
        assert chunks[0]['metadata']['source'] == "test"
        assert chunks[0]['metadata']['is_complete_document'] is True
    
    def test_chunk_medium_document(self):
        """Тест обработки средних документов"""
        # Создаем текст средней длины
        text = " ".join(["This is a medium document with multiple sentences."] * 50)
        metadata = {"source": "test"}
        
        # Создаем стратегию для средних документов
        strategy = ChunkingStrategy(
            use_structural=True,
            use_sliding_window=True,
            chunk_size=512,
            overlap=100
        )
        
        chunks = self.chunker._chunk_medium_document(text, metadata, strategy)
        
        assert len(chunks) >= 1
        for chunk in chunks:
            assert 'content' in chunk
            assert 'metadata' in chunk
            assert chunk['metadata']['chunk_type'] == 'medium_document'
    
    def test_chunk_long_document(self):
        """Тест обработки длинных документов"""
        # Создаем длинный текст
        text = " ".join(["This is a long document with many sentences."] * 200)
        metadata = {"source": "test"}
        
        # Создаем стратегию для длинных документов
        strategy = ChunkingStrategy(
            use_structural=True,
            use_sliding_window=True,
            chunk_size=800,
            overlap=160
        )
        
        chunks = self.chunker._chunk_long_document(text, metadata, strategy)
        
        assert len(chunks) >= 1
        for chunk in chunks:
            assert 'content' in chunk
            assert 'metadata' in chunk
            assert chunk['metadata']['chunk_type'] == 'long_document'
    
    def test_chunk_with_empty_text(self):
        """Тест обработки пустого текста"""
        chunks = self.chunker.chunk_text("", {})
        assert chunks == []
        
        chunks = self.chunker.chunk_text(None, {})
        assert chunks == []
    
    def test_chunk_with_whitespace_only(self):
        """Тест обработки текста только с пробелами"""
        chunks = self.chunker.chunk_text("   \n\n   ", {})
        assert chunks == []


if __name__ == "__main__":
    pytest.main([__file__])