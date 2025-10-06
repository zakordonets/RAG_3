"""
Unified chunker that combines all chunking strategies.
Provides intelligent strategy selection and fallbacks.
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from abc import ABC, abstractmethod
from loguru import logger

from app.config import CONFIG
from app.tokenizer import count_tokens
from .adaptive_chunker import adaptive_chunk_text
from .semantic_chunker import chunk_text_semantic
import hashlib


# Utility functions
def text_hash(text: str) -> str:
    """Compute hash for text deduplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def is_jina_reader_text(text: str) -> bool:
    """
    Detect if text is from Jina Reader.

    Args:
        text: Text to check

    Returns:
        True if text is from Jina Reader
    """
    if not text:
        return False

    # Characteristic markers of Jina Reader text
    jina_markers = [
        "Title:",
        "URL Source:",
        "Markdown Content:",
        "\n\nURL Source: http"
    ]

    text_start = text[:500]  # Check only beginning of text
    return any(marker in text_start for marker in jina_markers)


def preprocess_jina_text(text: str) -> str:
    """
    Preprocess Jina Reader text by removing metadata.

    Args:
        text: Raw Jina Reader text

    Returns:
        Cleaned text without metadata
    """
    lines = text.split('\n')
    processed_lines = []

    skip_next = False
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        line = line.strip()

        # Skip Jina Reader metadata
        if line.startswith(('Title:', 'URL Source:')):
            continue

        # Skip "Markdown Content:" and next empty line
        if line == 'Markdown Content:':
            skip_next = True
            continue

        # Skip navigation elements
        if (line.startswith(('*   [', '[Skip to main content]', 'ctrl K', 'On this page')) or
            line.startswith(('[Previous ', '[Next ')) or
            line.startswith('[![Image')):
            continue

        # Skip separators
        if line.startswith('===') or line.startswith('---') or line == '===============':
            continue

        # Skip very short lines (usually garbage)
        if len(line.split()) < 3 and not any(char.isalnum() for char in line):
            continue

        if line:
            processed_lines.append(line)

    result = '\n\n'.join(processed_lines)
    logger.debug(f"Preprocessed Jina text: {len(text)} -> {len(result)} chars")
    return result


def deduplicate_chunks(chunks: List[str]) -> List[str]:
    """Remove duplicate chunks."""
    seen = set()
    unique_chunks = []

    for chunk in chunks:
        chunk_hash = text_hash(chunk)
        if chunk_hash not in seen:
            seen.add(chunk_hash)
            unique_chunks.append(chunk)

    return unique_chunks


class BaseChunker(ABC):
    """Base interface for all chunkers."""

    @abstractmethod
    def chunk_text(self, text: str, **kwargs) -> List[str]:
        """
        Chunk text into segments.

        Args:
            text: Input text to chunk
            **kwargs: Additional parameters

        Returns:
            List of text chunks
        """
        pass

    @abstractmethod
    def chunk_with_metadata(self, text: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Chunk text with metadata.

        Args:
            text: Input text to chunk
            metadata: Optional metadata to include
            **kwargs: Additional parameters

        Returns:
            List of chunks with metadata
        """
        pass


class ChunkingStrategy(Enum):
    """Available chunking strategies."""
    SIMPLE = "simple"
    ADAPTIVE = "adaptive"
    SEMANTIC = "semantic"
    AUTO = "auto"


class UnifiedChunker(BaseChunker):
    """
    Unified chunker that intelligently selects the best chunking strategy.
    """

    def __init__(self, default_strategy: ChunkingStrategy = ChunkingStrategy.AUTO):
        """
        Initialize unified chunker.

        Args:
            default_strategy: Default strategy to use
        """
        self.default_strategy = default_strategy
        self.strategies = {
            ChunkingStrategy.SIMPLE: self._chunk_simple,
            ChunkingStrategy.ADAPTIVE: self._chunk_adaptive,
            ChunkingStrategy.SEMANTIC: self._chunk_semantic,
            ChunkingStrategy.AUTO: self._chunk_auto
        }

        logger.info(f"UnifiedChunker initialized with strategy: {default_strategy.value}")

    def chunk_text(self, text: str, strategy: Optional[ChunkingStrategy] = None, **kwargs) -> List[str]:
        """
        Chunk text using specified or default strategy.

        Args:
            text: Input text to chunk
            strategy: Chunking strategy to use
            **kwargs: Additional parameters

        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []

        strategy = strategy or self.default_strategy
        chunker_func = self.strategies.get(strategy, self._chunk_auto)

        try:
            logger.debug(f"Using chunking strategy: {strategy.value}")
            chunks = chunker_func(text, **kwargs)

            if chunks:
                logger.debug(f"Chunking successful: {len(chunks)} chunks created")
                return chunks
            else:
                logger.warning(f"Chunking failed with strategy {strategy.value}, trying fallback")
                return self._chunk_simple(text, **kwargs)

        except Exception as e:
            logger.error(f"Error in chunking with strategy {strategy.value}: {e}")
            return self._chunk_simple(text, **kwargs)

    def chunk_with_metadata(self, text: str, metadata: Optional[Dict[str, Any]] = None,
                           strategy: Optional[ChunkingStrategy] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Chunk text with metadata.

        Args:
            text: Input text to chunk
            metadata: Optional metadata to include
            strategy: Chunking strategy to use
            **kwargs: Additional parameters

        Returns:
            List of chunks with metadata
        """
        if not text or not text.strip():
            return []

        # Use adaptive chunker for metadata support
        strategy = strategy or ChunkingStrategy.ADAPTIVE

        if strategy == ChunkingStrategy.ADAPTIVE:
            try:
                return adaptive_chunk_text(text, metadata)
            except Exception as e:
                logger.error(f"Error in adaptive chunking: {e}")
                # Fallback to simple chunking with metadata
                chunks = self._chunk_simple(text, **kwargs)
                return [{'content': chunk, 'metadata': metadata or {}} for chunk in chunks]
        else:
            # For other strategies, add metadata manually
            chunks = self.chunk_text(text, strategy, **kwargs)
            return [{'content': chunk, 'metadata': metadata or {}} for chunk in chunks]

    def _chunk_simple(self, text: str, **kwargs) -> List[str]:
        """Use simple chunking strategy."""
        try:
            min_tokens = kwargs.get('min_tokens', CONFIG.chunk_min_tokens)
            max_tokens = kwargs.get('max_tokens', CONFIG.chunk_max_tokens)
            return _chunk_text_simple(text, min_tokens, max_tokens)
        except Exception as e:
            logger.error(f"Error in simple chunking: {e}")
            return []

    def _chunk_adaptive(self, text: str, **kwargs) -> List[str]:
        """Use adaptive chunking strategy."""
        try:
            chunks_with_metadata = adaptive_chunk_text(text, **kwargs)
            return [chunk['content'] for chunk in chunks_with_metadata]
        except Exception as e:
            logger.error(f"Error in adaptive chunking: {e}")
            return self._chunk_simple(text, **kwargs)

    def _chunk_semantic(self, text: str, **kwargs) -> List[str]:
        """Use semantic chunking strategy."""
        try:
            use_overlap = kwargs.get('use_overlap', False)
            return chunk_text_semantic(text, use_overlap=use_overlap)
        except Exception as e:
            logger.error(f"Error in semantic chunking: {e}")
            return self._chunk_simple(text, **kwargs)

    def _chunk_auto(self, text: str, **kwargs) -> List[str]:
        """
        Automatically select best chunking strategy based on text characteristics.
        """
        try:
            # Analyze text characteristics
            text_length = len(text)
            word_count = len(text.split())
            is_jina = is_jina_reader_text(text)

            logger.debug(f"Text analysis: length={text_length}, words={word_count}, is_jina={is_jina}")

            # Strategy selection logic
            if is_jina:
                # Jina Reader text - use simple chunker
                logger.debug("Detected Jina Reader text, using simple chunker")
                return self._chunk_simple(text, **kwargs)

            elif word_count < 300:
                # Short text - use simple chunker
                logger.debug("Short text detected, using simple chunker")
                return self._chunk_simple(text, **kwargs)

            elif word_count > 1000:
                # Long text - try semantic, fallback to adaptive
                logger.debug("Long text detected, trying semantic chunker")
                try:
                    chunks = self._chunk_semantic(text, **kwargs)
                    if chunks and len(chunks) > 1:
                        return chunks
                except Exception:
                    pass

                logger.debug("Semantic failed, using adaptive chunker")
                return self._chunk_adaptive(text, **kwargs)

            else:
                # Medium text - try semantic first, then adaptive
                logger.debug("Medium text detected, trying semantic chunker")
                try:
                    chunks = self._chunk_semantic(text, **kwargs)
                    if chunks:
                        return chunks
                except Exception:
                    pass

                logger.debug("Semantic failed, using adaptive chunker")
                return self._chunk_adaptive(text, **kwargs)

        except Exception as e:
            logger.error(f"Error in auto chunking: {e}")
            return self._chunk_simple(text, **kwargs)

    def chunk_with_overlap(self, text: str, strategy: Optional[ChunkingStrategy] = None, **kwargs) -> List[str]:
        """
        Chunk text with overlap support.

        Args:
            text: Input text to chunk
            strategy: Chunking strategy to use
            **kwargs: Additional parameters

        Returns:
            List of chunks with overlap
        """
        if not text or not text.strip():
            return []

        strategy = strategy or self.default_strategy

        # Set overlap flag
        kwargs['use_overlap'] = True

        if strategy == ChunkingStrategy.SEMANTIC:
            return self._chunk_semantic(text, **kwargs)
        elif strategy == ChunkingStrategy.SIMPLE:
            try:
                return chunk_text_with_overlap(text, **kwargs)
            except Exception as e:
                logger.error(f"Error in simple chunking with overlap: {e}")
                return self._chunk_simple(text, **kwargs)
        else:
            # For adaptive and auto, use simple with overlap as fallback
            try:
                return chunk_text_with_overlap(text, **kwargs)
            except Exception as e:
                logger.error(f"Error in overlap chunking: {e}")
                return self._chunk_simple(text, **kwargs)


# Global instance
_unified_chunker = None


def get_unified_chunker() -> UnifiedChunker:
    """Get global unified chunker instance."""
    global _unified_chunker
    if _unified_chunker is None:
        _unified_chunker = UnifiedChunker()
    return _unified_chunker


def chunk_text(text: str, strategy: Optional[Union[str, ChunkingStrategy]] = None, **kwargs) -> List[str]:
    """
    Convenience function for text chunking.

    Args:
        text: Input text to chunk
        strategy: Strategy name or enum
        **kwargs: Additional parameters

    Returns:
        List of text chunks
    """
    if isinstance(strategy, str):
        try:
            strategy = ChunkingStrategy(strategy.lower())
        except ValueError:
            logger.warning(f"Unknown strategy '{strategy}', using auto")
            strategy = ChunkingStrategy.AUTO

    chunker = get_unified_chunker()
    return chunker.chunk_text(text, strategy, **kwargs)


def chunk_text_with_metadata(text: str, metadata: Optional[Dict[str, Any]] = None,
                            strategy: Optional[Union[str, ChunkingStrategy]] = None, **kwargs) -> List[Dict[str, Any]]:
    """
    Convenience function for chunking with metadata.

    Args:
        text: Input text to chunk
        metadata: Optional metadata
        strategy: Strategy name or enum
        **kwargs: Additional parameters

    Returns:
        List of chunks with metadata
    """
    if isinstance(strategy, str):
        try:
            strategy = ChunkingStrategy(strategy.lower())
        except ValueError:
            logger.warning(f"Unknown strategy '{strategy}', using adaptive")
            strategy = ChunkingStrategy.ADAPTIVE

    chunker = get_unified_chunker()
    return chunker.chunk_with_metadata(text, metadata, strategy, **kwargs)


# Уникальные функции из simple_chunker
def _split_large_paragraph(paragraph: str, min_tokens: int, max_tokens: int,
                          optimal_min: int, optimal_max: int) -> List[str]:
    """
    Разбивает большой параграф на оптимальные чанки.

    Args:
        paragraph: Большой параграф для разбиения
        min_tokens: Минимальный размер чанка
        max_tokens: Максимальный размер чанка
        optimal_min: Оптимальный минимум
        optimal_max: Оптимальный максимум

    Returns:
        Список чанков
    """
    sentences = _split_paragraph_into_sentences(paragraph)

    if not sentences:
        return []

    chunks = []
    current_chunk = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)

        # Если предложение само по себе слишком большое
        if sentence_tokens > max_tokens:
            # Завершаем текущий чанк
            if current_chunk and current_tokens >= min_tokens:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            # Разбиваем предложение по словам
            words = sentence.split()
            for i in range(0, len(words), max_tokens):
                chunk_words = words[i:i + max_tokens]
                if len(chunk_words) >= min_tokens or not chunks:
                    chunks.append(" ".join(chunk_words))
            continue

        # Проверяем, поместится ли предложение
        if current_tokens + sentence_tokens <= optimal_max:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
        else:
            # Завершаем текущий чанк если он достаточно большой
            if current_tokens >= min_tokens:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                # Текущий чанк слишком маленький, добавляем предложение принудительно
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

    # Добавляем последний чанк
    if current_chunk:
        if current_tokens >= min_tokens:
            chunks.append(" ".join(current_chunk))
        elif chunks:
            chunks[-1] += " " + " ".join(current_chunk)
        else:
            chunks.append(" ".join(current_chunk))

    return chunks


def _split_paragraph_into_sentences(paragraph: str) -> List[str]:
    """
    Разбивает параграф на предложения.

    Args:
        paragraph: Параграф для разбиения

    Returns:
        Список предложений
    """
    import re

    # Простое разбиение по знакам препинания
    # Учитываем особенности русского языка
    sentence_endings = r'[.!?]+(?:\s|$)'
    sentences = re.split(sentence_endings, paragraph)

    # Очищаем и фильтруем пустые предложения
    sentences = [s.strip() for s in sentences if s.strip()]

    # Если не удалось разбить, возвращаем по фразам (разделенным запятыми)
    if len(sentences) <= 1:
        sentences = [s.strip() for s in paragraph.split(',') if s.strip()]

    # В крайнем случае разбиваем по словам (группы по 50 слов)
    if len(sentences) <= 1:
        words = paragraph.split()
        sentences = []
        for i in range(0, len(words), 50):
            chunk_words = words[i:i+50]
            sentences.append(' '.join(chunk_words))

    return sentences


def _chunk_text_simple(text: str, min_tokens: int, max_tokens: int) -> List[str]:
    """
    Оптимальный chunker по абзацам с интеллектуальным разбиением.

    Стратегия:
    1. Сохраняет целостность абзацев когда возможно
    2. Создает чанки оптимального размера (70-90% от max_tokens)
    3. Разбивает большие абзацы по предложениям
    4. Объединяет маленькие абзацы в оптимальные чанки
    """

    # Предварительная обработка для Jina Reader текста
    if is_jina_reader_text(text):
        text = preprocess_jina_text(text)
        logger.debug("Preprocessed Jina Reader text")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Фильтруем слишком короткие параграфы
    paragraphs = [p for p in paragraphs if len(p.split()) >= 5]

    if not paragraphs:
        return []

    # Оптимальные размеры чанков для BGE-M3 (512 токенов ±20%)
    optimal_min = max(min_tokens, int(max_tokens * 0.8))  # 80% от максимума = 491 токенов
    optimal_max = int(max_tokens * 1.0)  # 100% от максимума = 614 токенов

    chunks = []
    current_chunk_paragraphs = []
    current_chunk_tokens = 0

    logger.debug(f"Chunking {len(paragraphs)} paragraphs with optimal range {optimal_min}-{optimal_max} tokens")

    for i, paragraph in enumerate(paragraphs):
        paragraph_tokens = count_tokens(paragraph)

        # Случай 1: Параграф слишком большой - разбиваем его
        if paragraph_tokens > max_tokens:
            logger.debug(f"Large paragraph ({paragraph_tokens} tokens) - splitting")

            # Сначала завершаем текущий чанк, если есть
            if current_chunk_paragraphs and current_chunk_tokens >= min_tokens:
                chunks.append("\n\n".join(current_chunk_paragraphs))
                current_chunk_paragraphs = []
                current_chunk_tokens = 0

            # Разбиваем большой параграф
            paragraph_chunks = _split_large_paragraph(paragraph, min_tokens, max_tokens, optimal_min, optimal_max)
            chunks.extend(paragraph_chunks)
            continue

        # Случай 2: Параграф помещается в текущий чанк
        if current_chunk_tokens + paragraph_tokens <= optimal_max:
            current_chunk_paragraphs.append(paragraph)
            current_chunk_tokens += paragraph_tokens

            # Проверяем, достигли ли оптимального размера
            if current_chunk_tokens >= optimal_min:
                # Смотрим вперед - если следующий параграф не поместится, завершаем чанк
                next_paragraph_tokens = 0
                if i + 1 < len(paragraphs):
                    next_paragraph_tokens = count_tokens(paragraphs[i + 1])

                # Оптимальное завершение чанков для BGE-M3
                should_finish = (
                    current_chunk_tokens + next_paragraph_tokens > optimal_max or  # Следующий не поместится
                    current_chunk_tokens >= optimal_max * 0.9 or  # Достигли 90% от оптимального максимума
                    i == len(paragraphs) - 1  # Последний параграф
                )

                if should_finish:
                    chunks.append("\n\n".join(current_chunk_paragraphs))
                    current_chunk_paragraphs = []
                    current_chunk_tokens = 0

        # Случай 3: Параграф не помещается - завершаем текущий чанк и начинаем новый
        else:
            if current_chunk_paragraphs and current_chunk_tokens >= min_tokens:
                chunks.append("\n\n".join(current_chunk_paragraphs))

            # Начинаем новый чанк с текущего параграфа
            current_chunk_paragraphs = [paragraph]
            current_chunk_tokens = paragraph_tokens

    # Добавляем последний чанк
    if current_chunk_paragraphs:
        if current_chunk_tokens >= min_tokens:
            chunks.append("\n\n".join(current_chunk_paragraphs))
        elif chunks:
            # Добавляем к предыдущему чанку если слишком маленький
            chunks[-1] += "\n\n" + "\n\n".join(current_chunk_paragraphs)
        else:
            # Единственный чанк, даже если маленький
            chunks.append("\n\n".join(current_chunk_paragraphs))

    # Quality gates: дедупликация
    chunks = deduplicate_chunks(chunks)

    if chunks:
        avg_size = sum(len(chunk.split()) for chunk in chunks) / len(chunks)
        logger.debug(f"Optimal chunker produced {len(chunks)} chunks, avg size: {avg_size:.0f} tokens")
        return chunks

    # Fallback
    logger.warning(f"Optimal chunker failed, using fallback")
    words = text.split()
    if len(words) >= max(min_tokens // 2, 40):
        return [" ".join(words[:max_tokens])]

    return []
