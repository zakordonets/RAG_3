"""
Утилиты для обработки Docusaurus документации

Объединяет функции для:
- Очистки MD/MDX контента
- Обработки ссылок ContentRef
- Преобразования путей в URL
"""

from __future__ import annotations
import os
import re
from pathlib import Path


# ============================================================================
# Константы и регулярные выражения
# ============================================================================

NUM_PREFIX_RE = re.compile(r"^\d+-")
RE_IMPORT = re.compile(r"(?m)^\s*(import|export)\b[^\n]*\n")
RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
RE_SELF_CLOSING_JSX = re.compile(r"<[A-Z][A-Za-z0-9]*(\s[^<>]*?)?/>")
RE_ADMON = re.compile(
    r"::: *(tip|note|info|warning|caution|danger)\s*(.*?)\s*:::", re.DOTALL
)
CONTENTREF_RE = re.compile(
    r"<ContentRef\s+url=['\"]([^'\"]+)['\"]>(.*?)</ContentRef>", re.DOTALL
)


# ============================================================================
# Функции очистки контента
# ============================================================================

def _strip_pair_jsx(text: str) -> str:
    """Грубая зачистка парных JSX с заглавной буквы тега, оставляя внутренний текст."""
    # Сначала убираем открывающие/закрывающие теги, потом схлопываем пробелы.
    text = re.sub(r"</?[A-Z][A-Za-z0-9]*(\s[^<>]*?)?>", "", text)
    return text


def clean(text: str) -> str:
    """Очищает MD/MDX от импортов, HTML-комментариев, JSX-компонентов,
    расплющивает admonitions и нормализует пробелы/строки.
    """
    if not text:
        return ""
    t = RE_IMPORT.sub("", text)
    t = RE_HTML_COMMENT.sub("", t)
    t = RE_ADMON.sub(lambda m: m.group(2), t)
    t = RE_SELF_CLOSING_JSX.sub("", t)
    t = _strip_pair_jsx(t)

    # Очистка HTML-тегов (details, summary и других)
    t = re.sub(r"<details[^>]*>", "", t)
    t = re.sub(r"</details>", "", t)
    t = re.sub(r"<summary[^>]*>", "", t)
    t = re.sub(r"</summary>", "", t)
    t = re.sub(r"<[^>]+>", "", t)  # Удаляем все остальные HTML-теги

    # Нормализация (сохраняем структуру текста)
    t = re.sub(r"[ \t]+", " ", t)  # Заменяем множественные пробелы и табы на одинарные пробелы
    t = re.sub(r" \n", "\n", t)    # Убираем пробелы перед переносами строк
    t = re.sub(r"\n ", "\n", t)    # Убираем пробелы после переносов строк
    t = re.sub(r"\n{3,}", "\n\n", t)  # Ограничиваем множественные переносы строк
    return t.strip()


# ============================================================================
# Функции обработки ссылок
# ============================================================================

def replace_contentref(text: str, site_base: str) -> str:
    """Заменяет <ContentRef url="...">Label</ContentRef> на
    "Label (см. ABS_URL)". Относительные URL (начинающиеся с '/')
    резолвятся через site_base.
    """
    def _sub(m):
        url = m.group(1)
        label = (m.group(2) or "").strip()
        abs_url = site_base.rstrip("/") + url if url.startswith("/") else url
        return f"{label} (см. {abs_url})"

    return CONTENTREF_RE.sub(_sub, text)


# ============================================================================
# Функции преобразования путей
# ============================================================================

def clean_segment(seg: str, drop_numeric_prefix: bool = True) -> str:
    """Возвращает имя сегмента без расширения и числового префикса вида '01-'.
    Не трогает вложенные дефисы в середине имени.
    """
    name, _ext = os.path.splitext(seg)
    if drop_numeric_prefix:
        name = NUM_PREFIX_RE.sub("", name)
    return name


def fs_to_url(
    docs_root: Path,
    abs_path: Path,
    site_base: str,
    docs_prefix: str,
    drop_prefix_all_levels: bool = True,
    add_trailing_slash: bool = False,
) -> str:
    """Строит абсолютный URL страницы Docusaurus по пути к файлу.

    Прим.: имя файла берётся без расширения; числовые префиксы удаляются либо на всех уровнях,
    либо только на первом (если drop_prefix_all_levels=False).
    """
    rel = abs_path.relative_to(docs_root)
    parts = list(rel.parts)
    # заменить последний сегмент на имя без расширения
    parts[-1] = os.path.splitext(parts[-1])[0]

    if drop_prefix_all_levels:
        parts = [NUM_PREFIX_RE.sub("", p) for p in parts]
    else:
        if parts:
            parts[0] = NUM_PREFIX_RE.sub("", parts[0])

    prefix = docs_prefix.strip("/")
    path_parts = parts if not prefix else [prefix] + parts
    url_path = "/".join(path_parts).replace("\\", "/")
    if add_trailing_slash:
        url_path = url_path.rstrip("/")
    # Если path_parts оказался пустым (например, файл лежит прямо в корне и docs_prefix=""),
    # то url_path будет пустым, значит отдаем базовый URL без завершающего слеша.
    if not url_path:
        return site_base.rstrip("/")
    return f"{site_base.rstrip('/')}/{url_path}"
