from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import os
from typing import Dict, Iterable, List, Optional


from ingestion.utils.docusaurus_utils import fs_to_url




@dataclass
class CrawlerItem:
    abs_path: Path
    rel_path: str
    dir_meta: Dict[str, str]
    mtime: float
    site_url: str




def _read_dir_label(dir_path: Path) -> Optional[str]:
    cfg = dir_path / "_category_.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "label" in data:
                return str(data["label"]) # type: ignore
        except Exception:
            return None
        return None


def crawl_docs(
    docs_root: Path,
    site_base_url: str,
    site_docs_prefix: str = "/docs",
    drop_prefix_all_levels: bool = True,
) -> Iterable[CrawlerItem]:
    """Рекурсивно обходит файловую систему Docusaurus и собирает метаданные.

    Args:
        docs_root: Корневая директория с документацией
        site_base_url: Базовый URL сайта
        site_docs_prefix: Префикс для документации в URL
        drop_prefix_all_levels: Удалять числовые префиксы на всех уровнях

    Yields:
        CrawlerItem: Элемент с метаданными файла
    """
    exts = {".md", ".mdx"}
    docs_root = docs_root.resolve()

    for abs_path in docs_root.rglob("*"):
        if abs_path.suffix.lower() not in exts:
            continue

        rel_path = str(abs_path.relative_to(docs_root)).replace("\\", "/")

        # Собираем метаданные из _category_.json по всему пути
        dir_meta = _collect_dir_metadata(docs_root, abs_path.parent)

        mtime = abs_path.stat().st_mtime
        site_url = fs_to_url(
            docs_root, abs_path, site_base=site_base_url, docs_prefix=site_docs_prefix,
            drop_prefix_all_levels=drop_prefix_all_levels,
        )

        yield CrawlerItem(
            abs_path=abs_path,
            rel_path=rel_path,
            dir_meta=dir_meta,
            mtime=mtime,
            site_url=site_url,
        )


def _collect_dir_metadata(docs_root: Path, file_dir: Path) -> Dict[str, str]:
    """Собирает метаданные из _category_.json файлов по пути от корня до директории файла.

    Args:
        docs_root: Корневая директория документации
        file_dir: Директория файла

    Returns:
        Dict с метаданными (labels, groups_path, breadcrumbs)
    """
    dir_meta = {}
    labels: List[str] = []
    breadcrumbs: List[str] = []

    # Строим путь от корня до директории файла
    try:
        rel_path = file_dir.relative_to(docs_root)
        path_parts = [docs_root] + list(rel_path.parts)
    except ValueError:
        # Файл находится вне docs_root
        return dir_meta

    # Проходим по пути от корня к директории файла
    for i, part in enumerate(path_parts):
        if i == 0:  # Пропускаем корневую директорию
            continue

        current_dir = Path(*path_parts[:i+1])
        label = _read_dir_label(current_dir)

        if label:
            labels.append(label)
            breadcrumbs.append(label)

    # Сохраняем собранные метаданные
    if labels:
        dir_meta["labels"] = "|".join(labels)  # Все метки через разделитель
        dir_meta["current_label"] = labels[-1]  # Метка текущей директории
        dir_meta["breadcrumbs"] = " > ".join(breadcrumbs)  # Хлебные крошки

    return dir_meta
