"""
Пакет чанкинга для универсальной обработки документов
"""

from .universal_chunker import (
    UniversalChunker,
    Chunk,
    Block,
    OversizePolicy,
    chunk_text_universal,
    get_universal_chunker
)

__all__ = [
    'UniversalChunker',
    'Chunk',
    'Block',
    'OversizePolicy',
    'chunk_text_universal',
    'get_universal_chunker'
]
