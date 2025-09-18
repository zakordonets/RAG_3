from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Optional
from loguru import logger


COOKIES_PATH = Path(".cache/cookies.json")


async def fetch_html(url: str, timeout_s: int = 30, headless: bool = False) -> str:
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ])
        context = await browser.new_context(
            viewport={"width": random.randint(1280, 1680), "height": random.randint(800, 1050)},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        # restore cookies
        try:
            if COOKIES_PATH.exists():
                cookies = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
                await context.add_cookies(cookies)
        except Exception:
            pass
        page = await context.new_page()

        # robust navigation with retries
        nav_errors: list[str] = []
        for attempt in range(3):
            try:
                wait_mode = "commit" if attempt == 0 else ("domcontentloaded" if attempt == 1 else "load")
                await page.goto(url, wait_until=wait_mode, timeout=timeout_s * 1000)
                break
            except Exception as e:
                nav_errors.append(f"{type(e).__name__}: {e}")
                if attempt == 2:
                    raise
                await page.wait_for_timeout(1000 + 500 * attempt)
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=timeout_s * 1000)
                except Exception:
                    pass

        # simulate reading and scrolling
        for _ in range(3):
            await page.wait_for_timeout(random.randint(900, 1800))
            try:
                await page.mouse.wheel(0, random.randint(600, 1200))
            except Exception:
                break
        # wait for network to calm down
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_s * 1000)
        except Exception:
            pass

        html = await page.content()
        # persist cookies
        try:
            cookies = await context.cookies()
            COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
            COOKIES_PATH.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

        await context.close()
        await browser.close()
        return html


def fetch_html_sync(url: str, timeout_s: int = 30, headless: bool = False) -> str:
    return asyncio.run(fetch_html(url, timeout_s=timeout_s, headless=headless))


