"""
Unified chunking system for RAG pipeline.
Provides multiple chunking strategies with intelligent fallbacks.
"""

from typing import List
from .unified_chunker import (
    UnifiedChunker,
    chunk_text,
    chunk_text_with_metadata,
    ChunkingStrategy
)
from .unified_chunker import text_hash

# Backward compatibility functions
def chunk_text_with_overlap(text: str, **kwargs) -> List[str]:
    """Chunk text with overlap support."""
    from .unified_chunker import get_unified_chunker
    chunker = get_unified_chunker()
    return chunker.chunk_with_overlap(text, **kwargs)

__all__ = [
    'UnifiedChunker',
    'chunk_text',
    'chunk_text_with_metadata',
    'chunk_text_with_overlap',
    'ChunkingStrategy',
    'text_hash'
]
