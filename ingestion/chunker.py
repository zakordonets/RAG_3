from __future__ import annotations

import hashlib
from typing import Iterable
from loguru import logger
from app.config import CONFIG
from app.tokenizer import count_tokens

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


def _is_jina_reader_text(text: str) -> bool:
    """
    Определяет, является ли текст результатом Jina Reader.

    Args:
        text: Текст для проверки

    Returns:
        True если текст от Jina Reader
    """
    if not text:
        return False

    # Характерные признаки текста от Jina Reader
    jina_markers = [
        "Title:",
        "URL Source:",
        "Markdown Content:",
        "\n\nURL Source: http"
    ]

    text_start = text[:500]  # Проверяем только начало текста

    return any(marker in text_start for marker in jina_markers)


def chunk_text(text: str, min_tokens: int = None, max_tokens: int = None, use_semantic: bool = None) -> list[str]:
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

    # Автоматически определяем, использовать ли семантический chunker
    if use_semantic is None:
        # Не используем semantic chunker для текста из Jina Reader (содержит метаданные)
        use_semantic = not _is_jina_reader_text(text)

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
    """
    Оптимальный chunker по абзацам с интеллектуальным разбиением.

    Стратегия:
    1. Сохраняет целостность абзацев когда возможно
    2. Создает чанки оптимального размера (70-90% от max_tokens)
    3. Разбивает большие абзацы по предложениям
    4. Объединяет маленькие абзацы в оптимальные чанки
    """

    # Предварительная обработка для Jina Reader текста
    if _is_jina_reader_text(text):
        text = _preprocess_jina_text(text)
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
    chunks = _deduplicate_chunks(chunks)

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


def _split_large_paragraph(paragraph: str, min_tokens: int, max_tokens: int,
                          optimal_min: int, optimal_max: int) -> list[str]:
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


def _deduplicate_chunks(chunks: list[str]) -> list[str]:
    """Удаляет дублирующиеся чанки."""
    seen = set()
    unique_chunks = []

    for chunk in chunks:
        chunk_hash = text_hash(chunk)
        if chunk_hash not in seen:
            seen.add(chunk_hash)
            unique_chunks.append(chunk)

    return unique_chunks


def _split_paragraph_into_sentences(paragraph: str) -> list[str]:
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


def _preprocess_jina_text(text: str) -> str:
    """
    Предварительная обработка текста от Jina Reader.

    Args:
        text: Исходный текст от Jina Reader

    Returns:
        Обработанный текст без метаданных
    """
    lines = text.split('\n')
    processed_lines = []

    skip_next = False
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        line = line.strip()

        # Пропускаем метаданные Jina Reader
        if line.startswith(('Title:', 'URL Source:')):
            continue

        # Пропускаем строку "Markdown Content:" и следующую пустую строку
        if line == 'Markdown Content:':
            skip_next = True  # Пропускаем следующую строку (обычно пустую)
            continue

        # Пропускаем навигационные элементы
        if (line.startswith(('*   [', '[Skip to main content]', 'ctrl K', 'On this page')) or
            line.startswith(('[Previous ', '[Next ')) or
            line.startswith('[![Image')):
            continue

        # Пропускаем разделители
        if line.startswith('===') or line.startswith('---') or line == '===============':
            continue

        # Пропускаем очень короткие строки (обычно мусор)
        if len(line.split()) < 3 and not any(char.isalnum() for char in line):
            continue

        if line:
            processed_lines.append(line)

    result = '\n\n'.join(processed_lines)
    logger.debug(f"Preprocessed Jina text: {len(text)} -> {len(result)} chars")
    return result


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
