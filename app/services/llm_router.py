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


def _yandex_complete(prompt: str, max_tokens: int = 800) -> str:
    url = f"{CONFIG.yandex_api_url}/completion"
    logger.debug(f"Yandex URL: {url}")
    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": str(min(max_tokens, CONFIG.yandex_max_tokens))
        },
        "messages": [
            {
                "role": "user",
                "text": prompt
            }
        ]
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


def _gpt5_complete(prompt: str, max_tokens: int = 800) -> str:
    if not CONFIG.gpt5_api_url or not CONFIG.gpt5_api_key:
        raise RuntimeError("GPT-5 creds are not set")
    headers = {"Authorization": f"Bearer {CONFIG.gpt5_api_key}", "Content-Type": "application/json"}
    payload = {"model": CONFIG.gpt5_model or "gpt5", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    resp = requests.post(CONFIG.gpt5_api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        text = str(data)
    logger.debug(f"LLM[GPT5] raw len={len(text)} preview={text[:200]!r}")
    return text


def _deepseek_complete(prompt: str, max_tokens: int = 800) -> str:
    headers = {"Authorization": f"Bearer {CONFIG.deepseek_api_key}", "Content-Type": "application/json"}
    payload = {"model": CONFIG.deepseek_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
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
    for c in context:
        url = (c.get("payload", {}) or {}).get("url")
        if url:
            urls.append(str(url))
    sources_block = "\n".join(urls)
    prompt = (
        "Вы — ассистент edna Chat Center. Отвечайте по-русски, кратко и по делу.\n\n"
        "Используйте ТОЛЬКО информацию из переданного контекста (ссылки ниже). \n"
        "Если фактов из контекста недостаточно, честно напишите: «В контексте нет данных», \n"
        "и дайте безопасные общие рекомендации (без домыслов), затем предложите посмотреть по ссылкам.\n\n"
        "Формат ответа — обычный Markdown:\n"
        "- используйте **жирный**, *курсив*, списки с «- » или нумерованные «1.»;\n"
        "- ссылки только в формате [текст](URL); не выдумывайте URL;\n"
        "- код/команды — в тройных кавычках ``` (без языка);\n"
        "- избегайте лишних символов, которые могут вызвать проблемы при форматировании.\n\n"
        # "Структура (соблюдайте порядок и названия разделов):\n"
        # "**Кратко** — 1–3 предложения сути.\n"
        # "**Шаги** — подробная пошаговая инструкция (маркированный список).\n"
        # "**Важно** — риски/заметки/ограничения (по необходимости).\n"
        # "**Ссылки** — перечень только из переданных URL (если они были).\n"
        # "**Ссылки** — перечень только из переданных URL (если они были).\n"
        f"Вопрос: {query}\n\n"
        f"Контекст (ссылки):\n{sources_block}"
    )

    order = [DEFAULT_LLM, "GPT5", "DEEPSEEK"]
    for provider in order:
        try:
            logger.debug(f"LLM provider attempt: {provider}")
            if provider == "YANDEX":
                answer = _yandex_complete(prompt)
                logger.debug(f"Before format [YANDEX] preview={answer[:200]!r}")
                write_debug_event("llm.answer", {"provider": "YANDEX", "len": len(answer), "preview": answer[:500]})
                return _format_for_telegram(answer)
            if provider == "GPT5":
                answer = _gpt5_complete(prompt)
                logger.debug(f"Before format [GPT5] preview={answer[:200]!r}")
                write_debug_event("llm.answer", {"provider": "GPT5", "len": len(answer), "preview": answer[:500]})
                return _format_for_telegram(answer)
            if provider == "DEEPSEEK":
                answer = _deepseek_complete(prompt)
                logger.debug(f"Before format [DEEPSEEK] preview={answer[:200]!r}")
                write_debug_event("llm.answer", {"provider": "DEEPSEEK", "len": len(answer), "preview": answer[:500]})
                return _format_for_telegram(answer)
        except Exception as e:
            # Логируем причину фолбэка по провайдеру
            write_debug_event("llm.provider_error", {"provider": provider, "error": f"{type(e).__name__}: {e}"})
            logger.warning(f"Provider {provider} failed: {type(e).__name__}: {e}; trying next")
            continue
    return "Извините, провайдеры LLM недоступны. Попробуйте позже."
