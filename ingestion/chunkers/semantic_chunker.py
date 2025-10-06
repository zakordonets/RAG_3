"""
Семантический chunker для улучшенного разбиения текста.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, List, Tuple
import numpy as np
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("SentenceTransformers not available, using fallback chunker")

from app.config import CONFIG
from app.hardware import get_device, optimize_for_gpu


class SemanticChunker:
    """
    Семантический chunker, который разбивает текст на основе семантического сходства.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        similarity_threshold: float = 0.7,
        min_chunk_size: int = 80,
        max_chunk_size: int = 600,
        overlap_size: int = 50
    ):
        """
        Инициализация семантического chunker.

        Args:
            model_name: Название модели для вычисления эмбеддингов
            similarity_threshold: Порог сходства для объединения предложений
            min_chunk_size: Минимальный размер чанка в токенах
            max_chunk_size: Максимальный размер чанка в токенах
            overlap_size: Размер перекрытия между чанками
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size

        self.model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                device = get_device()
                logger.info(f"Loading semantic chunker model: {model_name} on {device}...")

                # Для DirectML используем CPU, так как SentenceTransformer не поддерживает DirectML напрямую
                if device == "dml":
                    logger.info("DirectML detected, using CPU for semantic chunker (SentenceTransformer doesn't support DirectML)")
                    device = "cpu"

                self.model = SentenceTransformer(model_name, device=device)

                # Оптимизируем для GPU если доступно
                if device.startswith('cuda'):
                    self.model = optimize_for_gpu(self.model, device)
                    logger.info(f"Semantic chunker optimized for GPU: {device}")

                logger.info(f"Semantic chunker initialized with model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to load model {model_name}: {e}")
                self.model = None
        else:
            logger.warning("SentenceTransformers not available, using fallback chunker")

    def _split_into_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения."""
        # Простое разбиение по знакам препинания
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Разбивает текст на абзацы."""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return paragraphs

    def _compute_similarity(self, sentence1: str, sentence2: str) -> float:
        """Вычисляет семантическое сходство между предложениями."""
        if not self.model:
            # Fallback: простое сходство по словам
            words1 = set(sentence1.lower().split())
            words2 = set(sentence2.lower().split())
            if not words1 or not words2:
                return 0.0
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            return intersection / union if union > 0 else 0.0

        try:
            embeddings = self.model.encode([sentence1, sentence2])
            # Косинусное сходство
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception as e:
            logger.warning(f"Error computing similarity: {e}")
            return 0.0

    def _estimate_tokens(self, text: str) -> int:
        """Оценивает количество токенов в тексте."""
        # Простая оценка: ~1 токен = 1 слово
        return len(text.split())

    def _create_chunks_from_sentences(self, sentences: List[str]) -> List[str]:
        """Создает чанки из предложений на основе семантического сходства."""
        if not sentences:
            return []

        chunks = []
        current_chunk = [sentences[0]]
        current_tokens = self._estimate_tokens(sentences[0])

        for i in range(1, len(sentences)):
            sentence = sentences[i]
            sentence_tokens = self._estimate_tokens(sentence)

            # Проверяем, поместится ли предложение в текущий чанк
            if current_tokens + sentence_tokens > self.max_chunk_size:
                # Чанк заполнен, сохраняем его (quality gates отфильтруют позже)
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens
                continue

            # Вычисляем сходство с предыдущим предложением
            similarity = self._compute_similarity(sentences[i-1], sentence)

            if similarity > self.similarity_threshold:
                # Предложения семантически похожи, объединяем
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
            else:
                # Предложения разные, начинаем новый чанк
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens

        # Добавляем последний чанк (всегда, quality gates отфильтруют позже)
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _create_chunks_from_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """Создает чанки из абзацев с учетом семантического сходства."""
        if not paragraphs:
            return []

        chunks = []
        current_chunk = [paragraphs[0]]
        current_tokens = self._estimate_tokens(paragraphs[0])

        for i in range(1, len(paragraphs)):
            paragraph = paragraphs[i]
            paragraph_tokens = self._estimate_tokens(paragraph)

            # Проверяем размер
            if current_tokens + paragraph_tokens > self.max_chunk_size:
                # Сохраняем чанк даже если он меньше минимального (quality gates отфильтруют позже)
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_tokens = paragraph_tokens
                continue

            # Вычисляем сходство между абзацами
            similarity = self._compute_similarity(paragraphs[i-1], paragraph)

            if similarity > self.similarity_threshold:
                current_chunk.append(paragraph)
                current_tokens += paragraph_tokens
            else:
                # Сохраняем чанк даже если он меньше минимального
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_tokens = paragraph_tokens

        # Добавляем последний чанк (всегда, quality gates отфильтруют позже)
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

    def chunk_text(self, text: str) -> List[str]:
        """
        Разбивает текст на семантически связанные чанки.

        Args:
            text: Исходный текст для разбиения

        Returns:
            Список чанков
        """
        if not text or not text.strip():
            logger.debug("Empty text provided to semantic chunker")
            return []

        text_tokens = self._estimate_tokens(text)
        logger.debug(f"Semantic chunker: processing text with {text_tokens} tokens")

        # Сначала пробуем разбить по абзацам
        paragraphs = self._split_into_paragraphs(text)
        logger.debug(f"Split into {len(paragraphs)} paragraphs")

        # Если абзацы слишком большие, разбиваем по предложениям
        large_paragraphs = [p for p in paragraphs if self._estimate_tokens(p) > self.max_chunk_size]
        if large_paragraphs:
            logger.debug(f"Using sentence-based chunking due to {len(large_paragraphs)} large paragraphs")
            sentences = []
            for paragraph in paragraphs:
                sentences.extend(self._split_into_sentences(paragraph))
            logger.debug(f"Split into {len(sentences)} sentences")
            chunks = self._create_chunks_from_sentences(sentences)
        else:
            logger.debug("Using paragraph-based chunking")
            chunks = self._create_chunks_from_paragraphs(paragraphs)

        logger.debug(f"Created {len(chunks)} chunks before quality gates")

        # Применяем quality gates
        chunks = self._apply_quality_gates(chunks)

        logger.debug(f"Final result: {len(chunks)} chunks after quality gates")
        if not chunks:
            logger.warning(f"Semantic chunker produced no chunks from {text_tokens} tokens of text")

        return chunks

    def _apply_quality_gates(self, chunks: List[str]) -> List[str]:
        """Применяет quality gates к чанкам."""
        logger.debug(f"Quality gates: starting with {len(chunks)} chunks")

        # Удаляем пустые чанки
        non_empty = [chunk for chunk in chunks if chunk.strip()]
        logger.debug(f"Quality gates: {len(non_empty)} non-empty chunks (removed {len(chunks) - len(non_empty)})")

        # Дедупликация
        seen = set()
        unique_chunks = []
        for chunk in non_empty:
            chunk_hash = hashlib.sha256(chunk.strip().encode("utf-8")).hexdigest()
            if chunk_hash not in seen:
                seen.add(chunk_hash)
                unique_chunks.append(chunk)

        duplicates_removed = len(non_empty) - len(unique_chunks)
        if duplicates_removed > 0:
            logger.debug(f"Quality gates: {len(unique_chunks)} unique chunks (removed {duplicates_removed} duplicates)")

        # Проверяем минимальный размер (более мягкая проверка)
        filtered_chunks = []
        too_small_count = 0
        min_size_soft = max(self.min_chunk_size // 2, 20)  # Мягкий минимум

        for chunk in unique_chunks:
            tokens = self._estimate_tokens(chunk)
            if tokens >= min_size_soft:  # Используем мягкий минимум
                filtered_chunks.append(chunk)
            else:
                too_small_count += 1
                logger.debug(f"Chunk too small ({tokens} < {min_size_soft} tokens), skipping: '{chunk[:100]}...'")

        if too_small_count > 0:
            logger.debug(f"Quality gates: {len(filtered_chunks)} chunks passed size filter (removed {too_small_count} too small)")

        # Если все чанки слишком маленькие, возвращаем хотя бы один
        if not filtered_chunks and unique_chunks:
            logger.warning(f"All chunks too small, returning the largest one")
            largest_chunk = max(unique_chunks, key=lambda x: self._estimate_tokens(x))
            filtered_chunks = [largest_chunk]

        return filtered_chunks

    def chunk_with_overlap(self, text: str) -> List[str]:
        """
        Создает чанки с перекрытием для лучшего контекста.

        Args:
            text: Исходный текст

        Returns:
            Список чанков с перекрытием
        """
        chunks = self.chunk_text(text)

        if len(chunks) <= 1:
            return chunks

        overlapped_chunks = []
        for i, chunk in enumerate(chunks):
            overlapped_chunks.append(chunk)

            # Добавляем перекрытие с предыдущим чанком
            if i > 0:
                prev_chunk = chunks[i-1]
                prev_words = prev_chunk.split()
                overlap_words = prev_words[-self.overlap_size:] if len(prev_words) > self.overlap_size else prev_words

                if overlap_words:
                    overlap_text = ' '.join(overlap_words)
                    overlapped_chunk = f"{overlap_text} {chunk}"

                    # Проверяем, что перекрытый чанк не превышает максимальный размер
                    if self._estimate_tokens(overlapped_chunk) <= self.max_chunk_size:
                        overlapped_chunks[-1] = overlapped_chunk

        return overlapped_chunks


# Глобальный экземпляр chunker
_semantic_chunker = None


def get_semantic_chunker() -> SemanticChunker:
    """Получает глобальный экземпляр семантического chunker."""
    global _semantic_chunker
    if _semantic_chunker is None:
        _semantic_chunker = SemanticChunker(
            min_chunk_size=max(CONFIG.chunk_min_tokens // 4, 30),  # Еще более мягкий минимум
            max_chunk_size=CONFIG.chunk_max_tokens,
            similarity_threshold=0.5  # Еще менее строгий порог сходства
        )
        logger.info(f"Semantic chunker initialized: min_size={_semantic_chunker.min_chunk_size}, "
                   f"max_size={_semantic_chunker.max_chunk_size}, threshold={_semantic_chunker.similarity_threshold}")
    return _semantic_chunker


def chunk_text_semantic(text: str, use_overlap: bool = False) -> List[str]:
    """
    Разбивает текст на семантически связанные чанки.

    Args:
        text: Исходный текст
        use_overlap: Использовать перекрытие между чанками

    Returns:
        Список чанков
    """
    chunker = get_semantic_chunker()

    if use_overlap:
        return chunker.chunk_with_overlap(text)
    else:
        return chunker.chunk_text(text)


def text_hash(text: str) -> str:
    """Вычисляет хэш текста для дедупликации."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
