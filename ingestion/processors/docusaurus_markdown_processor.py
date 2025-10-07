from __future__ import annotations
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

from ingestion.utils.docusaurus_clean import clean
from ingestion.utils.docusaurus_links import replace_contentref
from ingestion.chunking.universal_chunker import UniversalChunker


@dataclass
class Chunk:
    """Структура чанка с вектором и метаданными"""
    vector: List[float]
    payload: Dict[str, Any]




def _parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """Парсит фронтматтер YAML из начала markdown файла.

    Args:
        text: Исходный текст markdown файла

    Returns:
        Tuple[Dict[str, str], str]: (метаданные фронтматтера, тело документа)
    """
    meta = {}
    body = text

    # Проверяем наличие фронтматтера
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            frontmatter_text = parts[1]
            body = parts[2]

            # Простой парсинг YAML (только базовые случаи)
            for line in frontmatter_text.splitlines():
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        meta[key] = value

    return meta, body


def _stable_id(text: str) -> str:
    """Создает стабильный ID из текста (SHA1)."""
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


def _extract_heading_path(text: str) -> str:
    """Извлекает путь заголовков из markdown текста."""
    headings = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            # Убираем # и лишние пробелы
            heading = re.sub(r'^#+\s*', '', line).strip()
            if heading:
                headings.append(heading)

    return " > ".join(headings) if headings else ""


def _markdown_aware_chunk(text: str, max_tokens: int = 600, overlap_tokens: int = 120) -> List[str]:
    """Markdown-aware чанкинг с учетом заголовков и структуры.

    Args:
        text: Исходный markdown текст
        max_tokens: Максимальное количество токенов в чанке
        overlap_tokens: Количество токенов для перекрытия

    Returns:
        List[str]: Список чанков
    """
    # Приблизительная оценка токенов (1 токен ≈ 4 символа для русского текста)
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4

    try:
        # Используем UniversalChunker
        chunker = UniversalChunker(max_tokens=max_tokens, min_tokens=min_tokens//2)
        chunks = chunker.chunk(text, 'markdown', {'doc_id': 'temp'})
        # Извлекаем только текст из чанков
        chunks = [chunk.text for chunk in chunks]

        # Если получили пустой результат, используем fallback
        if not chunks:
            return _simple_markdown_chunk(text, max_chars, overlap_chars)

        return chunks
    except Exception:
        # Fallback к простому чанкингу
        return _simple_markdown_chunk(text, max_chars, overlap_chars)


def _simple_markdown_chunk(text: str, max_chars: int = 2400, overlap: int = 480) -> List[str]:
    """Простое разбиение по заголовкам и длине (fallback)."""
    parts: List[str] = []
    buf: List[str] = []
    acc = 0

    for line in text.splitlines(True):
        # Проверяем заголовки H1-H3
        if line.lstrip().startswith(("# ", "## ", "### ")) and acc > max_chars:
            if buf:
                parts.append("".join(buf).strip())
                # Overlap: берем хвост предыдущего чанка
                tail = ("".join(buf))[-overlap:]
                buf = [tail, line]
                acc = len(tail) + len(line)
            else:
                buf = [line]
                acc = len(line)
        else:
            buf.append(line)
            acc += len(line)

        # Принудительное разбиение по длине
        if acc >= max_chars:
            if buf:
                parts.append("".join(buf).strip())
                tail = ("".join(buf))[-overlap:]
                buf = [tail]
                acc = len(tail)

    # Добавляем последний чанк
    if buf:
        parts.append("".join(buf).strip())

    return [p for p in parts if p]


def process_markdown(
    raw_text: str,
    abs_path: Path,
    rel_path: str,
    site_url: str,
    dir_meta: Dict[str, str],
    default_category: str = "UNSPECIFIED",
) -> Tuple[Dict[str, Any], List[Chunk]]:
    """Обрабатывает markdown файл Docusaurus и возвращает метаданные документа и чанки.

    Args:
        raw_text: Исходный текст markdown файла
        abs_path: Абсолютный путь к файлу
        rel_path: Относительный путь от корня документации
        site_url: URL страницы на сайте
        dir_meta: Метаданные директорий (labels, breadcrumbs)
        default_category: Категория по умолчанию

    Returns:
        Tuple[Dict[str, Any], List[Chunk]]: (метаданные документа, список чанков)
    """
    # Парсим фронтматтер
    frontmatter, body = _parse_frontmatter(raw_text)
    title = frontmatter.get("title")
    category = frontmatter.get("category", default_category)

    # Очистка и резолв ссылок
    body = replace_contentref(body, site_base="https://docs-chatcenter.edna.ru")
    body = clean(body)

    # Извлекаем путь заголовков
    heading_path = _extract_heading_path(body)

    # Фоллбэки для title
    if not title:
        name = Path(rel_path).stem
        title = re.sub(r"^\d+-", "", name).replace("-", " ").strip()

    # Создаем стабильный ID документа
    doc_id = _stable_id(site_url)

    # Markdown-aware чанкинг
    chunks_text = _markdown_aware_chunk(body, max_tokens=600, overlap_tokens=120)

    # Если чанкинг не дал результатов, используем весь очищенный текст
    if not chunks_text:
        chunks_text = [body] if body.strip() else []

    # Формируем чанки с payload
    chunks: List[Chunk] = []
    for idx, chunk_text in enumerate(chunks_text):
        # Извлекаем заголовки для текущего чанка
        chunk_heading_path = _extract_heading_path(chunk_text)

        # Формируем payload согласно CODEX_BRIEF.md
        payload = {
            # Основные идентификаторы
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}#{idx}",
            "chunk_index": idx,
            "chunk_count": len(chunks_text),

            # Пути и URL
            "site_url": site_url,
            "rel_path": rel_path,
            "abs_path": str(abs_path),

            # Метаданные контента
            "title": title,
            "category": category,
            "content_type": "markdown",
            "lang": "ru",

            # Структурные метаданные
            "heading_path": chunk_heading_path or heading_path,

            # Метаданные групп из _category_.json
            "group_labels": dir_meta.get("labels", "").split("|") if dir_meta.get("labels") else [],
            "groups_path": dir_meta.get("breadcrumbs", "").split(" > ") if dir_meta.get("breadcrumbs") else [],
            "current_group": dir_meta.get("current_label", ""),

            # Дополнительные метаданные
            "source": "docusaurus",
            "chunk_text": chunk_text,  # Для отладки и анализа
        }

        chunks.append(Chunk(vector=[], payload=payload))

    # Метаданные документа
    doc_meta = {
        "doc_id": doc_id,
        "site_url": site_url,
        "title": title,
        "category": category,
        "rel_path": rel_path,
        "abs_path": str(abs_path),
        "heading_path": heading_path,
        "chunk_count": len(chunks_text),
        "group_labels": dir_meta.get("labels", "").split("|") if dir_meta.get("labels") else [],
        "groups_path": dir_meta.get("breadcrumbs", "").split(" > ") if dir_meta.get("breadcrumbs") else [],
        "current_group": dir_meta.get("current_label", ""),
    }

    return doc_meta, chunks
