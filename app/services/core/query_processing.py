"""
Обработка пользовательских запросов для RAG-системы

Модуль выполняет предварительную обработку пользовательских запросов:
- Нормализация текста и аббревиатур
- Извлечение доменных сущностей
- Декомпозиция сложных запросов
- Настройка boosts для поиска
- Классификация типа запроса для выбора стратегии поиска (Query Type Routing)

Используется в RAG-пайплайне: User Query → Query Processing → Embeddings → Search
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

from app.config import CONFIG


# =============================================================================
# Query Type Classification (вдохновлено LlamaIndex Query Routing)
# =============================================================================

class QueryType(Enum):
    """
    Типы пользовательских запросов для выбора оптимальной стратегии поиска.

    Каждый тип требует разных параметров retrieval:
    - FACTUAL: короткие ответы, меньше документов
    - PROCEDURAL: пошаговые инструкции, больше контекста
    - COMPARATIVE: сравнения, нужно несколько источников
    - TROUBLESHOOTING: диагностика проблем, глубокий поиск
    - LIST: перечисления, специальный режим извлечения
    - EXPLORATORY: общие вопросы, широкий поиск
    """
    FACTUAL = "factual"           # "Что такое X?", "Где находится Y?"
    PROCEDURAL = "procedural"     # "Как сделать X?", "Настройка Y"
    COMPARATIVE = "comparative"   # "Чем X отличается от Y?", "Разница между"
    TROUBLESHOOTING = "troubleshooting"  # "Ошибка X", "Не работает Y", "Почему?"
    LIST = "list"                 # "Какие есть X?", "Список Y", "Перечисли"
    EXPLORATORY = "exploratory"   # Общие вопросы без чёткой категории


@dataclass
class RetrievalStrategy:
    """
    Стратегия поиска для конкретного типа запроса.

    Attributes:
        k: Количество документов для retrieval
        rerank_top_n: Количество документов после reranking
        use_auto_merge: Использовать ли auto-merge соседних чанков
        context_reserve: Резерв токенов под ответ LLM (0.0-1.0)
        boost_multiplier: Множитель для page_type boosts
    """
    k: int
    rerank_top_n: int
    use_auto_merge: bool
    context_reserve: float
    boost_multiplier: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует стратегию в словарь для передачи в пайплайн."""
        return {
            "k": self.k,
            "rerank_top_n": self.rerank_top_n,
            "use_auto_merge": self.use_auto_merge,
            "context_reserve": self.context_reserve,
            "boost_multiplier": self.boost_multiplier,
        }


# Предопределённые стратегии для каждого типа запроса
RETRIEVAL_STRATEGIES: Dict[QueryType, RetrievalStrategy] = {
    QueryType.FACTUAL: RetrievalStrategy(
        k=15,              # Меньше кандидатов — ответ обычно в топ-документах
        rerank_top_n=3,    # Мало документов в контексте
        use_auto_merge=False,  # Не нужно расширение контекста
        context_reserve=0.4,   # Больше места для точного ответа
        boost_multiplier=1.0,
    ),
    QueryType.PROCEDURAL: RetrievalStrategy(
        k=25,              # Больше кандидатов для пошаговых инструкций
        rerank_top_n=6,    # Нужно больше контекста
        use_auto_merge=True,   # Расширяем чанки для полных инструкций
        context_reserve=0.3,   # Меньше резерва — больше контекста
        boost_multiplier=1.2,  # Усиливаем page_type boosts
    ),
    QueryType.COMPARATIVE: RetrievalStrategy(
        k=20,              # Нужно найти информацию о нескольких сущностях
        rerank_top_n=5,    # Средний размер контекста
        use_auto_merge=False,  # Не объединяем — нужны разные источники
        context_reserve=0.35,
        boost_multiplier=1.0,
    ),
    QueryType.TROUBLESHOOTING: RetrievalStrategy(
        k=30,              # Глубокий поиск для диагностики
        rerank_top_n=7,    # Много контекста для анализа проблемы
        use_auto_merge=True,   # Расширяем для полного описания решения
        context_reserve=0.3,
        boost_multiplier=1.3,  # Сильный boost для FAQ и troubleshooting
    ),
    QueryType.LIST: RetrievalStrategy(
        k=10,              # Минимальный поиск
        rerank_top_n=2,    # Один-два документа со списком
        use_auto_merge=False,  # Не объединяем
        context_reserve=0.25,  # Минимальный резерв — списки компактны
        boost_multiplier=1.0,
    ),
    QueryType.EXPLORATORY: RetrievalStrategy(
        k=20,              # Широкий поиск
        rerank_top_n=5,    # Средний контекст
        use_auto_merge=True,
        context_reserve=0.35,
        boost_multiplier=1.0,
    ),
}


def classify_query_type(query: str) -> QueryType:
    """
    Классифицирует тип запроса для выбора оптимальной стратегии retrieval.

    Использует эвристики на основе ключевых слов и паттернов.
    Порядок проверок важен — более специфичные паттерны проверяются первыми.

    Args:
        query: Текст пользовательского запроса

    Returns:
        QueryType: Классифицированный тип запроса
    """
    if not query:
        return QueryType.EXPLORATORY

    q = query.lower().strip()

    # 1. LIST — перечисления (проверяем первым, т.к. специфичный паттерн)
    list_patterns = [
        "какие есть", "какие бывают", "список", "перечисли", "перечень",
        "все варианты", "все способы", "все типы", "все виды",
        "какие каналы", "какие интеграции", "какие методы"
    ]
    if any(p in q for p in list_patterns):
        logger.debug(f"Query classified as LIST: '{query[:50]}...'")
        return QueryType.LIST

    # 2. TROUBLESHOOTING — проблемы и ошибки
    troubleshooting_patterns = [
        "ошибка", "не работает", "не могу", "проблема", "сбой",
        "не удаётся", "не удается", "не получается", "почему не",
        "failed", "error", "issue", "баг", "bug", "не отображается",
        "не приходит", "не отправляется", "зависает", "падает"
    ]
    if any(p in q for p in troubleshooting_patterns):
        logger.debug(f"Query classified as TROUBLESHOOTING: '{query[:50]}...'")
        return QueryType.TROUBLESHOOTING

    # 3. COMPARATIVE — сравнения
    comparative_patterns = [
        "отличие", "отличается", "разница", "различие", "сравн",
        "лучше", "хуже", "vs", "versus", "или", " чем ",
        "в отличие от", "по сравнению"
    ]
    if any(p in q for p in comparative_patterns):
        logger.debug(f"Query classified as COMPARATIVE: '{query[:50]}...'")
        return QueryType.COMPARATIVE

    # 4. PROCEDURAL — инструкции и настройка
    procedural_patterns = [
        "как настроить", "как создать", "как добавить", "как удалить",
        "как подключить", "как включить", "как выключить", "как изменить",
        "пошагово", "пошаговая", "инструкция", "руководство",
        "настройка", "конфигурация", "установка", "развёртывание",
        "развертывание", "интеграция с", "подключение"
    ]
    if any(p in q for p in procedural_patterns):
        logger.debug(f"Query classified as PROCEDURAL: '{query[:50]}...'")
        return QueryType.PROCEDURAL

    # 5. FACTUAL — фактические вопросы
    factual_patterns = [
        "что такое", "что значит", "что означает", "определение",
        "где находится", "где расположен", "когда", "сколько",
        "кто", "какой порт", "какой адрес", "какая версия"
    ]
    if any(p in q for p in factual_patterns):
        logger.debug(f"Query classified as FACTUAL: '{query[:50]}...'")
        return QueryType.FACTUAL

    # 6. Fallback — если ничего не подошло
    # Проверяем общие вопросительные слова для FACTUAL
    if q.startswith(("что ", "где ", "когда ", "кто ", "сколько ")):
        logger.debug(f"Query classified as FACTUAL (fallback): '{query[:50]}...'")
        return QueryType.FACTUAL

    # Проверяем "как" для PROCEDURAL
    if q.startswith("как "):
        logger.debug(f"Query classified as PROCEDURAL (fallback): '{query[:50]}...'")
        return QueryType.PROCEDURAL

    logger.debug(f"Query classified as EXPLORATORY (default): '{query[:50]}...'")
    return QueryType.EXPLORATORY


def get_retrieval_strategy(query_type: QueryType) -> RetrievalStrategy:
    """
    Возвращает стратегию retrieval для указанного типа запроса.

    Args:
        query_type: Тип запроса

    Returns:
        RetrievalStrategy: Параметры стратегии поиска
    """
    return RETRIEVAL_STRATEGIES.get(query_type, RETRIEVAL_STRATEGIES[QueryType.EXPLORATORY])


def get_strategy_for_query(query: str) -> tuple[QueryType, RetrievalStrategy]:
    """
    Удобная функция для получения типа и стратегии одним вызовом.

    Args:
        query: Текст запроса

    Returns:
        tuple: (QueryType, RetrievalStrategy)
    """
    query_type = classify_query_type(query)
    strategy = get_retrieval_strategy(query_type)
    return query_type, strategy


# =============================================================================
# Existing Query Processing Functions
# =============================================================================


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
    декомпозиция, классификация типа и настройка boosts для поиска.

    Args:
        text: Исходный текст пользовательского запроса

    Returns:
        Словарь с результатами обработки:
        - normalized_text: Нормализованный текст (используется в пайплайне)
        - entities: Извлеченные доменные сущности (для будущего использования)
        - boosts: Настройки повышения релевантности (используется в поиске)
        - subqueries: Декомпозированные части запроса (для будущего использования)
        - query_type: Классифицированный тип запроса (QueryType enum)
        - retrieval_strategy: Стратегия поиска для данного типа (dict)
    """
    # Извлекаем доменные сущности
    entities = extract_entities(text)

    # Нормализуем запрос
    normalized = rewrite_query(text)

    # Пытаемся декомпозировать на части
    subqueries = maybe_decompose(normalized)

    # Классифицируем тип запроса и получаем стратегию
    query_type, strategy = get_strategy_for_query(normalized)

    # Настраиваем boosts для поиска (с учётом множителя из стратегии)
    page_boosts, group_boosts = _calculate_boosts(normalized)

    # Применяем boost_multiplier из стратегии
    if strategy.boost_multiplier != 1.0:
        page_boosts = {k: v * strategy.boost_multiplier for k, v in page_boosts.items()}
        group_boosts = {k: v * strategy.boost_multiplier for k, v in group_boosts.items()}

    logger.info(
        f"Query processed: type={query_type.value}, "
        f"k={strategy.k}, rerank_top_n={strategy.rerank_top_n}, "
        f"auto_merge={strategy.use_auto_merge}"
    )

    return {
        "normalized_text": normalized,
        "entities": entities,
        "boosts": page_boosts,
        "group_boosts": group_boosts,
        "subqueries": subqueries,
        "query_type": query_type,
        "retrieval_strategy": strategy.to_dict(),
    }


def _calculate_boosts(normalized_text: str) -> tuple[Dict[str, float], Dict[str, float]]:
    """
    Вычисляет коэффициенты повышения релевантности для разных типов документов.

    Args:
        normalized_text: Нормализованный текст запроса

    Returns:
        Словарь с коэффициентами boost для разных типов контента
    """
    boosts: Dict[str, float] = {}
    group_boosts: Dict[str, float] = {}
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

    for label, config_entry in CONFIG.group_boost_synonyms.items():
        normalized_label = label.lower().strip()
        if not normalized_label:
            continue

        synonyms: list[str] = []
        weight: float | None = None

        if isinstance(config_entry, dict):
            raw_synonyms = config_entry.get("synonyms", [])
            if isinstance(raw_synonyms, list):
                synonyms = [
                    str(keyword).lower().strip()
                    for keyword in raw_synonyms
                    if str(keyword).strip()
                ]
            raw_weight = config_entry.get("weight")
            try:
                if raw_weight is not None:
                    weight = float(raw_weight)
            except (TypeError, ValueError):
                weight = None
        else:
            continue

        terms = {normalized_label}
        terms.update(synonyms)
        if any(term and term in text_lower for term in terms):
            boost_value = weight if weight and weight > 0 else 1.25
            current = group_boosts.get(normalized_label, 1.0)
            group_boosts[normalized_label] = max(current, boost_value)

    return boosts, group_boosts
