"""
LLM Router - маршрутизатор для работы с различными LLM провайдерами

Модуль обеспечивает единообразный интерфейс для работы с разными LLM провайдерами
(Yandex GPT, GPT-5, DeepSeek) с автоматическим fallback'ом при недоступности.

Основные функции:
- Генерация ответов с использованием контекста документов
- Автоматический fallback между провайдерами
- Форматирование ответов для Telegram
- Обработка system-промптов и пользовательских запросов

Используется в RAG-пайплайне: Context Optimization → LLM Router → Formatted Answer
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
import requests
import telegramify_markdown
from app.config import CONFIG
from loguru import logger
from app.utils import write_debug_event


DEFAULT_LLM = CONFIG.default_llm


def _build_messages(prompt: str, system_prompt: Optional[str] = None, content_key: str = "content") -> List[Dict[str, str]]:
    """
    Строит массив сообщений для LLM API.

    Args:
        prompt: Пользовательский промпт
        system_prompt: Системный промпт (опционально)
        content_key: Ключ для содержимого сообщения ("content" или "text")

    Returns:
        Список сообщений в формате для LLM API
    """
    messages = []

    # Добавляем system-промпт, если он указан
    if system_prompt:
        messages.append({
            "role": "system",
            content_key: system_prompt
        })

    # Добавляем пользовательский промпт
    messages.append({
        "role": "user",
        content_key: prompt
    })

    return messages


def _escape_markdown_v2(text: str) -> str:
    """Экранирует спецсимволы Telegram MarkdownV2, не трогая уже экранированные.
    Экранируемые символы: _ * [ ] ( ) ~ ` > # + - = | { } . ! и обратный слэш.
    """
    # Сначала экранируем обратный слэш
    text = re.sub(r"\\", r"\\\\", text)
    # Затем экранируем спецсимволы, КРОМЕ # в начале строки (заголовки)
    # Не экранируем #, если он стоит как Markdown заголовок: ^#{1,6}\s
    def repl(m: re.Match[str]) -> str:
        ch = m.group(1)
        if ch == '#':
            # Проверяем контекст: начало строки и последовательность ### пробел
            start = m.start(1)
            # Найдём начало строки
            line_start = text.rfind('\n', 0, start) + 1
            prefix = text[line_start:start]
            # Если перед # только пробелы и дальше идёт пробел после группы # — не экранируем
            # Упрощённо: не экранируем #, оставляем как есть
            return '#'
        return '\\' + ch

    return re.sub(r"(?<!\\)([_*\[\]()~`>#+\-=|{}.!])", repl, text)


def _yandex_complete(prompt: str, max_tokens: int = 800, temperature: Optional[float] = None, top_p: Optional[float] = None, system_prompt: Optional[str] = None) -> str:
    """
    Генерирует ответ через Yandex GPT API.

    Args:
        prompt: Пользовательский промпт
        max_tokens: Максимальное количество токенов
        temperature: Температура генерации (0.0-1.0)
        top_p: Top-p параметр для nucleus sampling
        system_prompt: Системный промпт

    Returns:
        Сгенерированный текст ответа

    Raises:
        Exception: При ошибках API или сети
    """
    url = f"{CONFIG.yandex_api_url}/completion"
    logger.debug(f"Yandex URL: {url}")
    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }

    # Параметры генерации с fallback значениями
    _temperature = 0.2 if temperature is None else float(temperature)
    _top_p = 1.0 if top_p is None else float(top_p)

    # Используем общую функцию для формирования messages
    messages = _build_messages(prompt, system_prompt, content_key="text")

    payload = {
        "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
        "completionOptions": {
            "stream": False,
            "temperature": _temperature,
            "topP": _top_p,
            "maxTokens": str(min(max_tokens, CONFIG.yandex_max_tokens))
        },
        "messages": messages
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        status = resp.status_code
        body_preview = resp.text[:500]
    except Exception as e:
        logger.error(f"Yandex request failed: {type(e).__name__}: {e}")
        raise
    if status != 200:
        logger.error(f"Yandex HTTP {status}: {body_preview}")
        resp.raise_for_status()
    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"Yandex JSON parse error: {e}; body preview={body_preview!r}")
        raise
    # Ответ Yandex может отличаться; извлекаем текст из completion
    try:
        text = data["result"]["alternatives"][0]["message"]["text"]
    except Exception:
        text = str(data)
    # Логируем сырой ответ (repr, чтобы видеть экранирования)
    logger.debug(f"LLM[Yandex] raw len={len(text)} preview={text[:200]!r}")
    return text


def _gpt5_complete(prompt: str, max_tokens: int = 800, system_prompt: Optional[str] = None) -> str:
    """
    Генерирует ответ через GPT-5 API.

    Args:
        prompt: Пользовательский промпт
        max_tokens: Максимальное количество токенов
        system_prompt: Системный промпт

    Returns:
        Сгенерированный текст ответа

    Raises:
        RuntimeError: Если не настроены credentials для GPT-5
        Exception: При ошибках API или сети
    """
    if not CONFIG.gpt5_api_url or not CONFIG.gpt5_api_key:
        raise RuntimeError("GPT-5 credentials are not configured")

    headers = {"Authorization": f"Bearer {CONFIG.gpt5_api_key}", "Content-Type": "application/json"}

    # Используем общую функцию для формирования messages
    messages = _build_messages(prompt, system_prompt, content_key="content")

    payload = {"model": CONFIG.gpt5_model or "gpt5", "messages": messages, "max_tokens": max_tokens}
    resp = requests.post(CONFIG.gpt5_api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = str(data)
    logger.debug(f"LLM[GPT5] raw len={len(text)} preview={text[:200]!r}")
    return text


def _deepseek_complete(prompt: str, max_tokens: int = 800, system_prompt: Optional[str] = None) -> str:
    """
    Генерирует ответ через DeepSeek API.

    Args:
        prompt: Пользовательский промпт
        max_tokens: Максимальное количество токенов
        system_prompt: Системный промпт

    Returns:
        Сгенерированный текст ответа

    Raises:
        Exception: При ошибках API или сети
    """
    headers = {"Authorization": f"Bearer {CONFIG.deepseek_api_key}", "Content-Type": "application/json"}

    # Используем общую функцию для формирования messages
    messages = _build_messages(prompt, system_prompt, content_key="content")

    payload = {"model": CONFIG.deepseek_model, "messages": messages, "max_tokens": max_tokens}
    resp = requests.post(CONFIG.deepseek_api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = str(data)
    logger.debug(f"LLM[DEEPSEEK] raw len={len(text)} preview={text[:200]!r}")
    return text


def _format_for_telegram(text: str) -> str:
    """
    Форматирует текст для отображения в Telegram через MarkdownV2.

    Args:
        text: Исходный текст в Markdown формате

    Returns:
        Текст, отформатированный для Telegram MarkdownV2
    """
    try:
        # Используем markdownify для конвертации в MarkdownV2
        out = telegramify_markdown.markdownify(text)
        if out is None:
            logger.warning("telegramify_markdown.markdownify returned None, using original text")
            return text
        logger.debug("telegramify_markdown.markdownify: preview=%s", out[:120])
        return out
    except Exception as e:
        logger.warning(f"telegramify_markdown.markdownify failed: {type(e).__name__}: {e}")

    # Fallback: возвращаем исходный текст
    return text


def generate_answer(query: str, context: List[Dict[str, Any]], policy: Optional[Dict[str, Any]] = None) -> str:
    """
    Генерирует ответ на основе контекста документов с использованием LLM провайдеров.

    Формирует структурированный промпт с контекстом документов и источниками,
    затем пытается получить ответ от провайдеров в порядке fallback'а.

    Args:
        query: Пользовательский запрос
        context: Список документов с контекстом (после оптимизации)
        policy: Дополнительные параметры политики (не используется)

    Returns:
        Сгенерированный ответ, отформатированный для Telegram

    Fallback порядок:
        1. DEFAULT_LLM (обычно Yandex GPT)
        2. GPT-5
        3. DeepSeek
    """
    policy = policy or {}
    # Формируем промпт с цитатами и ссылками «Подробнее»
    urls: list[str] = []
    content_blocks: list[str] = []

    logger.info(f"LLM Router: Processing {len(context)} context documents")

    for i, c in enumerate(context):
        payload = c.get("payload", {}) or {}
        url = payload.get("url")
        if url:
            urls.append(str(url))

        # Добавляем контент документа
        text = payload.get("text", "")
        title = payload.get("title", "")

        logger.info(f"LLM Router: Document {i+1}: title='{title}', text_len={len(text)}, url='{url}'")

        if text:
            # Формируем структурированный блок с заголовком и контентом
            content_block = f"📄 {title}\n" if title else f"📄 Документ\n"
            if url:
                content_block += f"🔗 {url}\n"
            content_block += f"📝 {text}"  # Используем полный текст без обрезки
            content_blocks.append(content_block)
            logger.info(f"LLM Router: Added content block {len(content_blocks)} with {len(text)} chars")
        else:
            logger.warning(f"LLM Router: Document {i+1} has empty text!")

    logger.info(f"LLM Router: Total content blocks: {len(content_blocks)}, total URLs: {len(urls)}")

    sources_block = "\n".join(urls)
    context_block = "\n\n".join(content_blocks)

    # System-промпт для профессионального ассистента
    system_prompt = (
        "Ты профессиональный ассистент edna Chat Center, специализирующийся на мультидокументном анализе. "
        "Твоя задача — объединять информацию из разных источников, сохраняя логическую связность и структурированность ответа. "
        "Обращай внимание на заголовки документов (📄) для лучшего понимания контекста. "
        "Стремись к краткости и информативности, но не упусти важные детали. "
        "При недостатке информации предоставляй безопасные общие рекомендации и предлагай релевантные ссылки для дальнейшего изучения темы."
    )

    # Пользовательский промпт с контекстом
    prompt = (
        f"Вопрос: {query}\n\n"
        f"Контекст документов:\n{context_block}\n\n"
        f"Ссылки на источники:\n{sources_block}\n\n"
        "Отвечай по-русски, кратко и по делу. Используй ТОЛЬКО информацию из переданного контекста документов. "
        "Если фактов из контекста недостаточно, честно напиши: «В контексте нет данных», "
        "и дай безопасные общие рекомендации (без домыслов), затем предложи посмотреть по ссылкам.\n\n"
        "Формат ответа — обычный Markdown:\n"
        "- используй **жирный**, *курсив*, списки с «- » или нумерованные «1.»;\n"
        "- ссылки только в формате [текст](URL); не выдумывай URL;\n"
        "- код/команды — в тройных кавычках ``` (без языка);\n"
        "- избегай лишних символов, которые могут вызвать проблемы при форматировании."
    )

    order = [DEFAULT_LLM, "GPT5", "DEEPSEEK"]
    for provider in order:
        try:
            logger.debug(f"LLM provider attempt: {provider}")
            if provider == "YANDEX":
                answer = _yandex_complete(prompt, system_prompt=system_prompt)
                logger.debug(f"Before format [YANDEX] preview={answer[:200]!r}")
                write_debug_event("llm.answer", {"provider": "YANDEX", "len": len(answer), "preview": answer[:500]})
                return _format_for_telegram(answer)
            if provider == "GPT5":
                answer = _gpt5_complete(prompt, system_prompt=system_prompt)
                logger.debug(f"Before format [GPT5] preview={answer[:200]!r}")
                write_debug_event("llm.answer", {"provider": "GPT5", "len": len(answer), "preview": answer[:500]})
                return _format_for_telegram(answer)
            if provider == "DEEPSEEK":
                answer = _deepseek_complete(prompt, system_prompt=system_prompt)
                logger.debug(f"Before format [DEEPSEEK] preview={answer[:200]!r}")
                write_debug_event("llm.answer", {"provider": "DEEPSEEK", "len": len(answer), "preview": answer[:500]})
                return _format_for_telegram(answer)
        except Exception as e:
            # Логируем причину фолбэка по провайдеру
            write_debug_event("llm.provider_error", {"provider": provider, "error": f"{type(e).__name__}: {e}"})
            logger.warning(f"Provider {provider} failed: {type(e).__name__}: {e}; trying next")
            continue
    return "Извините, провайдеры LLM недоступны. Попробуйте позже."
