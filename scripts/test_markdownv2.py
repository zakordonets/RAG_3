#!/usr/bin/env python3
from __future__ import annotations

from loguru import logger
import requests
import os

from app.services.llm_router import _format_for_telegram


CASES = [
    (
        "baseline",
        "**Кратко**\nТестовый текст без спецсимволов.",
    ),
    (
        "dash_list",
        "**Список дефисами**\n- пункт один\n- пункт два\n- пункт три",
    ),
    (
        "lists_and_code",
        "**Шаги**\n1. Пункт один\n2. Пункт два\n- bullets\n`code_inline`\n```\nmultiline code\n```",
    ),
    (
        "links",
        "**Ссылки**\n[Документация](https://docs-chatcenter.edna.ru/docs/)\n[Подробнее](https://docs-chatcenter.edna.ru/)",
    ),
    (
        "russian_text",
        "**Важно**\n* Убедитесь, что операторы объединены в отдельную группу.\n* Правила применяются сверху вниз.",
    ),
]


def to_telegram(text: str) -> str:
    return _format_for_telegram(text)


def main() -> int:
    for name, raw in CASES:
        out = to_telegram(raw)
        print("\n=== CASE:", name, "===")
        print("RAW:\n", raw)
        print("OUT:\n", out)

        # Локальная валидация через Telegram API (если указан токен и chat_id)
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_TEST_CHAT_ID")
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": out,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            }, timeout=15)
            print("SEND STATUS:", resp.status_code)
            if resp.status_code != 200:
                print("SEND ERROR:", resp.text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
