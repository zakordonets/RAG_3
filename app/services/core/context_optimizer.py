#!/usr/bin/env python3
"""
Оптимизатор контекста для RAG-системы

Модуль оптимизирует контекст перед отправкой в LLM, управляя размером токенов
и адаптивно выбирая количество документов в зависимости от сложности запроса.

Используется в RAG-пайплайне: Search → Reranking → Context Optimization → LLM

Основные функции:
- Управление лимитами токенов для LLM
- Адаптивный выбор количества документов
- Умная обрезка текста с сохранением важных частей
- Резервирование токенов под ответ LLM
"""
import re
from typing import List, Dict, Any, Tuple
from loguru import logger


class ContextOptimizer:
    """
    Оптимизирует контекст для RAG-системы перед отправкой в LLM.

    Управляет размером токенов, адаптивно выбирает количество документов
    и оптимизирует текст с сохранением важных частей.
    """

    def __init__(self):
        # Настройки управления токенами
        self.max_context_tokens = 2000  # Максимальный контекст для LLM
        self.min_context_tokens = 1000  # Минимальный контекст
        self.reserve_for_response = 0.35  # 35% резерв под ответ и промпт

        # Адаптивные лимиты
        self.max_documents = 7
        self.min_documents = 3
        self.target_chunk_tokens = 400

    def optimize_context(self, documents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
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
        optimized_docs = self._optimize_chunk_sizes(documents[:target_docs], available_tokens)

        # 5. Проверяем итоговый размер
        total_tokens = sum(self._estimate_tokens(doc.get("payload", {}).get("text", ""))
                          for doc in optimized_docs)

        logger.info(f"Final context: {len(optimized_docs)} docs, {total_tokens} tokens")

        return optimized_docs

    def _analyze_query_complexity(self, query: str) -> str:
        """Анализирует сложность запроса"""
        query_lower = query.lower()

        # Простые вопросы
        simple_indicators = ["что такое", "как называется", "где находится", "когда"]
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
            return min(4, available_docs)  # Меньше документов для простых вопросов
        elif complexity == "complex":
            return min(7, available_docs)  # Больше документов для сложных вопросов
        else:
            return min(6, available_docs)  # Стандартное количество

    def _optimize_chunk_sizes(self, documents: List[Dict[str, Any]], available_tokens: int) -> List[Dict[str, Any]]:
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
                max_tokens = min(tokens_per_doc * 1.5, 600)
            else:
                max_tokens = min(tokens_per_doc, 400)

            # Оптимизируем текст
            optimized_text = self._optimize_text(original_text, max_tokens)

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
        """Оптимизирует текст с сохранением важных частей"""
        if not text:
            return ""

        # Оценка текущих токенов
        current_tokens = self._estimate_tokens(text)

        if current_tokens <= max_tokens:
            return text  # Текст уже оптимального размера

        # Стратегия оптимизации: приоритет началу + ключевые предложения
        max_chars = max_tokens * 4  # Примерно 4 символа на токен

        # Разбиваем на предложения
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return text[:max_chars]

        # Берем начало (первые 2-3 предложения)
        result_sentences = sentences[:3]
        current_length = sum(len(s) for s in result_sentences)

        # Добавляем ключевые предложения из середины и конца
        if current_length < max_chars * 0.7:  # Если еще есть место
            # Берем средние предложения
            mid_start = len(sentences) // 3
            mid_end = len(sentences) * 2 // 3
            mid_sentences = sentences[mid_start:mid_end]

            for sentence in mid_sentences:
                if current_length + len(sentence) > max_chars:
                    break
                result_sentences.append(sentence)
                current_length += len(sentence)

        # Добавляем конец, если есть место
        if current_length < max_chars * 0.9:
            end_sentences = sentences[-2:]
            for sentence in end_sentences:
                if current_length + len(sentence) > max_chars:
                    break
                result_sentences.append(sentence)
                current_length += len(sentence)

        result = '. '.join(result_sentences)

        # Добавляем точку в конце, если нужно
        if result and not result.endswith(('.', '!', '?')):
            result += '.'

        return result

    def _estimate_tokens(self, text: str) -> int:
        """Оценивает количество токенов в тексте"""
        if not text:
            return 0
        # Упрощенная оценка: примерно 4 символа на токен для русского текста
        return len(text) // 4


# Глобальный экземпляр
context_optimizer = ContextOptimizer()
