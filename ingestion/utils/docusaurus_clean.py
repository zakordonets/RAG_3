from __future__ import annotations
import re


RE_IMPORT = re.compile(r"(?m)^\s*(import|export)\b[^\n]*\n")
RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
RE_SELF_CLOSING_JSX = re.compile(r"<[A-Z][A-Za-z0-9]*(\s[^<>]*?)?/>")
RE_ADMON = re.compile(
r"::: *(tip|note|info|warning|caution|danger)\s*(.*?)\s*:::", re.DOTALL
)




def _strip_pair_jsx(text: str) -> str:
    # Грубая зачистка парных JSX с заглавной буквы тега, оставляя внутренний текст.
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
    # Нормализация
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
