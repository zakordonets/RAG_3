import json
import tempfile
from pathlib import Path
from ingestion.crawlers.docusaurus_fs_crawler import crawl_docs, CrawlerItem, _read_dir_label


def test_read_dir_label():
    """Тест чтения метки из _category_.json"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем _category_.json с меткой
        category_file = temp_path / "_category_.json"
        category_file.write_text('{"label": "Администратор"}', encoding="utf-8")

        # Тестируем чтение метки
        label = _read_dir_label(temp_path)
        assert label == "Администратор"

        # Тестируем отсутствие файла
        empty_dir = temp_path / "empty"
        empty_dir.mkdir()
        label = _read_dir_label(empty_dir)
        assert label is None


def test_read_dir_label_invalid_json():
    """Тест обработки невалидного JSON"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем невалидный JSON
        category_file = temp_path / "_category_.json"
        category_file.write_text('{"label": "Администратор"', encoding="utf-8")

        label = _read_dir_label(temp_path)
        assert label is None


def test_read_dir_label_no_label():
    """Тест JSON без поля label"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем JSON без поля label
        category_file = temp_path / "_category_.json"
        category_file.write_text('{"description": "Описание"}', encoding="utf-8")

        label = _read_dir_label(temp_path)
        assert label is None


def test_crawl_docs_basic():
    """Базовый тест обхода документации"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем структуру документации
        admin_dir = temp_path / "40-admin"
        admin_dir.mkdir()
        widget_dir = admin_dir / "02-widget"
        widget_dir.mkdir()

        # Создаем _category_.json файлы
        (admin_dir / "_category_.json").write_text('{"label": "Администратор"}', encoding="utf-8")
        (widget_dir / "_category_.json").write_text('{"label": "Виджеты"}', encoding="utf-8")

        # Создаем markdown файл
        md_file = widget_dir / "01-admin-widget-features.md"
        md_file.write_text("# Админ виджет\n\nОписание функций.", encoding="utf-8")

        # Тестируем обход
        items = list(crawl_docs(
            docs_root=temp_path,
            site_base_url="https://docs-chatcenter.edna.ru",
            site_docs_prefix="/docs"
        ))

        assert len(items) == 1
        item = items[0]

        assert item.abs_path == md_file
        assert item.rel_path == "40-admin/02-widget/01-admin-widget-features.md"
        assert item.site_url == "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features"
        assert "Администратор" in item.dir_meta["labels"]
        assert "Виджеты" in item.dir_meta["labels"]
        assert item.dir_meta["current_label"] == "Виджеты"
        assert "Администратор > Виджеты" in item.dir_meta["breadcrumbs"]


def test_crawl_docs_nested_structure():
    """Тест вложенной структуры документации"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем глубоко вложенную структуру
        guide_dir = temp_path / "10-guide"
        guide_dir.mkdir()
        advanced_dir = guide_dir / "20-advanced"
        advanced_dir.mkdir()
        troubleshooting_dir = advanced_dir / "30-troubleshooting"
        troubleshooting_dir.mkdir()

        # Создаем _category_.json файлы
        (guide_dir / "_category_.json").write_text('{"label": "Руководство"}', encoding="utf-8")
        (advanced_dir / "_category_.json").write_text('{"label": "Продвинутые"}', encoding="utf-8")
        (troubleshooting_dir / "_category_.json").write_text('{"label": "Устранение неполадок"}', encoding="utf-8")

        # Создаем markdown файл
        md_file = troubleshooting_dir / "debug.md"
        md_file.write_text("# Отладка\n\nИнструкции по отладке.", encoding="utf-8")

        # Тестируем обход
        items = list(crawl_docs(
            docs_root=temp_path,
            site_base_url="https://docs-chatcenter.edna.ru",
            site_docs_prefix="/docs"
        ))

        assert len(items) == 1
        item = items[0]

        assert item.site_url == "https://docs-chatcenter.edna.ru/docs/guide/advanced/troubleshooting/debug"
        assert "Руководство" in item.dir_meta["labels"]
        assert "Продвинутые" in item.dir_meta["labels"]
        assert "Устранение неполадок" in item.dir_meta["labels"]
        assert item.dir_meta["current_label"] == "Устранение неполадок"
        assert "Руководство > Продвинутые > Устранение неполадок" in item.dir_meta["breadcrumbs"]


def test_crawl_docs_multiple_files():
    """Тест обхода нескольких файлов"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем структуру с несколькими файлами
        admin_dir = temp_path / "40-admin"
        admin_dir.mkdir()

        (admin_dir / "_category_.json").write_text('{"label": "Администратор"}', encoding="utf-8")

        # Создаем несколько markdown файлов
        file1 = admin_dir / "getting-started.md"
        file1.write_text("# Начало работы", encoding="utf-8")

        file2 = admin_dir / "configuration.md"
        file2.write_text("# Конфигурация", encoding="utf-8")

        # Создаем MDX файл
        file3 = admin_dir / "advanced.mdx"
        file3.write_text("# Продвинутые настройки", encoding="utf-8")

        # Тестируем обход
        items = list(crawl_docs(
            docs_root=temp_path,
            site_base_url="https://docs-chatcenter.edna.ru",
            site_docs_prefix="/docs"
        ))

        assert len(items) == 3

        # Проверяем, что все файлы найдены
        rel_paths = {item.rel_path for item in items}
        expected_paths = {
            "40-admin/getting-started.md",
            "40-admin/configuration.md",
            "40-admin/advanced.mdx"
        }
        assert rel_paths == expected_paths

        # Проверяем, что все элементы имеют правильные метаданные
        for item in items:
            assert item.dir_meta["current_label"] == "Администратор"
            assert "Администратор" in item.dir_meta["breadcrumbs"]


def test_crawl_docs_no_category_files():
    """Тест обхода без _category_.json файлов"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем структуру без _category_.json
        admin_dir = temp_path / "40-admin"
        admin_dir.mkdir()

        md_file = admin_dir / "getting-started.md"
        md_file.write_text("# Начало работы", encoding="utf-8")

        # Тестируем обход
        items = list(crawl_docs(
            docs_root=temp_path,
            site_base_url="https://docs-chatcenter.edna.ru",
            site_docs_prefix="/docs"
        ))

        assert len(items) == 1
        item = items[0]

        # Проверяем, что метаданные пустые
        assert item.dir_meta == {}


def test_crawl_docs_ignore_non_markdown():
    """Тест игнорирования файлов, не являющихся markdown"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем различные типы файлов
        admin_dir = temp_path / "40-admin"
        admin_dir.mkdir()

        # Markdown файл (должен быть обработан)
        md_file = admin_dir / "getting-started.md"
        md_file.write_text("# Начало работы", encoding="utf-8")

        # Другие файлы (должны быть проигнорированы)
        (admin_dir / "config.json").write_text('{"key": "value"}', encoding="utf-8")
        (admin_dir / "script.py").write_text("print('hello')", encoding="utf-8")
        (admin_dir / "readme.txt").write_text("Readme content", encoding="utf-8")

        # Тестируем обход
        items = list(crawl_docs(
            docs_root=temp_path,
            site_base_url="https://docs-chatcenter.edna.ru",
            site_docs_prefix="/docs"
        ))

        # Должен быть найден только markdown файл
        assert len(items) == 1
        assert items[0].abs_path == md_file


def test_crawl_docs_drop_prefix_first_level_only():
    """Тест с удалением префикса только на первом уровне"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем структуру с префиксами
        admin_dir = temp_path / "40-admin"
        admin_dir.mkdir()
        widget_dir = admin_dir / "02-widget"
        widget_dir.mkdir()

        md_file = widget_dir / "01-features.md"
        md_file.write_text("# Функции", encoding="utf-8")

        # Тестируем с drop_prefix_all_levels=False
        items = list(crawl_docs(
            docs_root=temp_path,
            site_base_url="https://docs-chatcenter.edna.ru",
            site_docs_prefix="/docs",
            drop_prefix_all_levels=False
        ))

        assert len(items) == 1
        item = items[0]
        # Только первый уровень должен быть очищен от префикса
        assert item.site_url == "https://docs-chatcenter.edna.ru/docs/admin/02-widget/01-features"
