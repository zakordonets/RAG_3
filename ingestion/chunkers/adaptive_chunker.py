#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Адаптивный chunker для смешанных документов
Реализует гибридную стратегию разбивки в зависимости от типа и длины документа
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from loguru import logger

from app.config import CONFIG
from app.tokenizer import count_tokens, get_size_category
try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # fallback if not installed


class DocumentType(Enum):
    """Тип документа по длине"""
    SHORT = "short"      # < 300 токенов
    MEDIUM = "medium"    # 300-1000 токенов
    LONG = "long"        # > 1000 токенов


@dataclass
class ChunkingStrategy:
    """Стратегия чанкинга для типа документа"""
    chunk_size: int
    overlap: int
    use_structural: bool
    use_sliding_window: bool


class AdaptiveChunker:
    """Адаптивный chunker для смешанных документов"""

    def __init__(self):
        self.strategies = {
            DocumentType.SHORT: ChunkingStrategy(
                chunk_size=0,
                overlap=0,
                use_structural=False,
                use_sliding_window=False
            ),
            DocumentType.MEDIUM: ChunkingStrategy(
                chunk_size=CONFIG.adaptive_medium_size,
                overlap=CONFIG.adaptive_medium_overlap,
                use_structural=True,
                use_sliding_window=True
            ),
            DocumentType.LONG: ChunkingStrategy(
                chunk_size=CONFIG.adaptive_long_size,
                overlap=CONFIG.adaptive_long_overlap,
                use_structural=True,
                use_sliding_window=True
            )
        }

    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Адаптивное разбиение текста на чанки

        Args:
            text: Исходный текст
            metadata: Метаданные документа

        Returns:
            Список чанков с метаданными
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided to chunk_text")
                return []

            # Определяем тип документа по длине
            word_count = len(text.split())
            doc_type = self._classify_document_type(text)
            strategy = self.strategies[doc_type]

            logger.debug(f"Document type: {doc_type.value}, words: {word_count}, strategy: {strategy}")

            # Применяем соответствующую стратегию
            if doc_type == DocumentType.SHORT:
                return self._chunk_short_document(text, metadata)
            elif doc_type == DocumentType.MEDIUM:
                return self._chunk_medium_document(text, metadata, strategy)
            else:  # LONG
                return self._chunk_long_document(text, metadata, strategy)

        except Exception as e:
            logger.error(f"Critical error in chunk_text: {e}")
            # Fallback: создаем один чанк с исходным текстом
            try:
                return [{
                    'content': text.strip(),
                    'metadata': {
                        **(metadata or {}),
                        'chunk_type': 'fallback',
                        'chunk_index': 0,
                        'total_chunks': 1,
                        'word_count': len(text.split()),
                        'token_count': count_tokens(text),
                        'is_complete_document': True,
                        'error': str(e)
                    }
                }]
            except Exception as fallback_error:
                logger.error(f"Fallback chunking also failed: {fallback_error}")
                return []

    def _classify_document_type(self, text: str) -> DocumentType:
        """Классифицирует документ по длине используя токенайзер"""
        size_category = get_size_category(text)
        if size_category == 'short':
            return DocumentType.SHORT
        elif size_category == 'medium':
            return DocumentType.MEDIUM
        else:
            return DocumentType.LONG

    def _chunk_short_document(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Обработка коротких документов - целиком"""
        return [{
            'content': text.strip(),
            'metadata': {
                **(metadata or {}),
                'chunk_type': 'short_document',
                'chunk_index': 0,
                'total_chunks': 1,
                'word_count': len(text.split()),
                'token_count': count_tokens(text),
                'is_complete_document': True
            }
        }]

    def _chunk_medium_document(self, text: str, metadata: Dict[str, Any] = None, strategy: ChunkingStrategy = None) -> List[Dict[str, Any]]:
        """Обработка средних документов - структурная + sliding window"""
        chunks = []

        # Сначала структурная сегментация
        if strategy.use_structural:
            segments = self._structural_segmentation(text)
        else:
            segments = [text]

        # Затем sliding window для каждого сегмента
        for seg_idx, segment in enumerate(segments):
            if strategy.use_sliding_window:
                segment_chunks = self._sliding_window_chunking(
                    segment,
                    strategy.chunk_size,
                    strategy.overlap
                )
            else:
                segment_chunks = [segment]

            # Добавляем метаданные
            for chunk_idx, chunk_content in enumerate(segment_chunks):
                chunks.append({
                    'content': chunk_content.strip(),
                    'metadata': {
                        **(metadata or {}),
                        'chunk_type': 'medium_document',
                        'chunk_index': len(chunks),
                        'total_chunks': len(segment_chunks),
                        'segment_index': seg_idx,
                        'word_count': len(chunk_content.split()),
                        'token_count': count_tokens(chunk_content),
                        'is_complete_document': False
                    }
                })

        return chunks

    def _chunk_long_document(self, text: str, metadata: Dict[str, Any] = None, strategy: ChunkingStrategy = None) -> List[Dict[str, Any]]:
        """Обработка длинных документов - иерархический подход"""
        chunks = []

        # Сначала разбивка по заголовкам
        sections = self._hierarchical_segmentation(text)

        for section_idx, section in enumerate(sections):
            section_content = section['content']
            section_title = section.get('title', f'Section {section_idx + 1}')

            # Для каждого раздела применяем sliding window
            if strategy.use_sliding_window:
                section_chunks = self._sliding_window_chunking(
                    section_content,
                    strategy.chunk_size,
                    strategy.overlap
                )
            else:
                section_chunks = [section_content]

            # Добавляем метаданные с информацией о разделе
            for chunk_idx, chunk_content in enumerate(section_chunks):
                chunks.append({
                    'content': chunk_content.strip(),
                    'metadata': {
                        **(metadata or {}),
                        'chunk_type': 'long_document',
                        'chunk_index': len(chunks),
                        'total_chunks': len(section_chunks),
                        'section_index': section_idx,
                        'section_title': section_title,
                        'word_count': len(chunk_content.split()),
                        'token_count': count_tokens(chunk_content),
                        'is_complete_document': False
                    }
                })

        return chunks

    def _structural_segmentation(self, text: str) -> List[str]:
        """Структурная сегментация по абзацам"""
        # Ограничим текст для защиты памяти при патогенных входах
        if len(text) > 2_000_000:  # ~2М символов (~2MB)
            logger.warning(f"Input text too large for structural segmentation: {len(text)} chars, truncating")
            text = text[:2_000_000]
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        # Объединяем слишком короткие абзацы
        segments = []
        current_segment = []
        current_tokens = 0

        for paragraph in paragraphs:
            paragraph_tokens = count_tokens(paragraph)

            # Если абзац очень короткий, объединяем с предыдущим
            if paragraph_tokens < CONFIG.adaptive_chunk_min_merge_tokens and current_segment:
                current_segment.append(paragraph)
                current_tokens += paragraph_tokens
            else:
                # Завершаем текущий сегмент
                if current_segment:
                    segments.append('\n\n'.join(current_segment))

                # Начинаем новый сегмент
                current_segment = [paragraph]
                current_tokens = paragraph_tokens

        # Добавляем последний сегмент
        if current_segment:
            segments.append('\n\n'.join(current_segment))

        return segments

    def _hierarchical_segmentation(self, text: str) -> List[Dict[str, Any]]:
        """Иерархическая сегментация по заголовкам"""
        sections: List[Dict[str, Any]] = []

        # Попытка: если это HTML и есть BeautifulSoup — резать по h1–h6
        if BeautifulSoup is not None and ('<h1' in text or '<h2' in text or '<h3' in text or '<h4' in text or '<h5' in text or '<h6' in text):
            try:
                soup = BeautifulSoup(text, 'html.parser')
                # Собираем все элементы, где начинаются секции
                headings = soup.find_all(re.compile(r'^h[1-6]$'))
                if headings:
                    for idx, h in enumerate(headings):
                        try:
                            title = h.get_text(strip=True)
                            if not title:  # Пропускаем пустые заголовки
                                continue

                            # Контент до следующего заголовка
                            content_parts = []
                            for sib in h.next_siblings:
                                if getattr(sib, 'name', None) and re.match(r'^h[1-6]$', sib.name):
                                    break
                                # Берём текст параграфов/списков
                                if getattr(sib, 'get_text', None):
                                    try:
                                        txt = sib.get_text(" ", strip=True)
                                        if txt and len(txt) > 10:  # Минимальная длина контента
                                            content_parts.append(txt)
                                    except Exception as e:
                                        logger.debug(f"Error extracting text from sibling element: {e}")
                                        continue
                            content = '\n\n'.join(content_parts).strip()
                            if content and len(content) > 20:  # Минимальная длина секции
                                sections.append({'title': title, 'content': content})
                        except Exception as e:
                            logger.warning(f"Error processing heading {idx}: {e}")
                            continue
                if sections:
                    logger.debug(f"Successfully segmented HTML into {len(sections)} sections")
                    return sections
            except Exception as e:
                logger.warning(f"Error in HTML hierarchical segmentation: {e}, falling back to Markdown")
                pass  # fallback к Markdown-разметке

        # Markdown-подобные заголовки (# .. ######)
        header_pattern = r'^(#{1,6})\s+(.+)$'
        lines = text.split('\n')
        current_section = {'title': 'Introduction', 'content': []}
        for line in lines:
            header_match = re.match(header_pattern, line.strip())
            if header_match:
                if current_section['content']:
                    sections.append({'title': current_section['title'], 'content': '\n'.join(current_section['content']).strip()})
                title = header_match.group(2).strip()
                current_section = {'title': title, 'content': []}
            else:
                current_section['content'].append(line)
        if current_section['content']:
            sections.append({'title': current_section['title'], 'content': '\n'.join(current_section['content']).strip()})
        return sections

    def _sliding_window_chunking(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Sliding window разбивка текста"""
        try:
            # Валидация входных параметров
            if not text or not text.strip():
                logger.warning("Empty text provided to sliding window chunking")
                return []

            if chunk_size <= 0:
                logger.warning(f"Invalid chunk_size: {chunk_size}, using default 512")
                chunk_size = 512

            if overlap < 0 or overlap >= chunk_size:
                logger.warning(f"Invalid overlap: {overlap}, using default 100")
                overlap = min(100, chunk_size // 4)

            # Ограничение на максимальную длину для защиты памяти
            words = text.split()
            if len(words) > 200000:  # ~ защитный лимит ~200k слов
                logger.warning(f"Input too large for sliding window: {len(words)} words, truncating for safety")
                words = words[:200000]
            chunks = []

            if len(words) <= chunk_size:
                return [text]

            start = 0
            max_chunks = 1000  # Уменьшенный защитный лимит
            produced = 0

            # Убеждаемся, что overlap не больше chunk_size
            safe_overlap = min(overlap, chunk_size - 1)
            if safe_overlap <= 0:
                safe_overlap = max(1, chunk_size // 4)  # Минимальный overlap

            logger.debug(f"Sliding window: chunk_size={chunk_size}, safe_overlap={safe_overlap}")

            while start < len(words) and produced < max_chunks:
                try:
                    end = min(start + chunk_size, len(words))
                    chunk_words = words[start:end]

                    # Завершаем на полном предложении если возможно
                    if end < len(words):
                        chunk_text = ' '.join(chunk_words)
                        # Ищем последнюю точку, восклицательный или вопросительный знак
                        last_sentence_end = max(
                            chunk_text.rfind('.'),
                            chunk_text.rfind('!'),
                            chunk_text.rfind('?')
                        )

                        if last_sentence_end > len(chunk_text) * 0.7:  # Если предложение не слишком короткое
                            chunk_text = chunk_text[:last_sentence_end + 1]
                            # Пересчитываем позицию
                            end = start + len(chunk_text.split())

                    chunk_content = ' '.join(words[start:end])
                    if chunk_content.strip():  # Только непустые чанки
                        chunks.append(chunk_content)

                    # Безопасное увеличение позиции
                    next_start = end - safe_overlap
                    if next_start <= start:
                        # Предотвращаем бесконечный цикл
                        next_start = start + 1

                    start = next_start
                    produced += 1

                    # Дополнительная защита от бесконечного цикла
                    if produced > 100 and len(chunks) == 0:
                        logger.warning("Sliding window stuck, breaking loop")
                        break

                except Exception as e:
                    logger.warning(f"Error creating chunk {produced}: {e}")
                    # Пропускаем проблемный чанк и продолжаем
                    start += chunk_size
                    produced += 1

            logger.debug(f"Created {len(chunks)} chunks with sliding window")
            return chunks

        except Exception as e:
            logger.error(f"Critical error in sliding window chunking: {e}")
            # Fallback: простое разбиение на равные части
            try:
                words = text.split()
                if len(words) <= chunk_size:
                    return [text]
                chunks = []
                for i in range(0, len(words), chunk_size - overlap):
                    chunk = ' '.join(words[i:i + chunk_size])
                    if chunk.strip():
                        chunks.append(chunk)
                return chunks
            except Exception as fallback_error:
                logger.error(f"Fallback chunking also failed: {fallback_error}")
                return [text]  # Последний resort


def adaptive_chunk_text(text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Адаптивное разбиение текста на чанки

    Args:
        text: Исходный текст
        metadata: Метаданные документа

    Returns:
        Список чанков с метаданными
    """
    chunker = AdaptiveChunker()
    return chunker.chunk_text(text, metadata)
