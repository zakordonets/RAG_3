from __future__ import annotations
import os
import re
from pathlib import Path


NUM_PREFIX_RE = re.compile(r"^\d+-")




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


    url_path = "/".join([docs_prefix.strip("/")] + parts).replace("\\", "/")
    if add_trailing_slash:
        url_path = url_path.rstrip("/")
    return f"{site_base.rstrip('/')}/{url_path}"
