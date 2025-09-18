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
from app.gpu_utils import get_device, optimize_for_gpu


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
                # Чанк заполнен, сохраняем его
                if current_tokens >= self.min_chunk_size:
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
                if current_tokens >= self.min_chunk_size:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens

        # Добавляем последний чанк
        if current_chunk and current_tokens >= self.min_chunk_size:
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
                if current_tokens >= self.min_chunk_size:
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
                if current_tokens >= self.min_chunk_size:
                    chunks.append('\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_tokens = paragraph_tokens

        # Добавляем последний чанк
        if current_chunk and current_tokens >= self.min_chunk_size:
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
            return []

        # Сначала пробуем разбить по абзацам
        paragraphs = self._split_into_paragraphs(text)

        # Если абзацы слишком большие, разбиваем по предложениям
        if any(self._estimate_tokens(p) > self.max_chunk_size for p in paragraphs):
            logger.debug("Using sentence-based chunking due to large paragraphs")
            sentences = []
            for paragraph in paragraphs:
                sentences.extend(self._split_into_sentences(paragraph))
            chunks = self._create_chunks_from_sentences(sentences)
        else:
            logger.debug("Using paragraph-based chunking")
            chunks = self._create_chunks_from_paragraphs(paragraphs)

        # Применяем quality gates
        chunks = self._apply_quality_gates(chunks)

        return chunks

    def _apply_quality_gates(self, chunks: List[str]) -> List[str]:
        """Применяет quality gates к чанкам."""
        # Удаляем пустые чанки
        chunks = [chunk for chunk in chunks if chunk.strip()]

        # Дедупликация
        seen = set()
        unique_chunks = []
        for chunk in chunks:
            chunk_hash = hashlib.sha256(chunk.strip().encode("utf-8")).hexdigest()
            if chunk_hash not in seen:
                seen.add(chunk_hash)
                unique_chunks.append(chunk)

        # Проверяем минимальный размер
        filtered_chunks = []
        for chunk in unique_chunks:
            tokens = self._estimate_tokens(chunk)
            if tokens >= self.min_chunk_size:
                filtered_chunks.append(chunk)
            else:
                logger.debug(f"Chunk too small ({tokens} tokens), skipping")

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
            min_chunk_size=CONFIG.chunk_min_tokens,
            max_chunk_size=CONFIG.chunk_max_tokens
        )
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
