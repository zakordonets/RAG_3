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
from urllib.parse import urlparse
import requests
from app.config import CONFIG
from loguru import logger
from app.utils import write_debug_event


DEFAULT_LLM = CONFIG.default_llm
LIST_INTENT_PATTERN = re.compile(r"\b(какие|список|перечень)\b.*\bканал", re.IGNORECASE | re.DOTALL)


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


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path).geturl()
    return normalized or url.strip()


def apply_url_whitelist(answer_md: str, sources: List[Dict[str, str]]) -> str:
    """
    Оставляет в ответе только ссылки из whitelist'а sources.

    Args:
        answer_md: Исходный Markdown-ответ модели.
        sources: Список разрешенных источников с URL.

    Returns:
        Markdown-текст без посторонних ссылок.
    """
    if not answer_md:
        return answer_md

    allowed_urls = {
        _normalize_url(str(source.get("url", "")).strip())
        for source in sources
        if source.get("url")
    }
    allowed_urls = {url for url in allowed_urls if url}

    def replace_markdown_link(match: re.Match[str]) -> str:
        text, url = match.group(1), match.group(2)
        normalized = _normalize_url(url)
        if normalized in allowed_urls:
            return match.group(0)
        logger.debug(f"Removing non-whitelisted markdown link: {url}")
        return text

    def replace_bare_url(match: re.Match[str]) -> str:
        url = match.group(0)
        normalized = _normalize_url(url)
        if normalized in allowed_urls:
            return url
        logger.debug(f"Removing non-whitelisted bare URL: {url}")
        return ""

    sanitized = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_markdown_link, answer_md)
    sanitized = re.sub(r"https?://[^\s)]+", replace_bare_url, sanitized)
    return sanitized


def is_list_intent(query: str) -> bool:
    """Определяет, относится ли запрос к списочному режиму (extract mode)."""
    if not query:
        return False
    return bool(LIST_INTENT_PATTERN.search(query))


def _collect_sources(context: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    seen = set()
    for doc in context:
        payload = doc.get("payload", {}) or {}
        url = str(payload.get("url") or "").strip()
        if not url:
            continue
        normalized = _normalize_url(url)
        if normalized in seen:
            continue
        title = str(payload.get("title") or "Документация").strip() or "Документация"
        sources.append({"title": title, "url": url})
        seen.add(normalized)
        if len(sources) >= limit:
            break
    return sources


def _build_sources_block(sources: List[Dict[str, str]]) -> str:
    if not sources:
        return "нет источников"
    lines = []
    for index, source in enumerate(sources, start=1):
        lines.append(f"{index}. {source.get('title', 'Источник')}: {source.get('url')}")
    return "\n".join(lines)


def _trim_text(text: str) -> str:
    return text.strip() if isinstance(text, str) else ""


def _build_context_block(context: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    for idx, doc in enumerate(context, start=1):
        payload = doc.get("payload", {}) or {}
        title = _trim_text(payload.get("title")) or f"Документ {idx}"
        url = _trim_text(payload.get("url"))
        text = _trim_text(payload.get("text"))
        block_lines = [f"### {title}"]
        if url:
            block_lines.append(f"{url}")
        if text:
            block_lines.append(text)
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


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


def generate_answer(query: str, context: List[Dict[str, Any]], policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Генерирует ответ на основе контекста документов и возвращает структуру
    с чистым Markdown и whitelisted источниками.
    """
    policy = policy or {}
    mode = "extract" if is_list_intent(query) else "compose"

    if mode == "extract":
        temperature: Optional[float] = 0.05
        top_p: Optional[float] = 0.9
        system_prompt = (
            "вернуть пункты дословно, в исходном порядке; без обобщений и новых ссылок; "
            "если нет раздела — 'В контексте нет данных'."
        )
    else:
        temperature = policy.get("temperature")
        top_p = policy.get("top_p")
        system_prompt = (
            "Ты ассистент edna Chat Center. Отвечай на русском языке, используя только предоставленный контекст. "
            "Формат ответа — чистый Markdown: заголовки '###', списки '-', нумерация '1.' при необходимости, "
            "кодовые блоки в ``` без указания языка. "
            "Если информации недостаточно, честно сообщи об этом. Не придумывай ссылки и факты."
        )

    sources = _collect_sources(context)
    context_block = _build_context_block(context)
    sources_block = _build_sources_block(sources)

    prompt = (
        f"Вопрос: {query.strip()}\n\n"
        f"Контекст:\n{context_block or 'нет контекста'}\n\n"
        f"Ссылки на источники:\n{sources_block}"
    )

    order = [DEFAULT_LLM, "GPT5", "DEEPSEEK"]
    logger.info(
        f"LLM Router: mode={mode}, providers={' -> '.join(order)}, "
        f"context_docs={len(context)}, sources={len(sources)}"
    )

    meta: Dict[str, Any] = {
        "mode": mode,
        "temperature": temperature,
        "top_p": top_p,
        "provider": None,
    }

    for provider in order:
        try:
            logger.info(
                f"LLM Router: provider={provider}, mode={mode}, "
                f"temperature={temperature}, top_p={top_p}"
            )
            if provider == "YANDEX":
                answer = _yandex_complete(
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    top_p=top_p,
                )
            elif provider == "GPT5":
                answer = _gpt5_complete(
                    prompt,
                    system_prompt=system_prompt,
                )
            else:
                answer = _deepseek_complete(
                    prompt,
                    system_prompt=system_prompt,
                )

            answer_markdown = (answer or "").strip()
            filtered_answer = apply_url_whitelist(answer_markdown, sources)
            if filtered_answer != answer_markdown:
                logger.info("LLM Router: removed non-whitelisted links from answer")

            meta["provider"] = provider
            meta["answer_length"] = len(filtered_answer)

            write_debug_event(
                "llm.answer",
                {
                    "provider": provider,
                    "mode": mode,
                    "len": len(answer_markdown),
                    "preview": answer_markdown[:500],
                    "temperature": temperature,
                    "top_p": top_p,
                },
            )

            return {
                "answer_markdown": filtered_answer,
                "sources": sources,
                "meta": meta,
            }
        except Exception as exc:
            write_debug_event(
                "llm.provider_error",
                {"provider": provider, "error": f"{type(exc).__name__}: {exc}"},
            )
            logger.warning(
                f"LLM Router: provider {provider} failed: {type(exc).__name__}: {exc}"
            )
            continue

    logger.error("LLM Router: all providers failed")
    failure_answer = "Извините, провайдеры LLM недоступны. Попробуйте позже."
    meta["error"] = "all_providers_failed"
    return {
        "answer_markdown": failure_answer,
        "sources": sources,
        "meta": meta,
    }
