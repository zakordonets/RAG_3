import tempfile
from pathlib import Path
from ingestion.processors.docusaurus_markdown_processor import (
    process_markdown,
    _parse_frontmatter,
    _extract_heading_path,
    _stable_id,
    Chunk
)


def test_parse_frontmatter_basic():
    """Тест парсинга базового фронтматтера"""
    text = """---
title: "Админ виджет"
category: "АРМ_adm"
---

# Админ виджет

Описание функций админ виджета.
"""
    meta, body = _parse_frontmatter(text)

    assert meta["title"] == "Админ виджет"
    assert meta["category"] == "АРМ_adm"
    assert "# Админ виджет" in body
    assert "Описание функций" in body


def test_parse_frontmatter_no_frontmatter():
    """Тест текста без фронтматтера"""
    text = """# Заголовок

Обычный markdown без фронтматтера.
"""
    meta, body = _parse_frontmatter(text)

    assert meta == {}
    assert body == text


def test_parse_frontmatter_complex():
    """Тест сложного фронтматтера"""
    text = """---
title: "Продвинутые настройки"
category: "АРМ_sv"
description: "Подробное руководство"
author: "Команда разработки"
---

# Продвинутые настройки

Содержимое документа.
"""
    meta, body = _parse_frontmatter(text)

    assert meta["title"] == "Продвинутые настройки"
    assert meta["category"] == "АРМ_sv"
    assert meta["description"] == "Подробное руководство"
    assert meta["author"] == "Команда разработки"
    assert "# Продвинутые настройки" in body


def test_extract_heading_path():
    """Тест извлечения пути заголовков"""
    text = """# Главный заголовок

Текст под главным заголовком.

## Подзаголовок 1

Текст под первым подзаголовком.

### Подподзаголовок

Текст под подподзаголовком.

## Подзаголовок 2

Текст под вторым подзаголовком.
"""
    heading_path = _extract_heading_path(text)

    expected = "Главный заголовок > Подзаголовок 1 > Подподзаголовок > Подзаголовок 2"
    assert heading_path == expected


def test_extract_heading_path_no_headings():
    """Тест текста без заголовков"""
    text = """Обычный текст без заголовков.

Просто параграфы с содержимым.
"""
    heading_path = _extract_heading_path(text)
    assert heading_path == ""


def test_stable_id():
    """Тест создания стабильного ID"""
    url1 = "https://docs-chatcenter.edna.ru/docs/admin/widget"
    url2 = "https://docs-chatcenter.edna.ru/docs/admin/widget"
    url3 = "https://docs-chatcenter.edna.ru/docs/admin/user"

    id1 = _stable_id(url1)
    id2 = _stable_id(url2)
    id3 = _stable_id(url3)

    assert id1 == id2  # Одинаковые URL дают одинаковые ID
    assert id1 != id3  # Разные URL дают разные ID
    assert len(id1) == 40  # SHA1 hex длина


def test_process_markdown_basic():
    """Базовый тест обработки markdown"""
    text = """---
title: "Админ виджет"
category: "АРМ_adm"
---

# Админ виджет

Описание функций админ виджета.

## Функции

- Функция 1
- Функция 2

<ContentRef url="/docs/admin/user">Пользователи</ContentRef>
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        md_file = temp_path / "admin-widget.md"

        dir_meta = {
            "labels": "Администратор|Виджеты",
            "current_label": "Виджеты",
            "breadcrumbs": "Администратор > Виджеты"
        }

        doc_meta, chunks = process_markdown(
            raw_text=text,
            abs_path=md_file,
            rel_path="40-admin/02-widget/admin-widget.md",
            site_url="https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget",
            dir_meta=dir_meta
        )

        # Проверяем метаданные документа
        assert doc_meta["title"] == "Админ виджет"
        assert doc_meta["category"] == "АРМ_adm"
        assert doc_meta["site_url"] == "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget"
        assert doc_meta["group_labels"] == ["Администратор", "Виджеты"]
        assert doc_meta["groups_path"] == ["Администратор", "Виджеты"]
        assert doc_meta["current_group"] == "Виджеты"

        # Проверяем чанки
        assert len(chunks) > 0
        chunk = chunks[0]
        assert isinstance(chunk, Chunk)
        assert chunk.vector == []

        payload = chunk.payload
        assert payload["title"] == "Админ виджет"
        assert payload["category"] == "АРМ_adm"
        assert payload["content_type"] == "markdown"
        assert payload["lang"] == "ru"
        assert payload["source"] == "docusaurus"
        assert payload["group_labels"] == ["Администратор", "Виджеты"]
        assert payload["current_group"] == "Виджеты"

        # Проверяем, что ContentRef был обработан (может быть в любом чанке)
        all_chunk_text = " ".join([chunk.payload["chunk_text"] for chunk in chunks])
        # ContentRef может быть отфильтрован чанкером, но если есть, то должен быть обработан
        if "Пользователи" in all_chunk_text:
            assert "Пользователи (см. https://docs-chatcenter.edna.ru/docs/admin/user)" in all_chunk_text


def test_process_markdown_no_frontmatter():
    """Тест обработки markdown без фронтматтера"""
    text = """# Админ виджет

Описание функций админ виджета.

## Функции

- Функция 1
- Функция 2
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        md_file = temp_path / "40-admin-widget.md"

        dir_meta = {"labels": "Администратор", "current_label": "Администратор"}

        doc_meta, chunks = process_markdown(
            raw_text=text,
            abs_path=md_file,
            rel_path="40-admin-widget.md",
            site_url="https://docs-chatcenter.edna.ru/docs/admin-widget",
            dir_meta=dir_meta
        )

        # Проверяем, что title был извлечен из имени файла
        assert doc_meta["title"] == "admin widget"
        assert doc_meta["category"] == "UNSPECIFIED"  # Категория по умолчанию

        # Проверяем чанки
        assert len(chunks) > 0
        chunk = chunks[0]
        assert chunk.payload["title"] == "admin widget"


def test_process_markdown_with_jsx_and_admonitions():
    """Тест обработки markdown с JSX и admonitions"""
    text = """---
title: "Руководство по настройке"
category: "АРМ_sv"
---

# Руководство по настройке

import React from 'react';

<SupportButton />

:::tip
Полезный совет по настройке
:::

<ContentRef url="/docs/admin/config">Конфигурация</ContentRef>

:::warning
Важное предупреждение
:::
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        md_file = temp_path / "setup-guide.md"

        dir_meta = {}

        doc_meta, chunks = process_markdown(
            raw_text=text,
            abs_path=md_file,
            rel_path="setup-guide.md",
            site_url="https://docs-chatcenter.edna.ru/docs/setup-guide",
            dir_meta=dir_meta
        )

        # Проверяем, что контент был очищен (может быть в любом чанке)
        all_chunk_text = " ".join([chunk.payload["chunk_text"] for chunk in chunks])

        # JSX и импорты должны быть удалены
        assert "import React" not in all_chunk_text
        assert "SupportButton" not in all_chunk_text

        # Admonitions должны быть расплющены
        assert "Полезный совет по настройке" in all_chunk_text
        assert "Важное предупреждение" in all_chunk_text
        assert ":::" not in all_chunk_text

        # ContentRef должен быть обработан
        assert "Конфигурация (см. https://docs-chatcenter.edna.ru/docs/admin/config)" in all_chunk_text


def test_process_markdown_chunking():
    """Тест чанкинга длинного документа"""
    # Создаем длинный документ с заголовками
    text = """---
title: "Длинное руководство"
category: "АРМ_adm"
---

# Введение

Введение в руководство.

## Глава 1

Содержимое первой главы.

### Подраздел 1.1

Подробное описание подраздела.

### Подраздел 1.2

Еще один подраздел.

## Глава 2

Содержимое второй главы.

### Подраздел 2.1

Описание второго подраздела.

## Заключение

Заключительные замечания.
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        md_file = temp_path / "long-guide.md"

        dir_meta = {}

        doc_meta, chunks = process_markdown(
            raw_text=text,
            abs_path=md_file,
            rel_path="long-guide.md",
            site_url="https://docs-chatcenter.edna.ru/docs/long-guide",
            dir_meta=dir_meta
        )

        # Документ должен быть обработан (может быть один или несколько чанков)
        assert len(chunks) >= 1

        # Проверяем, что каждый чанк имеет правильные метаданные
        for i, chunk in enumerate(chunks):
            payload = chunk.payload
            assert payload["chunk_index"] == i
            assert payload["chunk_count"] == len(chunks)
            assert payload["doc_id"] == doc_meta["doc_id"]
            assert payload["title"] == "Длинное руководство"
            assert payload["category"] == "АРМ_adm"


def test_process_markdown_empty_dir_meta():
    """Тест обработки с пустыми метаданными директорий"""
    text = """# Простой документ

Содержимое документа.
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        md_file = temp_path / "simple.md"

        dir_meta = {}  # Пустые метаданные

        doc_meta, chunks = process_markdown(
            raw_text=text,
            abs_path=md_file,
            rel_path="simple.md",
            site_url="https://docs-chatcenter.edna.ru/docs/simple",
            dir_meta=dir_meta
        )

        # Проверяем, что пустые метаданные обрабатываются корректно
        assert doc_meta["group_labels"] == []
        assert doc_meta["groups_path"] == []
        assert doc_meta["current_group"] == ""

        # Проверяем, что есть хотя бы один чанк
        assert len(chunks) > 0
        chunk = chunks[0]
        assert chunk.payload["group_labels"] == []
        assert chunk.payload["groups_path"] == []
        assert chunk.payload["current_group"] == ""


def test_process_markdown_contentref_processing():
    """Тест обработки ContentRef в процессоре"""
    text = """# Документ с ContentRef

Основной текст документа.

<ContentRef url="/docs/admin/user">Пользователи</ContentRef>

Дополнительный текст.
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        md_file = temp_path / "contentref-test.md"

        dir_meta = {}

        doc_meta, chunks = process_markdown(
            raw_text=text,
            abs_path=md_file,
            rel_path="contentref-test.md",
            site_url="https://docs-chatcenter.edna.ru/docs/contentref-test",
            dir_meta=dir_meta
        )

        # Проверяем, что есть хотя бы один чанк
        assert len(chunks) >= 1

        # Проверяем, что ContentRef был обработан
        all_chunk_text = " ".join([chunk.payload["chunk_text"] for chunk in chunks])
        assert "Пользователи (см. https://docs-chatcenter.edna.ru/docs/admin/user)" in all_chunk_text
