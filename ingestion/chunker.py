from __future__ import annotations

import hashlib
from typing import Iterable
from loguru import logger
from app.config import CONFIG

# Импортируем семантический chunker
try:
    from ingestion.semantic_chunker import chunk_text_semantic, text_hash as semantic_text_hash
    SEMANTIC_CHUNKER_AVAILABLE = True
except ImportError:
    SEMANTIC_CHUNKER_AVAILABLE = False
    logger.warning("Semantic chunker not available, using fallback")


def text_hash(text: str) -> str:
    """Вычисляет хэш текста для дедупликации."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def chunk_text(text: str, min_tokens: int = None, max_tokens: int = None, use_semantic: bool = True) -> list[str]:
    """
    Разбивает текст на чанки с возможностью использования семантического chunker.

    Args:
        text: Исходный текст
        min_tokens: Минимальный размер чанка в токенах
        max_tokens: Максимальный размер чанка в токенах
        use_semantic: Использовать семантический chunker

    Returns:
        Список чанков
    """
    # Используем значения из конфигурации по умолчанию
    min_tokens = min_tokens or CONFIG.chunk_min_tokens
    max_tokens = max_tokens or CONFIG.chunk_max_tokens

    if not text or not text.strip():
        return []

    # Пробуем использовать семантический chunker
    if use_semantic and SEMANTIC_CHUNKER_AVAILABLE:
        try:
            logger.debug("Using semantic chunker")
            chunks = chunk_text_semantic(text, use_overlap=False)
            if chunks:
                logger.debug(f"Semantic chunker produced {len(chunks)} chunks")
                return chunks
            else:
                logger.warning("Semantic chunker returned no chunks, falling back to simple chunker")
        except Exception as e:
            logger.warning(f"Semantic chunker failed: {e}, falling back to simple chunker")

    # Fallback к простому chunker
    logger.debug("Using simple chunker")
    return _chunk_text_simple(text, min_tokens, max_tokens)


def _chunk_text_simple(text: str, min_tokens: int, max_tokens: int) -> list[str]:
    """Простой chunker по абзацам (fallback)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    count = 0

    for p in paragraphs:
        tokens = p.split()
        if count + len(tokens) <= max_tokens:
            cur.append(p)
            count += len(tokens)
        else:
            if count >= min_tokens:
                chunks.append("\n\n".join(cur))
            cur = [p]
            count = len(tokens)

    if cur and count >= min_tokens:
        chunks.append("\n\n".join(cur))

    # Quality gates: no-empty, dedup
    seen = set()
    uniq: list[str] = []
    for c in chunks:
        h = text_hash(c)
        if h in seen:
            continue
        seen.add(h)
        uniq.append(c)

    if uniq:
        return uniq

    # Fallback: если не удалось набрать достаточные чанки, создаём один усечённый чанк
    words = text.split()
    if len(words) >= max(min_tokens // 2, 40):
        return [" ".join(words[:max_tokens])]
    return []


def chunk_text_with_overlap(text: str, min_tokens: int = None, max_tokens: int = None) -> list[str]:
    """
    Разбивает текст на чанки с перекрытием.

    Args:
        text: Исходный текст
        min_tokens: Минимальный размер чанка в токенах
        max_tokens: Максимальный размер чанка в токенах

    Returns:
        Список чанков с перекрытием
    """
    min_tokens = min_tokens or CONFIG.chunk_min_tokens
    max_tokens = max_tokens or CONFIG.chunk_max_tokens

    if not text or not text.strip():
        return []

    # Используем семантический chunker с перекрытием
    if SEMANTIC_CHUNKER_AVAILABLE:
        try:
            logger.debug("Using semantic chunker with overlap")
            chunks = chunk_text_semantic(text, use_overlap=True)
            if chunks:
                logger.debug(f"Semantic chunker with overlap produced {len(chunks)} chunks")
                return chunks
        except Exception as e:
            logger.warning(f"Semantic chunker with overlap failed: {e}")

    # Fallback к простому chunker без перекрытия
    logger.debug("Using simple chunker (no overlap support)")
    return _chunk_text_simple(text, min_tokens, max_tokens)
