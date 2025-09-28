from __future__ import annotations

from typing import Any
import re
import requests
import telegramify_markdown
from app.config import CONFIG
from loguru import logger
from app.log_utils import write_debug_event


DEFAULT_LLM = CONFIG.default_llm


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


def _yandex_complete(prompt: str, max_tokens: int = 800, temperature: float | None = None, top_p: float | None = None, system_prompt: str | None = None) -> str:
    url = f"{CONFIG.yandex_api_url}/completion"
    logger.debug(f"Yandex URL: {url}")
    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }
    # Allow deterministic overrides from callers (e.g., RAGAS evaluator)
    _temperature = 0.2 if temperature is None else float(temperature)
    _top_p = 1.0 if top_p is None else float(top_p)

    # Формируем массив сообщений с поддержкой system-роли
    messages = []

    # Добавляем system-промпт, если он указан
    if system_prompt:
        messages.append({
            "role": "system",
            "text": system_prompt
        })

    # Добавляем пользовательский промпт
    messages.append({
        "role": "user",
        "text": prompt
    })

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


def _gpt5_complete(prompt: str, max_tokens: int = 800, system_prompt: str | None = None) -> str:
    if not CONFIG.gpt5_api_url or not CONFIG.gpt5_api_key:
        raise RuntimeError("GPT-5 creds are not set")
    headers = {"Authorization": f"Bearer {CONFIG.gpt5_api_key}", "Content-Type": "application/json"}

    # Формируем массив сообщений с поддержкой system-роли
    messages = []

    # Добавляем system-промпт, если он указан
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    # Добавляем пользовательский промпт
    messages.append({
        "role": "user",
        "content": prompt
    })

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


def _deepseek_complete(prompt: str, max_tokens: int = 800, system_prompt: str | None = None) -> str:
    headers = {"Authorization": f"Bearer {CONFIG.deepseek_api_key}", "Content-Type": "application/json"}

    # Формируем массив сообщений с поддержкой system-роли
    messages = []

    # Добавляем system-промпт, если он указан
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    # Добавляем пользовательский промпт
    messages.append({
        "role": "user",
        "content": prompt
    })

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
    """Форматирует текст через telegramify_markdown.markdownify для MarkdownV2."""
    try:
        # Используем markdownify для конвертации в MarkdownV2
        out = telegramify_markdown.markdownify(text)
        if out is None:
            logger.warning("telegramify_markdown.markdownify returned None")
            return text
        logger.debug("telegramify_markdown.markdownify: preview=%s", out[:120])
        return out
    except Exception as e:
        logger.warning(f"telegramify_markdown.markdownify failed: {type(e).__name__}: {e}")

    # Фолбэк: возвращаем сырой текст
    return text


def generate_answer(query: str, context: list[dict], policy: dict[str, Any] | None = None) -> str:
    """
    Генерирует ответ, используя провайдер LLM согласно DEFAULT_LLM и fallback-порядку.
    - Формирует промпт с источниками (URL) и указанием добавлять "Подробнее".
    - Порядок: DEFAULT_LLM -> GPT5 -> DEEPSEEK.
    - Обрабатывает сетевые ошибки, возвращая следующее доступное решение.
    """
    policy = policy or {}
    # Формируем промпт с цитатами и ссылками «Подробнее»
    urls: list[str] = []
    content_blocks: list[str] = []
    for c in context:
        payload = c.get("payload", {}) or {}
        url = payload.get("url")
        if url:
            urls.append(str(url))

        # Добавляем контент документа
        text = payload.get("text", "")
        title = payload.get("title", "")
        if text:
            # Формируем структурированный блок с заголовком и контентом
            content_block = f"📄 {title}\n" if title else f"📄 Документ\n"
            content_block += f"🔗 {url}\n"
            content_block += f"📝 {text[:800]}..."  # Ограничиваем длину
            content_blocks.append(content_block)

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
