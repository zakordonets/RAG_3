"""
Универсальный структурно-осознанный чанкер для BGE-M3
Объединяет все лучшие практики из существующих чанкеров
"""

from __future__ import annotations

import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger


def text_hash(text: str) -> str:
    """Создает хеш строки для ID."""
    return hashlib.sha1(text.encode('utf-8')).hexdigest()

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("rank_bm25 не установлен, semantic packing будет отключен")

try:
    from FlagEmbedding import BGEM3FlagModel
    BGE_AVAILABLE = True
except ImportError:
    BGE_AVAILABLE = False
    logger.warning("FlagEmbedding не установлен, используется fallback токенизация")


@dataclass
class Block:
    """Структурный блок документа"""
    type: str  # heading, paragraph, list, code, table, etc.
    text: str
    depth: int  # Уровень вложенности (для заголовков)
    is_atomic: bool  # Атомарный блок (не режется)
    start_line: int
    end_line: int


@dataclass
class Chunk:
    """Чанк с метаданными"""
    text: str
    chunk_index: int
    total_chunks: int
    heading_path: List[str]
    content_type: str
    doc_id: str
    site_url: str
    source: str
    category: str
    lang: str = "ru"
    metadata: Dict[str, Any] = None


class OversizePolicy(Enum):
    """Политика обработки больших блоков"""
    KEEP = "keep"      # Хранить как один чанк
    SPLIT = "split"    # Делить по безопасным границам
    SKIP = "skip"      # Пропускать с предупреждением


class UniversalChunker:
    """
    Универсальный структурно-осознанный чанкер для BGE-M3

    Оптимизирован для:
    - Markdown/HTML документов
    - Dense + Sparse эмбеддингов
    - Сохранения структурной целостности
    - Адаптивного overlap
    """

    def __init__(
        self,
        tokenizer=None,
        max_tokens: int = 600,
        min_tokens: int = 350,
        overlap_base: int = 100,
        oversize_block_policy: OversizePolicy = OversizePolicy.SPLIT,
        oversize_block_limit: int = 1200
    ):
        """
        Инициализирует UniversalChunker

        Args:
            tokenizer: Токенизатор BGE-M3 (если None, используется fallback)
            max_tokens: Максимальный размер чанка в токенах
            min_tokens: Минимальный размер чанка в токенах
            overlap_base: Базовый overlap в токенах
            oversize_block_policy: Политика обработки больших блоков
            oversize_block_limit: Лимит для принудительного разбиения
        """
        self.tokenizer = tokenizer or self._get_fallback_tokenizer()
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_base = overlap_base
        self.oversize_block_policy = oversize_block_policy
        self.oversize_block_limit = oversize_block_limit

        # Регулярные выражения для парсинга
        self.markdown_patterns = {
            'heading': re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE),
            'list': re.compile(r'^(\s*[-*+]|\s*\d+\.)\s+.+$', re.MULTILINE),
            'code_block': re.compile(r'^```[\s\S]*?^```', re.MULTILINE),
            'inline_code': re.compile(r'`[^`]+`'),
            'table': re.compile(r'^\|.+\|$', re.MULTILINE),
            'blockquote': re.compile(r'^>\s+.+$', re.MULTILINE),
            'admonition': re.compile(r'^:::\w+[\s\S]*?^:::', re.MULTILINE),
        }

        logger.info(f"UniversalChunker инициализирован: max_tokens={max_tokens}, min_tokens={min_tokens}")

    def _get_fallback_tokenizer(self):
        """Получает fallback токенизатор"""
        if BGE_AVAILABLE:
            try:
                model = BGEM3FlagModel("BAAI/bge-m3")
                return model.tokenizer
            except Exception as e:
                logger.warning(f"Не удалось загрузить BGE-M3 токенизатор: {e}")

        # Fallback токенизация
        def fallback_tokenize(text: str) -> List[str]:
            return re.findall(r"[\w\-_/]+|[^\s\w]", text)

        return fallback_tokenize

    def _count_tokens(self, text: str) -> int:
        """Подсчитывает количество токенов в тексте"""
        if hasattr(self.tokenizer, 'encode'):
            try:
                return len(self.tokenizer.encode(text, add_special_tokens=False))
            except Exception:
                pass

        # Fallback через слова
        return len(text.split())

    def _blockify_markdown(self, text: str) -> List[Block]:
        """Разбирает Markdown текст на структурные блоки"""
        lines = text.split('\n')
        blocks = []
        current_type = 'empty'
        current_text = []
        current_depth = 0
        start_line = 0
        in_code_block = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Пропускаем пустые строки в начале
            if not line_stripped and not current_text:
                continue

            # Определяем тип блока
            block_type = self._classify_markdown_line(line_stripped)

            # Обрабатываем код-блоки специально
            if line_stripped.startswith(('```', '~~~')):
                if not in_code_block:
                    # Начало код-блока
                    in_code_block = True
                    block_type = 'code_block'
                else:
                    # Конец код-блока
                    in_code_block = False
                    # Добавляем строку к текущему блоку и завершаем его
                    if current_text:
                        current_text.append(line)
                        block_text = '\n'.join(current_text).strip()
                        if block_text:
                            blocks.append(Block(
                                type=current_type,
                                text=block_text,
                                depth=current_depth,
                                is_atomic=self._is_atomic_block(current_type),
                                start_line=start_line,
                                end_line=i
                            ))
                    current_type = 'empty'
                    current_text = []
                    continue

            # Если это пустая строка, добавляем к текущему блоку
            if block_type == 'empty':
                if current_text:
                    current_text.append(line)
                continue

            # Если тип блока изменился или нужно начать новый блок
            if (block_type != current_type and current_type != 'empty') or self._should_start_new_block(line_stripped, current_type, current_text):
                # Завершаем текущий блок
                if current_text:
                    block_text = '\n'.join(current_text).strip()
                    if block_text:  # Только если блок не пустой
                        blocks.append(Block(
                            type=current_type,
                            text=block_text,
                            depth=current_depth,
                            is_atomic=self._is_atomic_block(current_type),
                            start_line=start_line,
                            end_line=i-1
                        ))

                # Начинаем новый блок
                current_type = block_type
                current_text = [line]
                current_depth = self._get_block_depth(line_stripped, block_type)
                start_line = i
            else:
                current_text.append(line)

        # Добавляем последний блок
        if current_text:
            block_text = '\n'.join(current_text).strip()
            if block_text:  # Только если блок не пустой
                blocks.append(Block(
                    type=current_type,
                    text=block_text,
                    depth=current_depth,
                    is_atomic=self._is_atomic_block(current_type),
                    start_line=start_line,
                    end_line=len(lines)-1
                ))

        return blocks

    def _classify_markdown_line(self, line: str) -> str:
        """Классифицирует строку Markdown по типу блока"""
        if not line:
            return 'empty'

        if line.startswith('#'):
            return 'heading'
        elif line.startswith(('```', '~~~')):
            return 'code_block'
        elif line.startswith('|') and '|' in line[1:]:
            return 'table'
        elif line.startswith('>'):
            return 'blockquote'
        elif line.startswith(':::'):
            return 'admonition'
        elif re.match(r'^\s*[-*+]|\s*\d+\.', line):
            return 'list'
        else:
            return 'paragraph'

    def _should_start_new_block(self, line: str, current_type: str, current_text: List[str]) -> bool:
        """Определяет, нужно ли начинать новый блок"""
        line_stripped = line.strip()

        # Заголовки всегда начинают новый блок
        if line_stripped.startswith('#'):
            return True

        # Код-блоки начинаются и заканчиваются на ```
        if line_stripped.startswith(('```', '~~~')):
            # Если это начало код-блока, начинаем новый блок
            if current_type != 'code_block':
                return True
            # Если это конец код-блока, продолжаем текущий блок (не начинаем новый)
            return False

        # Таблицы должны содержать |
        if line_stripped.startswith('|') and '|' in line_stripped[1:]:
            return current_type != 'table'

        # Списки должны начинаться с -, *, + или цифры
        if re.match(r'^\s*[-*+]|\s*\d+\.', line_stripped):
            # Проверяем, является ли это другим типом списка
            if current_type == 'list':
                # Проверяем, является ли текущий блок маркированным списком
                current_is_bullet = any(re.match(r'^\s*[-*+]', l.strip()) for l in current_text if l.strip())
                current_is_numbered = any(re.match(r'^\s*\d+\.', l.strip()) for l in current_text if l.strip())

                # Проверяем новый элемент
                new_is_bullet = re.match(r'^\s*[-*+]', line_stripped)
                new_is_numbered = re.match(r'^\s*\d+\.', line_stripped)

                # Если типы списков разные, начинаем новый блок
                if (current_is_bullet and new_is_numbered) or (current_is_numbered and new_is_bullet):
                    return True

            return current_type != 'list'

        # Блоки цитат начинаются с >
        if line_stripped.startswith('>'):
            return current_type != 'blockquote'

        # Admonitions начинаются с :::
        if line_stripped.startswith(':::'):
            return current_type != 'admonition'

        # Если текущий тип - список, а строка не является списком, начинаем новый блок
        if current_type == 'list' and not re.match(r'^\s*[-*+]|\s*\d+\.', line_stripped) and line_stripped:
            return True

        # Если текущий тип - таблица, а строка не является таблицей, начинаем новый блок
        if current_type == 'table' and not (line_stripped.startswith('|') and '|' in line_stripped[1:]):
            return True

        # Если текущий тип - код-блок, а строка не является код-блоком, начинаем новый блок
        if current_type == 'code_block' and not line_stripped.startswith(('```', '~~~')):
            return True

        return False

    def _get_block_depth(self, line: str, block_type: str) -> int:
        """Получает глубину блока"""
        if block_type == 'heading':
            return len(line) - len(line.lstrip('#'))
        elif block_type == 'list':
            return len(line) - len(line.lstrip())
        return 0

    def _is_atomic_block(self, block_type: str) -> bool:
        """Определяет, является ли блок атомарным"""
        return block_type in ['code_block', 'table', 'list']

    def _safe_split_oversize_block(self, block: Block) -> List[Block]:
        """Безопасно разбивает большие блоки"""
        tokens = self._count_tokens(block.text)

        if tokens <= self.max_tokens:
            return [block]

        logger.warning(f"Большой блок {block.type} ({tokens} токенов) - разбиение")

        if block.type == 'code_block':
            return self._split_code_block(block)
        elif block.type == 'list':
            return self._split_list_block(block)
        elif block.type == 'table':
            return self._split_table_block(block)
        elif block.type == 'paragraph':
            return self._split_paragraph_block(block)
        else:
            # Для других типов используем простое разбиение
            return self._split_by_sentences(block)

    def _split_code_block(self, block: Block) -> List[Block]:
        """Разбивает код-блок по пустым строкам и комментариям"""
        lines = block.text.split('\n')
        chunks = []
        current_chunk = []

        for line in lines:
            current_chunk.append(line)

            # Проверяем, нужно ли разбить
            if (line.strip() == '' or
                line.strip().startswith(('#', '//', '/*', '*/')) or
                len(current_chunk) >= 20):  # Максимум 20 строк в чанке

                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append(Block(
                        type=block.type,
                        text=chunk_text,
                        depth=block.depth,
                        is_atomic=True,
                        start_line=block.start_line,
                        end_line=block.end_line
                    ))
                    current_chunk = []

        # Добавляем последний чанк
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(Block(
                type=block.type,
                text=chunk_text,
                depth=block.depth,
                is_atomic=True,
                start_line=block.start_line,
                end_line=block.end_line
            ))

        # Если не удалось разбить, возвращаем исходный блок
        if not chunks:
            return [block]

        return chunks

    def _split_list_block(self, block: Block) -> List[Block]:
        """Разбивает список по группам пунктов"""
        lines = block.text.split('\n')
        chunks = []
        current_chunk = []
        list_item_count = 0

        for line in lines:
            current_chunk.append(line)

            # Считаем пункты списка
            if re.match(r'^\s*[-*+]|\s*\d+\.', line):
                list_item_count += 1

                # Разбиваем каждые 15 пунктов
                if list_item_count >= 15:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append(Block(
                        type=block.type,
                        text=chunk_text,
                        depth=block.depth,
                        is_atomic=True,
                        start_line=block.start_line,
                        end_line=block.end_line
                    ))
                    current_chunk = []
                    list_item_count = 0

        # Добавляем последний чанк
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(Block(
                type=block.type,
                text=chunk_text,
                depth=block.depth,
                is_atomic=True,
                start_line=block.start_line,
                end_line=block.end_line
            ))

        # Если не удалось разбить, возвращаем исходный блок
        if not chunks:
            return [block]

        return chunks

    def _split_table_block(self, block: Block) -> List[Block]:
        """Разбивает таблицу по строкам"""
        lines = block.text.split('\n')
        chunks = []
        current_chunk = []

        for line in lines:
            current_chunk.append(line)

            # Разбиваем каждые 20 строк
            if len(current_chunk) >= 20:
                chunk_text = '\n'.join(current_chunk)
                chunks.append(Block(
                    type=block.type,
                    text=chunk_text,
                    depth=block.depth,
                    is_atomic=True,
                    start_line=block.start_line,
                    end_line=block.end_line
                ))
                current_chunk = []

        # Добавляем последний чанк
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(Block(
                type=block.type,
                text=chunk_text,
                depth=block.depth,
                is_atomic=True,
                start_line=block.start_line,
                end_line=block.end_line
            ))

        # Если не удалось разбить, возвращаем исходный блок
        if not chunks:
            return [block]

        return chunks

    def _split_paragraph_block(self, block: Block) -> List[Block]:
        """Разбивает параграф по предложениям"""
        sentences = re.split(r'[.!?]+\s+', block.text)
        chunks = []
        current_chunk = []

        for sentence in sentences:
            current_chunk.append(sentence)

            chunk_text = ' '.join(current_chunk)
            if self._count_tokens(chunk_text) >= self.max_tokens:
                chunks.append(Block(
                    type=block.type,
                    text=chunk_text,
                    depth=block.depth,
                    is_atomic=False,
                    start_line=block.start_line,
                    end_line=block.end_line
                ))
                current_chunk = []

        # Добавляем последний чанк
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(Block(
                type=block.type,
                text=chunk_text,
                depth=block.depth,
                is_atomic=False,
                start_line=block.start_line,
                end_line=block.end_line
            ))

        return chunks if chunks else [block]

    def _split_by_sentences(self, block: Block) -> List[Block]:
        """Простое разбиение по предложениям"""
        sentences = re.split(r'[.!?]+\s+', block.text)
        chunks = []

        for sentence in sentences:
            if sentence.strip():
                chunks.append(Block(
                    type=block.type,
                    text=sentence.strip(),
                    depth=block.depth,
                    is_atomic=block.is_atomic,
                    start_line=block.start_line,
                    end_line=block.end_line
                ))

        return chunks if chunks else [block]

    def _semantic_packing(self, blocks: List[Block]) -> List[List[Block]]:
        """Семантическая упаковка блоков в чанки"""
        if not BM25_AVAILABLE:
            # Fallback без семантического анализа
            return self._simple_packing(blocks)

        chunks = []
        current_chunk = []
        current_tokens = 0
        current_heading_path = []

        for block in blocks:
            block_tokens = self._count_tokens(block.text)

            # Обновляем heading_path
            if block.type == 'heading':
                current_heading_path = self._update_heading_path(current_heading_path, block)

            # Проверяем, поместится ли блок
            if current_tokens + block_tokens <= self.max_tokens:
                current_chunk.append(block)
                current_tokens += block_tokens
            else:
                # Завершаем текущий чанк
                if current_chunk:
                    chunks.append(current_chunk)

                # Начинаем новый чанк
                current_chunk = [block]
                current_tokens = block_tokens

        # Добавляем последний чанк
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _simple_packing(self, blocks: List[Block]) -> List[List[Block]]:
        """Простая упаковка без семантического анализа"""
        chunks = []
        current_chunk = []
        current_tokens = 0

        for block in blocks:
            block_tokens = self._count_tokens(block.text)

            if current_tokens + block_tokens <= self.max_tokens:
                current_chunk.append(block)
                current_tokens += block_tokens
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [block]
                current_tokens = block_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _update_heading_path(self, current_path: List[str], heading_block: Block) -> List[str]:
        """Обновляет путь заголовков"""
        heading_text = heading_block.text.strip('#').strip()
        depth = heading_block.depth

        # Обрезаем путь до нужной глубины
        new_path = current_path[:depth-1] + [heading_text]

        return new_path

    def _calculate_adaptive_overlap(
        self,
        current_chunk: List[Block],
        next_chunk: List[Block],
        current_heading_path: List[str],
        next_heading_path: List[str]
    ) -> int:
        """Вычисляет адаптивный overlap"""
        # Новый H1/H2 - без overlap
        if (len(next_heading_path) > 0 and
            (len(current_heading_path) == 0 or
             next_heading_path[0] != current_heading_path[0])):
            return 0

        # Тот же heading_path - базовый overlap
        if current_heading_path == next_heading_path:
            return self.overlap_base + 60

        # Обрыв списка - увеличенный overlap
        if (current_chunk and current_chunk[-1].type == 'list' and
            next_chunk and next_chunk[0].type == 'list'):
            return self.overlap_base + 120

        # По умолчанию
        return self.overlap_base

    def _apply_overlap(self, chunks: List[List[Block]]) -> List[List[Block]]:
        """Применяет адаптивный overlap к чанкам"""
        if len(chunks) <= 1:
            return chunks

        overlapped_chunks = []

        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped_chunks.append(chunk)
                continue

            # Вычисляем overlap
            current_heading_path = self._extract_heading_path(chunk)
            prev_heading_path = self._extract_heading_path(chunks[i-1])

            overlap_tokens = self._calculate_adaptive_overlap(
                chunks[i-1], chunk, prev_heading_path, current_heading_path
            )

            if overlap_tokens > 0:
                # Добавляем overlap из предыдущего чанка
                overlap_text = self._extract_overlap_text(chunks[i-1], overlap_tokens)
                if overlap_text:
                    overlapped_chunk = [Block(
                        type='overlap',
                        text=overlap_text,
                        depth=0,
                        is_atomic=False,
                        start_line=0,
                        end_line=0
                    )] + chunk
                    overlapped_chunks.append(overlapped_chunk)
                else:
                    overlapped_chunks.append(chunk)
            else:
                overlapped_chunks.append(chunk)

        return overlapped_chunks

    def _extract_heading_path(self, chunk: List[Block]) -> List[str]:
        """Извлекает путь заголовков из чанка"""
        path = []
        for block in chunk:
            if block.type == 'heading':
                heading_text = block.text.strip('#').strip()
                depth = block.depth
                path = path[:depth-1] + [heading_text]
        return path

    def _extract_overlap_text(self, chunk: List[Block], overlap_tokens: int) -> str:
        """Извлекает текст для overlap из конца чанка"""
        overlap_text = []
        current_tokens = 0

        # Идем с конца чанка
        for block in reversed(chunk):
            block_tokens = self._count_tokens(block.text)

            if current_tokens + block_tokens <= overlap_tokens:
                overlap_text.insert(0, block.text)
                current_tokens += block_tokens
            else:
                # Частично берем блок
                if current_tokens < overlap_tokens:
                    remaining_tokens = overlap_tokens - current_tokens
                    partial_text = self._extract_partial_text(block.text, remaining_tokens)
                    if partial_text:
                        overlap_text.insert(0, partial_text)
                break

        return '\n\n'.join(overlap_text)

    def _extract_partial_text(self, text: str, max_tokens: int) -> str:
        """Извлекает частичный текст до указанного количества токенов"""
        words = text.split()
        if len(words) <= max_tokens:
            return text

        return ' '.join(words[:max_tokens])

    def chunk(
        self,
        text: str,
        fmt: str,
        meta: Dict[str, Any]
    ) -> List[Chunk]:
        """
        Основной метод чанкинга

        Args:
            text: Исходный текст
            fmt: Формат ('markdown' или 'html')
            meta: Метаданные документа

        Returns:
            Список чанков с метаданными
        """
        if not text or not text.strip():
            return []

        logger.debug(f"Начинаем чанкинг документа: {meta.get('doc_id', 'unknown')}")

        # Шаг 1: Blockify
        if fmt == 'markdown':
            blocks = self._blockify_markdown(text)
        else:
            # Для HTML пока используем простое разбиение
            blocks = [Block(
                type='paragraph',
                text=text,
                depth=0,
                is_atomic=False,
                start_line=0,
                end_line=0
            )]

        # Шаг 2: Safe Split Oversize Blocks
        processed_blocks = []
        for block in blocks:
            block_tokens = self._count_tokens(block.text)

            if block_tokens > self.oversize_block_limit:
                # Принудительное разбиение для очень больших блоков (игнорируем политику)
                split_blocks = self._safe_split_oversize_block(block)
                processed_blocks.extend(split_blocks)
            elif block_tokens > self.max_tokens:
                # Обрабатываем согласно политике
                if self.oversize_block_policy == OversizePolicy.SPLIT:
                    split_blocks = self._safe_split_oversize_block(block)
                    processed_blocks.extend(split_blocks)
                elif self.oversize_block_policy == OversizePolicy.SKIP:
                    logger.warning(f"Пропускаем большой блок {block.type} ({block_tokens} токенов)")
                    continue
                else:  # KEEP - оставляем блок как есть
                    processed_blocks.append(block)
            else:
                processed_blocks.append(block)

        # Шаг 3: Semantic Packing
        chunk_groups = self._semantic_packing(processed_blocks)

        # Шаг 4: Adaptive Overlap
        overlapped_chunks = self._apply_overlap(chunk_groups)

        # Формируем финальные чанки
        final_chunks = []
        total_chunks = len(overlapped_chunks)

        for i, chunk_blocks in enumerate(overlapped_chunks):
            chunk_text = '\n\n'.join(block.text for block in chunk_blocks)

            # Извлекаем heading_path
            heading_path = self._extract_heading_path(chunk_blocks)

            # Создаем чанк
            chunk = Chunk(
                text=chunk_text,
                chunk_index=i,
                total_chunks=total_chunks,
                heading_path=heading_path,
                content_type=fmt,
                doc_id=meta.get('doc_id', ''),
                site_url=meta.get('site_url', ''),
                source=meta.get('source', ''),
                category=meta.get('category', ''),
                lang=meta.get('lang', 'ru'),
                metadata=meta
            )

            final_chunks.append(chunk)

        logger.info(f"Создано {len(final_chunks)} чанков для документа {meta.get('doc_id', 'unknown')}")
        return final_chunks


# Глобальный экземпляр для использования в пайплайне
_global_chunker = None


def get_universal_chunker(**kwargs) -> UniversalChunker:
    """Получает глобальный экземпляр UniversalChunker"""
    global _global_chunker
    if _global_chunker is None:
        _global_chunker = UniversalChunker(**kwargs)
    return _global_chunker


def chunk_text_universal(
    text: str,
    fmt: str = "markdown",
    meta: Optional[Dict[str, Any]] = None,
    **chunker_kwargs
) -> List[Dict[str, Any]]:
    """
    Удобная функция для чанкинга текста

    Args:
        text: Исходный текст
        fmt: Формат ('markdown' или 'html')
        meta: Метаданные документа
        **chunker_kwargs: Параметры для UniversalChunker

    Returns:
        Список чанков в формате словарей
    """
    chunker = get_universal_chunker(**chunker_kwargs)
    meta = meta or {}

    chunks = chunker.chunk(text, fmt, meta)

    # Преобразуем в формат словарей
    result = []
    for chunk in chunks:
        result.append({
            'text': chunk.text,
            'chunk_index': chunk.chunk_index,
            'total_chunks': chunk.total_chunks,
            'heading_path': chunk.heading_path,
            'content_type': chunk.content_type,
            'doc_id': chunk.doc_id,
            'site_url': chunk.site_url,
            'source': chunk.source,
            'category': chunk.category,
            'lang': chunk.lang,
            'metadata': chunk.metadata or {}
        })

    return result
