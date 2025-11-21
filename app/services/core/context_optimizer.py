#!/usr/bin/env python3
"""
Оптимизатор контекста для RAG-системы

Модуль оптимизирует контекст перед отправкой в LLM, управляя размером токенов
и адаптивно выбирая количество документов в зависимости от сложности запроса.

Используется в RAG-пайплайне: Search → Reranking → Context Optimization → LLM

Основные функции:
- Управление лимитами токенов для LLM
- Адаптивный выбор количества документов
- Умная обрезка текста с сохранением важных частей и Markdown-структуры
- Резервирование токенов под ответ LLM
- Специальная обработка списочных запросов
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger

LIST_INTENT_PATTERN = re.compile(r"\b(какие|список|перечень)\b.*\bканал", re.IGNORECASE | re.DOTALL)


class ContextOptimizer:
    """
    Оптимизирует контекст для RAG-системы перед отправкой в LLM.

    Управляет размером токенов, адаптивно выбирает количество документов
    и оптимизирует текст с сохранением Markdown-структуры и важных частей.
    """

    def __init__(self):
        # Настройки управления токенами
        self.max_context_tokens = 3000  # Максимальный контекст для LLM
        self.min_context_tokens = 1000  # Минимальный контекст
        self.reserve_for_response = 0.35  # 35% резерв под ответ и промпт (снижается для списков)
        self.reserve_for_list_response = 0.25  # 25% для коротких списочных ответов

        # Адаптивные лимиты
        self.max_documents = 7
        self.min_documents = 3
        self.target_chunk_tokens = 400

    def optimize_context(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Оптимизирует контекст для отправки в LLM.

        Args:
            documents: Список документов после reranking
            query: Пользовательский запрос

        Returns:
            Оптимизированный список документов с управляемым размером токенов
        """
        if not documents:
            return []

        # 0. Проверяем, является ли запрос списочным
        is_list_query = self._is_list_intent(query)

        if is_list_query:
            logger.info("Detected list intent - using extract mode")
            return self._handle_list_intent(documents, query)

        # 1. Определяем доступный бюджет токенов
        available_tokens = int(self.max_context_tokens * (1 - self.reserve_for_response))
        logger.info(f"Context optimization: {available_tokens} tokens available for documents")

        # 2. Анализируем сложность запроса
        query_complexity = self._analyze_query_complexity(query)
        logger.info(f"Query complexity: {query_complexity}")

        # 3. Адаптивно выбираем количество документов
        target_docs = self._select_document_count(len(documents), query_complexity)
        logger.info(f"Target documents: {target_docs}")

        # 4. Оптимизируем размер чанков
        optimized_docs = self._optimize_chunk_sizes(documents[:target_docs], available_tokens, query)

        # 5. Проверяем итоговый размер
        total_tokens = sum(self._estimate_tokens(doc.get("payload", {}).get("text", ""))
                          for doc in optimized_docs)

        logger.info(f"Final context: {len(optimized_docs)} docs, {total_tokens} tokens")

        return optimized_docs

    def _analyze_query_complexity(self, query: str) -> str:
        """Анализирует сложность запроса"""
        query_lower = query.lower()

        # Простые вопросы (включая списочные запросы)
        simple_indicators = [
            "что такое", "как называется", "где находится", "когда",
            "какие", "список", "перечисли", "перечень"
        ]
        if any(indicator in query_lower for indicator in simple_indicators):
            return "simple"

        # Сложные вопросы
        complex_indicators = ["как настроить", "пошаговая инструкция", "подробно", "примеры"]
        if any(indicator in query_lower for indicator in complex_indicators):
            return "complex"

        # Средние вопросы
        return "medium"

    def _select_document_count(self, available_docs: int, complexity: str) -> int:
        """Адаптивно выбирает количество документов"""
        if complexity == "simple":
            return min(2, available_docs)  # Меньше документов для простых/списочных вопросов
        elif complexity == "complex":
            return min(7, available_docs)  # Больше документов для сложных вопросов
        else:
            return min(6, available_docs)  # Стандартное количество

    def _optimize_chunk_sizes(self, documents: List[Dict[str, Any]], available_tokens: int, query: str = "") -> List[Dict[str, Any]]:
        """Оптимизирует размеры чанков"""
        if not documents:
            return []

        # Распределяем токены по документам
        tokens_per_doc = available_tokens // len(documents)

        optimized_docs = []
        for i, doc in enumerate(documents):
            payload = doc.get("payload", {})
            original_text = payload.get("text", "")

            # Топ-документы получают больше токенов
            if i < 2:  # Первые 2 документа
                max_tokens = int(min(tokens_per_doc * 1.5, 600))
            else:
                max_tokens = int(min(tokens_per_doc, 400))

            # Оптимизируем текст с сохранением Markdown структуры
            optimized_text = self._optimize_text_markdown(original_text, max_tokens, query)

            # Создаем оптимизированный документ
            optimized_payload = payload.copy()
            optimized_payload["text"] = optimized_text
            optimized_payload["original_length"] = len(original_text)
            optimized_payload["optimized_length"] = len(optimized_text)

            optimized_doc = doc.copy()
            optimized_doc["payload"] = optimized_payload

            optimized_docs.append(optimized_doc)

        return optimized_docs

    def _optimize_text(self, text: str, max_tokens: int) -> str:
        """
        DEPRECATED: Старый метод оптимизации текста.
        Используйте _optimize_text_markdown для сохранения Markdown структуры.
        """
        return self._optimize_text_markdown(text, max_tokens)

    def _optimize_text_markdown(self, text: str, max_tokens: int, query: str = "") -> str:
        """
        Оптимизирует текст с сохранением Markdown структуры.
        Режет по абзацам, а не по предложениям, чтобы не ломать списки и структуру.
        """
        if not text:
            return ""

        # Оценка текущих токенов
        current_tokens = self._estimate_tokens(text)

        if current_tokens <= max_tokens:
            return text  # Текст уже оптимального размера

        max_chars = int(max_tokens * 4)  # Примерно 4 символа на токен
        return self._truncate_by_paragraphs(text, max_chars=max_chars)

    def _split_markdown_blocks(self, text: str) -> List[str]:
        blocks: List[str] = []
        buffer: List[str] = []
        in_code_block = False

        for line in text.splitlines():
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code_block:
                    buffer.append(line)
                    blocks.append("\n".join(buffer).strip("\n"))
                    buffer = []
                    in_code_block = False
                else:
                    if buffer:
                        blocks.append("\n".join(buffer).strip("\n"))
                        buffer = []
                    in_code_block = True
                    buffer.append(line)
                continue

            if in_code_block:
                buffer.append(line)
                continue

            if not stripped:
                if buffer:
                    blocks.append("\n".join(buffer).strip("\n"))
                    buffer = []
                continue

            buffer.append(line)

        if buffer:
            blocks.append("\n".join(buffer).strip("\n"))

        return [block for block in blocks if block.strip()]

    def _truncate_block(self, block: str, max_chars: int) -> str:
        if len(block) <= max_chars:
            return block

        stripped = block.strip()
        if stripped.startswith("```"):
            truncated = block[: max(max_chars - 4, 0)].rstrip()
            if not truncated.endswith("```"):
                truncated = f"{truncated}\n```"
            return truncated

        lines = block.splitlines()
        acc: List[str] = []
        current = 0
        for line in lines:
            line_len = len(line)
            if current + line_len <= max_chars:
                acc.append(line)
                current += line_len + 1
            else:
                if not acc:
                    acc.append(line[:max_chars])
                break

        return "\n".join(acc).strip()

    def _truncate_by_paragraphs(self, text: str, max_chars: int) -> str:
        if not text:
            return ""

        blocks = self._split_markdown_blocks(text)
        if not blocks:
            return text[:max_chars]

        assembled = ""
        for block in blocks:
            block = block.strip("\n")
            if not block:
                continue
            candidate = f"{assembled}\n\n{block}" if assembled else block
            if len(candidate) <= max_chars:
                assembled = candidate
                continue

            remaining = max_chars - len(assembled) - (2 if assembled else 0)
            if remaining > 0:
                truncated = self._truncate_block(block, remaining)
                if truncated:
                    assembled = f"{assembled}\n\n{truncated}" if assembled else truncated
            break

        return assembled.strip()

    def _estimate_tokens(self, text: str) -> int:
        """Оценивает количество токенов в тексте"""
        if not text:
            return 0
        # Улучшенная оценка: примерно 3.5 символа на токен для русского текста
        return int(len(text) / 3.5)

    def _is_list_intent(self, query: str) -> bool:
        """
        Определяет, является ли запрос списочным (требующим перечисления).

        Списочные запросы требуют особой обработки:
        - Минимальное количество документов (1-2)
        - Извлечение конкретных разделов по заголовкам
        - Сохранение полной Markdown структуры без обрезки
        """
        if not query:
            return False
        matched = bool(LIST_INTENT_PATTERN.search(query))
        if matched:
            logger.info("List intent detected via strict каналы pattern")
        return matched

    def _handle_list_intent(self, documents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Обрабатывает запросы списочного типа по строгому сценарию «extract mode».

        Берем только первый документ, пытаемся вытащить раздел `## Каналы`
        (без изменения Markdown) и возвращаем его целиком.
        """
        top_doc = documents[0]
        payload = top_doc.get("payload", {}) or {}
        original_text = payload.get("text", "") or ""

        extracted_text = extract_markdown_section(
            original_text,
            heading_regex=r"^##\s+Каналы",
            max_chars=8000,
        )

        if not extracted_text.strip():
            logger.info("List intent: section '## Каналы' not found, falling back to full document")
            max_chars = int(self.max_context_tokens * (1 - self.reserve_for_list_response)) * 4
            extracted_text = self._truncate_by_paragraphs(original_text, max_chars=max_chars)

        optimized_payload = payload.copy()
        optimized_payload["text"] = extracted_text
        optimized_payload["original_length"] = len(original_text)
        optimized_payload["optimized_length"] = len(extracted_text)
        optimized_payload["list_mode"] = True

        optimized_doc = top_doc.copy()
        optimized_doc["payload"] = optimized_payload

        logger.info(
            f"List intent result: 1 doc, original_len={len(original_text)}, optimized_len={len(extracted_text)}"
        )
        return [optimized_doc]



def extract_markdown_section(
    text: str,
    heading_regex: str = r"^##\s+Каналы",
    max_chars: int = 8000,
) -> str:
    """
    Извлекает Markdown-раздел, начиная с заголовка, до следующего заголовка того же уровня.
    """
    if not text:
        return ""

    pattern = re.compile(heading_regex, re.IGNORECASE | re.MULTILINE)
    lines = text.splitlines()
    start_idx: Optional[int] = None
    heading_level = 2

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if pattern.match(stripped):
            heading_match = re.match(r"^(#{1,6})\s+", stripped)
            heading_level = len(heading_match.group(1)) if heading_match else 2
            start_idx = i
            logger.debug(f"extract_markdown_section: found heading at line {i} level {heading_level}")
            break

    if start_idx is None:
        logger.debug("extract_markdown_section: target heading not found")
        return ""

    collected: List[str] = []
    current_length = 0

    for line in lines[start_idx:]:
        stripped = line.strip()
        if collected:
            heading_match = re.match(r"^(#{1,6})\s+", stripped)
            if heading_match and len(heading_match.group(1)) <= heading_level:
                logger.debug("extract_markdown_section: next heading encountered, stopping")
                break

        if current_length + len(line) + 1 > max_chars:
            logger.debug("extract_markdown_section: max_chars reached, truncating section")
            break

        collected.append(line)
        current_length += len(line) + 1

    return "\n".join(collected).strip()


# Глобальный экземпляр
context_optimizer = ContextOptimizer()


def optimize_context(query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Module-level proxy для совместимости с внешним API."""
    return context_optimizer.optimize_context(query, documents)
