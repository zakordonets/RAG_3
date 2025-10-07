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

        # Исправленный детектор списков
        self.LIST_RE = re.compile(r'^\s*(?:[-*+]|\d+\.)\s+')

        # Единый regex для токенизации
        self._TOKEN_RE = re.compile(r"[\w\-_/]+|[^\s\w]", re.UNICODE)

        # Regex для admonitions
        self.ADMON_START_RE = re.compile(r'^:::\s*(tip|note|info|warning|caution|danger)\b', re.I)
        self.ADMON_END_RE = re.compile(r'^:::\s*$')

        logger.info(f"UniversalChunker инициализирован: max_tokens={max_tokens}, min_tokens={min_tokens}")

    def _get_fallback_tokenizer(self):
        """Получает fallback токенизатор"""
        logger.info("Используется fallback токенизация")

        def fallback_tokenize(text: str) -> List[str]:
            return re.findall(r"[\w\-_/]+|[^\s\w]", text)

        return fallback_tokenize

    def _regex_tokenize(self, text: str) -> List[str]:
        """Единая regex токенизация"""
        return self._TOKEN_RE.findall(text or "")

    def _count_tokens(self, text: str) -> int:
        """Подсчитывает количество токенов в тексте"""
        if hasattr(self.tokenizer, 'encode'):
            try:
                return len(self.tokenizer.encode(text, add_special_tokens=False))
            except Exception:
                pass

        # Fallback через единую regex-токенизацию
        return len(self._regex_tokenize(text))

    def _blockify_markdown(self, text: str) -> List[Block]:
        """Разбирает Markdown текст на структурные блоки"""
        lines = text.split('\n')
        blocks = []
        current_type = 'empty'
        current_text = []
        current_depth = 0
        start_line = 0

        # Состояние для admonitions
        in_admon = False
        admon_buf = []
        admon_start = 0
        in_code_block = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Обработка admonitions
            if self.ADMON_START_RE.match(line_stripped):
                # Закрыть текущий блок, если открыт
                if current_text:
                    block_text = '\n'.join(current_text).strip()
                    if block_text:
                        blocks.append(Block(
                            type=current_type, text=block_text, depth=current_depth,
                            is_atomic=self._is_atomic_block(current_type),
                            start_line=start_line, end_line=i-1
                        ))
                    current_type, current_text = 'empty', []
                in_admon, admon_buf, admon_start = True, [line], i
                continue

            if in_admon:
                admon_buf.append(line)
                if self.ADMON_END_RE.match(line_stripped):
                    # Закрыть admonition как единый блок
                    blocks.append(Block(
                        type='admonition', text='\n'.join(admon_buf).strip(),
                        depth=0, is_atomic=False, start_line=admon_start, end_line=i
                    ))
                    in_admon, admon_buf = False, []
                continue

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

    def _blockify_html(self, text: str) -> List[Block]:
        """Разбирает HTML текст на структурные блоки"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("BeautifulSoup не установлен, используем простой HTML парсинг")
            return self._blockify_html_simple(text)

        try:
            soup = BeautifulSoup(text, 'html.parser')
            blocks = []

            # Обрабатываем основные элементы
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'ul', 'ol', 'pre', 'code', 'table', 'blockquote']):
                block_type = self._classify_html_element(element)
                if block_type:
                    # Сохраняем структуру для атомарных блоков
                    if block_type in ("code_block", "table", "list"):
                        block_text = element.get_text("\n", strip=True)  # Важны переводы строк
                    else:
                        block_text = element.get_text(" ", strip=True)  # Обычный текст

                    if block_text:
                        depth = self._get_html_element_depth(element)
                        blocks.append(Block(
                            type=block_type,
                            text=block_text,
                            depth=depth,
                            is_atomic=self._is_atomic_block(block_type),
                            start_line=0,  # HTML не имеет понятия строк
                            end_line=0
                        ))

            return blocks if blocks else [Block(
                type='paragraph',
                text=text,
                depth=0,
                is_atomic=False,
                start_line=0,
                end_line=0
            )]

        except Exception as e:
            logger.warning(f"Ошибка при парсинге HTML: {e}")
            return self._blockify_html_simple(text)

    def _blockify_html_simple(self, text: str) -> List[Block]:
        """Простой HTML парсинг без BeautifulSoup"""
        # Удаляем HTML теги и разбиваем на параграфы
        import re
        clean_text = re.sub(r'<[^>]+>', '', text)
        paragraphs = re.split(r'\n\s*\n', clean_text)

        blocks = []
        for para in paragraphs:
            para = para.strip()
            if para:
                blocks.append(Block(
                    type='paragraph',
                    text=para,
                    depth=0,
                    is_atomic=False,
                    start_line=0,
                    end_line=0
                ))

        return blocks if blocks else [Block(
            type='paragraph',
            text=text,
            depth=0,
            is_atomic=False,
            start_line=0,
            end_line=0
        )]

    def _classify_html_element(self, element) -> Optional[str]:
        """Классифицирует HTML элемент по типу блока"""
        tag_name = element.name.lower()

        if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            return 'heading'
        elif tag_name in ['ul', 'ol']:
            return 'list'
        elif tag_name in ['pre', 'code']:
            return 'code_block'
        elif tag_name == 'table':
            return 'table'
        elif tag_name == 'blockquote':
            return 'blockquote'
        elif tag_name in ['p', 'div']:
            return 'paragraph'

        return None

    def _get_html_element_depth(self, element) -> int:
        """Получает глубину HTML элемента"""
        tag_name = element.name.lower()

        if tag_name.startswith('h'):
            return int(tag_name[1])  # h1 -> 1, h2 -> 2, etc.
        elif tag_name in ['ul', 'ol']:
            # Подсчитываем уровень вложенности списков
            depth = 0
            parent = element.parent
            while parent and parent.name in ['ul', 'ol', 'li']:
                if parent.name in ['ul', 'ol']:
                    depth += 1
                parent = parent.parent
            return depth

        return 0

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
        elif self.LIST_RE.match(line):
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
        if self.LIST_RE.match(line_stripped):
            # Проверяем, является ли это другим типом списка
            if current_type == 'list':
                # Проверяем, является ли текущий блок маркированным списком
                current_is_bullet = any(self.LIST_RE.match(l.strip()) and re.match(r'^\s*[-*+]', l.strip()) for l in current_text if l.strip())
                current_is_numbered = any(self.LIST_RE.match(l.strip()) and re.match(r'^\s*\d+\.', l.strip()) for l in current_text if l.strip())

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
        if current_type == 'list' and not self.LIST_RE.match(line_stripped) and line_stripped:
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
        """Разбивает код-блок с проверкой размера в токенах"""
        # Базово: порции ~20 строк
        lines = block.text.splitlines()
        chunks, buf = [], []

        for ln in lines:
            buf.append(ln)
            if len(buf) >= 20:
                chunk = "\n".join(buf).strip()
                if self._count_tokens(chunk) > self.max_tokens:
                    # Вторичный разрез по пустым строкам/комментариям
                    chunks.extend(self._split_code_soft(chunk, block))
                else:
                    chunks.append(Block(
                        type=block.type,
                        text=chunk,
                        depth=block.depth,
                        is_atomic=True,
                        start_line=block.start_line,
                        end_line=block.end_line
                    ))
                buf = []

        if buf:
            chunk = "\n".join(buf).strip()
            if self._count_tokens(chunk) > self.max_tokens:
                chunks.extend(self._split_code_soft(chunk, block))
            else:
                chunks.append(Block(
                    type=block.type,
                    text=chunk,
                    depth=block.depth,
                    is_atomic=True,
                    start_line=block.start_line,
                    end_line=block.end_line
                ))

        return [c for c in chunks if c] if chunks else [block]

    def _split_code_soft(self, code_piece: str, original_block: Block) -> List[Block]:
        """Делим код по блокам, пустым строкам и комментариям"""
        out, cur = [], []
        for ln in code_piece.splitlines():
            cur.append(ln)
            if not ln.strip() or ln.strip().startswith(("#", "//", "/*", "*", "*/")):
                candidate = "\n".join(cur).strip()
                if self._count_tokens(candidate) >= self.max_tokens:
                    # Если ещё слишком большой — финальный hard-split по строкам
                    out.extend(self._hard_split_by_tokens(candidate, original_block))
                else:
                    out.append(Block(
                        type=original_block.type,
                        text=candidate,
                        depth=original_block.depth,
                        is_atomic=True,
                        start_line=original_block.start_line,
                        end_line=original_block.end_line
                    ))
                cur = []

        if cur:
            candidate = "\n".join(cur).strip()
            if self._count_tokens(candidate) > self.max_tokens:
                out.extend(self._hard_split_by_tokens(candidate, original_block))
            else:
                out.append(Block(
                    type=original_block.type,
                    text=candidate,
                    depth=original_block.depth,
                    is_atomic=True,
                    start_line=original_block.start_line,
                    end_line=original_block.end_line
                ))

        return out

    def _hard_split_by_tokens(self, text: str, original_block: Block) -> List[Block]:
        """Жесткое разбиение по токенам"""
        toks = self._regex_tokenize(text)
        res, buf = [], []
        acc = 0

        for tk in toks:
            buf.append(tk)
            acc += 1
            if acc >= self.max_tokens:
                res.append(Block(
                    type=original_block.type,
                    text=" ".join(buf),
                    depth=original_block.depth,
                    is_atomic=True,
                    start_line=original_block.start_line,
                    end_line=original_block.end_line
                ))
                buf, acc = [], 0

        if buf:
            res.append(Block(
                type=original_block.type,
                text=" ".join(buf),
                depth=original_block.depth,
                is_atomic=True,
                start_line=original_block.start_line,
                end_line=original_block.end_line
            ))

        return res

    def _split_list_block(self, block: Block) -> List[Block]:
        """Разбивает список по группам пунктов"""
        lines = block.text.split('\n')
        chunks = []
        current_chunk = []
        list_item_count = 0

        for line in lines:
            current_chunk.append(line)

            # Считаем пункты списка
            if self.LIST_RE.match(line):
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
        """Разбивает параграф по предложениям с учетом русских сокращений"""
        # Сначала пробуем разбить по абзацам
        paragraphs = re.split(r'\n\s*\n+', block.text)

        if len(paragraphs) > 1:
            # Если есть абзацы, разбиваем по ним
            chunks = []
            for para in paragraphs:
                para = para.strip()
                if para:
                    chunks.append(Block(
                        type=block.type,
                        text=para,
                        depth=block.depth,
                        is_atomic=False,
                        start_line=block.start_line,
                        end_line=block.end_line
                    ))
            return chunks if chunks else [block]

        # Если абзацев нет, разбиваем по предложениям с учетом русских сокращений
        text = block.text

        # Список русских сокращений, которые не должны разбивать предложения
        russian_abbreviations = [
            'т.д.', 'т.п.', 'и т.д.', 'и т.п.', 'т.е.', 'т.к.', 'т.о.',
            'др.', 'пр.', 'стр.', 'г.', 'гг.', 'в.', 'вв.', 'н.э.',
            'до н.э.', 'см.', 'рис.', 'табл.', 'гл.', 'разд.', 'п.',
            'пп.', 'ст.', 'стст.', 'ч.', 'чч.', 'с.', 'сс.', 'кн.',
            'кнн.', 'т.', 'тт.', 'вып.', 'выпп.', '№', '№№',
            'т.д.;', 'т.п.;', 'и пр.', 'напр.', 'т.н.'
        ]

        # Создаем паттерн для разбиения с исключениями
        # Разбиваем по [.!?], но не если перед ними сокращение
        sentences = []
        current_sentence = ""

        # Простое разбиение с проверкой сокращений
        parts = re.split(r'([.!?]+)', text)

        for i, part in enumerate(parts):
            current_sentence += part

            # Проверяем, является ли это концом предложения
            if re.match(r'[.!?]+', part) and i < len(parts) - 1:
                # Проверяем, не является ли предыдущая часть сокращением
                is_abbreviation = False
                for abbrev in russian_abbreviations:
                    if current_sentence.strip().endswith(abbrev):
                        is_abbreviation = True
                        break

                if not is_abbreviation:
                    # Это конец предложения
                    sentence = current_sentence.strip()
                    if sentence:
                        sentences.append(sentence)
                    current_sentence = ""

        # Добавляем последнее предложение
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        # Если не удалось разбить на предложения, используем весь текст
        if not sentences:
            sentences = [text]

        # Формируем чанки из предложений
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
        """Семантическая упаковка блоков в чанки с BM25-анализом"""
        if not BM25_AVAILABLE:
            # Fallback без семантического анализа
            return self._simple_packing(blocks)

        chunks = []
        current_chunk = []
        current_tokens = 0
        current_heading_path = []

        for i, block in enumerate(blocks):
            block_tokens = self._count_tokens(block.text)

            # Обновляем heading_path
            if block.type == 'heading':
                current_heading_path = self._update_heading_path(current_heading_path, block)

            # Проверяем, поместится ли блок
            new_tokens = current_tokens + block_tokens

            should_close_chunk = False

            if new_tokens > self.max_tokens:
                # Превышен лимит токенов
                if current_tokens >= self.min_tokens:
                    should_close_chunk = True
                else:
                    # Недостаточно токенов, но превышен лимит - принудительно закрываем
                    should_close_chunk = True
            elif i < len(blocks) - 1:
                # Проверяем семантическую похожесть со следующим блоком
                next_block = blocks[i + 1]
                similarity = self._calculate_block_similarity(block, next_block)

                # Жёсткая граница: если следующий блок — заголовок H1/H2 и уже набрали min_tokens,
                # закрываем чанк независимо от похожести
                if next_block.type == "heading" and getattr(next_block, "depth", 3) <= 2 and current_tokens >= self.min_tokens:
                    should_close_chunk = True
                elif similarity < 0.15 and current_tokens >= self.min_tokens:
                    # Низкая похожесть и достаточно токенов - закрываем чанк
                    should_close_chunk = True

            if should_close_chunk and current_chunk:
                # Завершаем текущий чанк
                chunks.append(current_chunk)
                current_chunk = [block]
                current_tokens = block_tokens
            else:
                # Добавляем блок к текущему чанку
                current_chunk.append(block)
                current_tokens = new_tokens

        # Добавляем последний чанк
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _calculate_block_similarity(self, block1: Block, block2: Block) -> float:
        """Вычисляет семантическую похожесть между блоками с помощью BM25"""
        return self._bm25_similarity_sym(block1.text, block2.text)

    def _bm25_similarity_sym(self, text_a: str, text_b: str) -> float:
        """
        Симметричная похожесть блоков. Если rank_bm25 недоступен — fallback на Jaccard.
        Нормализация s/(1+s) даёт значение в [0,1] и стабильный порог ~0.15.
        """
        try:
            from rank_bm25 import BM25Okapi
            import re

            tok_a = re.findall(r"[\w\-_/]+", text_a.lower())
            tok_b = re.findall(r"[\w\-_/]+", text_b.lower())

            if not tok_a or not tok_b:
                return 0.0

            bm = BM25Okapi([tok_a, tok_b])
            s12 = bm.get_score(tok_b, 0)  # как "doc0" к "query tokens2"
            s21 = bm.get_score(tok_a, 1)  # как "doc1" к "query tokens1"
            s = 0.5 * (s12 + s21)
            return s / (1.0 + s)  # сглаженная нормализация в [0,1]

        except Exception:
            # Fallback на Jaccard similarity
            import re
            set_a = set(re.findall(r"[\w\-_/]+", text_a.lower()))
            set_b = set(re.findall(r"[\w\-_/]+", text_b.lower()))

            if not set_a or not set_b:
                return 0.0

            intersection = len(set_a & set_b)
            union = len(set_a | set_b)
            return intersection / float(union) if union > 0 else 0.0

    def _tokenize_for_bm25(self, text: str) -> List[str]:
        """Токенизация текста для BM25"""
        # Используем единую токенизацию
        return [word.lower() for word in self._regex_tokenize(text) if word.isalnum()]

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
                    is_code_like = block.type in {"code_block", "table", "list"}
                    partial_text = self._extract_partial_text(block.text, remaining_tokens, is_code_like=is_code_like)
                    if partial_text:
                        overlap_text.insert(0, partial_text)
                break

        return '\n\n'.join(overlap_text)


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
            # Для HTML используем HTML blockify
            blocks = self._blockify_html(text)

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
            # Извлекаем heading_path
            heading_path = self._extract_heading_path(chunk_blocks)

            # Находим глубину последнего заголовка в группе
            last_depth = 1
            for b in reversed(chunk_blocks):
                if b.type == 'heading':
                    last_depth = b.depth
                    break

            # Формируем текст чанка
            chunk_text = '\n\n'.join(block.text for block in chunk_blocks)

            # Добавляем заголовок в начало чанка, если его нет
            chunk_text = self._prepend_heading(heading_path, chunk_text, heading_depth=last_depth)

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


    def _prepend_heading(self, heading_path: List[str], text: str, heading_depth: int = 1) -> str:
        """Вставляет заголовок в начало чанка как шапку с учетом глубины"""
        if not heading_path:
            return text

        # Если текст уже начинается с '#', не дублируем
        if text.lstrip().startswith("#"):
            return text

        # Определяем уровень заголовка
        level = 1 if heading_depth <= 1 else (2 if heading_depth == 2 else 3)
        title = heading_path[-1]

        return f"{'#' * level} {title}\n\n{text}".strip()

    def _extract_partial_text(self, text: str, max_tokens: int, is_code_like: bool = False) -> str:
        """Извлекает частичный текст для overlap с учетом типа блока"""
        if max_tokens <= 0 or not text:
            return ""

        if is_code_like:
            # Для кода/таблиц/списков - по строкам
            acc = 0
            out = []
            for ln in reversed(text.splitlines()):
                t = self._count_tokens(ln)
                if acc + t > max_tokens:
                    break
                out.insert(0, ln)
                acc += t
            return "\n".join(out)

        # Построим позиции токенов в исходной строке
        spans = [m.span() for m in self._TOKEN_RE.finditer(text)]
        if not spans:
            return text

        take = min(max_tokens, len(spans))
        start = spans[-take][0]
        return text[start:]


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
