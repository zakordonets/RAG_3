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
        if not text or not text.strip():
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
                        title = h.get_text(strip=True)
                        # Контент до следующего заголовка
                        content_parts = []
                        for sib in h.next_siblings:
                            if getattr(sib, 'name', None) and re.match(r'^h[1-6]$', sib.name):
                                break
                            # Берём текст параграфов/списков
                            if getattr(sib, 'get_text', None):
                                txt = sib.get_text(" ", strip=True)
                                if txt:
                                    content_parts.append(txt)
                        content = '\n\n'.join(content_parts).strip()
                        if content:
                            sections.append({'title': title, 'content': content})
                if sections:
                    return sections
            except Exception:
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
        # Ограничение на максимальную длину для защиты памяти
        words = text.split()
        if len(words) > 200000:  # ~ защитный лимит ~200k слов
            logger.warning(f"Input too large for sliding window: {len(words)} words, truncating for safety")
            words = words[:200000]
        chunks = []

        if len(words) <= chunk_size:
            return [text]

        start = 0
        max_chunks = 20000  # защитный лимит
        produced = 0
        while start < len(words) and produced < max_chunks:
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

            chunks.append(' '.join(words[start:end]))
            start = end - overlap  # Перекрытие
            produced += 1

        return chunks


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
