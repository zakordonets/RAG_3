"""
Обработка пользовательских запросов для RAG-системы

Модуль выполняет предварительную обработку пользовательских запросов:
- Нормализация текста и аббревиатур
- Извлечение доменных сущностей
- Декомпозиция сложных запросов
- Настройка boosts для поиска

Используется в RAG-пайплайне: User Query → Query Processing → Embeddings → Search
"""
from __future__ import annotations

from typing import Any, Dict, List


def extract_entities(text: str) -> List[str]:
    """
    Извлекает доменные сущности из пользовательского запроса.

    Args:
        text: Исходный текст запроса

    Returns:
        Список найденных доменных терминов

    Note:
        Использует простую эвристику. В будущем можно заменить на ML-экстракцию
        или специализированные словари домена.
    """
    if not text:
        return []

    # Доменные термины edna Chat Center
    domain_entities = [
        "арм агента", "арм супервайзера", "арм администратора",
        "api", "faq", "release notes", "чат-боты",
        "интеграция", "настройка", "конфигурация", "развертывание"
    ]

    lowered = text.lower()
    return [entity for entity in domain_entities if entity in lowered]


def rewrite_query(text: str) -> str:
    """
    Нормализует пользовательский запрос, заменяя аббревиатуры и синонимы.

    Args:
        text: Исходный текст запроса

    Returns:
        Нормализованный текст с замененными аббревиатурами
    """
    if not text:
        return text

    # Словарь замен аббревиатур и синонимов
    replacements = {
        "РН": "Release Notes",
        "рн": "Release Notes",
        "АРМ": "АРМ",
        "арм": "АРМ",
        "API": "API",
        "api": "API",
        "FAQ": "FAQ",
        "faq": "FAQ"
    }

    normalized = text
    for abbrev, full_form in replacements.items():
        normalized = normalized.replace(abbrev, full_form)

    return normalized


def maybe_decompose(text: str, max_depth: int = 3) -> List[str]:
    """
    Декомпозирует сложные запросы на более простые части.

    Args:
        text: Исходный текст запроса
        max_depth: Максимальное количество частей для разбиения

    Returns:
        Список частей запроса (если декомпозиция возможна)

    Note:
        В текущей реализации разбивает только по " и ".
        В будущем можно добавить более сложную логику декомпозиции.
    """
    if not text:
        return []

    # Простая декомпозиция по союзу " и "
    parts = [part.strip() for part in text.split(" и ") if part.strip()]

    # Возвращаем только если есть несколько частей
    if len(parts) > 1:
        return parts[:max_depth]

    return []


def process_query(text: str) -> Dict[str, Any]:
    """
    Основная функция обработки пользовательского запроса.

    Выполняет полный цикл обработки: извлечение сущностей, нормализация,
    декомпозиция и настройка boosts для поиска.

    Args:
        text: Исходный текст пользовательского запроса

    Returns:
        Словарь с результатами обработки:
        - normalized_text: Нормализованный текст (используется в пайплайне)
        - entities: Извлеченные доменные сущности (для будущего использования)
        - boosts: Настройки повышения релевантности (используется в поиске)
        - subqueries: Декомпозированные части запроса (для будущего использования)
    """
    # Извлекаем доменные сущности
    entities = extract_entities(text)

    # Нормализуем запрос
    normalized = rewrite_query(text)

    # Пытаемся декомпозировать на части
    subqueries = maybe_decompose(normalized)

    # Настраиваем boosts для поиска
    boosts = _calculate_boosts(normalized)

    return {
        "normalized_text": normalized,
        "entities": entities,
        "boosts": boosts,
        "subqueries": subqueries
    }


def _calculate_boosts(normalized_text: str) -> Dict[str, float]:
    """
    Вычисляет коэффициенты повышения релевантности для разных типов документов.

    Args:
        normalized_text: Нормализованный текст запроса

    Returns:
        Словарь с коэффициентами boost для разных типов контента
    """
    boosts = {}
    text_lower = normalized_text.lower()

    # Повышаем релевантность FAQ для вопросов
    question_words = ["как", "что", "почему", "где", "когда", "зачем"]
    if any(word in text_lower for word in question_words):
        boosts["faq"] = 1.2

    # Повышаем релевантность API документации для технических запросов
    tech_words = ["api", "интеграция", "настройка", "конфигурация"]
    if any(word in text_lower for word in tech_words):
        boosts["api"] = 1.1

    # Повышаем релевантность Release Notes для запросов об обновлениях
    update_words = ["release notes", "обновление", "новая версия", "изменения"]
    if any(word in text_lower for word in update_words):
        boosts["release_notes"] = 1.15

    return boosts
