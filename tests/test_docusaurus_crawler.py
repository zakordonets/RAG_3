"""
Тесты для Docusaurus файлового краулера
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, Mock

from ingestion.crawlers.docusaurus_fs_crawler import (
    crawl_docs,
    CrawlerItem,
    _read_dir_label,
    _collect_dir_metadata
)

pytestmark = pytest.mark.unit


class TestDocusaurusFSCrawler:
    """Тесты для docusaurus_fs_crawler.py"""

    def test_read_dir_label_valid_json(self):
        """Тест чтения валидного _category_.json"""
        with tempfile.TemporaryDirectory() as temp_dir:
            category_file = Path(temp_dir) / "_category_.json"
            category_data = {"label": "Администрирование"}

            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(category_data, f, ensure_ascii=False)

            result = _read_dir_label(Path(temp_dir))
            assert result == "Администрирование"

    def test_read_dir_label_invalid_json(self):
        """Тест чтения невалидного _category_.json"""
        with tempfile.TemporaryDirectory() as temp_dir:
            category_file = Path(temp_dir) / "_category_.json"

            with open(category_file, 'w', encoding='utf-8') as f:
                f.write("invalid json")

            result = _read_dir_label(Path(temp_dir))
            assert result is None

    def test_read_dir_label_missing_file(self):
        """Тест чтения отсутствующего _category_.json"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = _read_dir_label(Path(temp_dir))
            assert result is None

    def test_read_dir_label_missing_label(self):
        """Тест чтения _category_.json без поля label"""
        with tempfile.TemporaryDirectory() as temp_dir:
            category_file = Path(temp_dir) / "_category_.json"
            category_data = {"position": 1}

            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(category_data, f)

            result = _read_dir_label(Path(temp_dir))
            assert result is None

    def test_collect_dir_metadata_single_level(self):
        """Тест сбора метаданных для одного уровня"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            # Создаем _category_.json
            category_file = admin_dir / "_category_.json"
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump({"label": "Администрирование"}, f, ensure_ascii=False)

            result = _collect_dir_metadata(docs_root, admin_dir)

            assert result["current_label"] == "Администрирование"
            assert result["labels"] == "Администрирование"
            assert result["breadcrumbs"] == "Администрирование"

    def test_collect_dir_metadata_nested(self):
        """Тест сбора метаданных для вложенной структуры"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру: admin/user
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()
            user_dir = admin_dir / "02-user"
            user_dir.mkdir()

            # Создаем _category_.json файлы
            admin_category = admin_dir / "_category_.json"
            with open(admin_category, 'w', encoding='utf-8') as f:
                json.dump({"label": "Администрирование"}, f, ensure_ascii=False)

            user_category = user_dir / "_category_.json"
            with open(user_category, 'w', encoding='utf-8') as f:
                json.dump({"label": "Пользователи"}, f, ensure_ascii=False)

            result = _collect_dir_metadata(docs_root, user_dir)

            assert result["current_label"] == "Пользователи"
            assert result["labels"] == "Администрирование|Пользователи"
            assert result["breadcrumbs"] == "Администрирование > Пользователи"

    def test_collect_dir_metadata_missing_categories(self):
        """Тест сбора метаданных при отсутствии _category_.json"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            result = _collect_dir_metadata(docs_root, admin_dir)

            # При отсутствии _category_.json функция возвращает пустой словарь
            assert result == {}

    def test_crawl_docs_basic(self):
        """Тест базового краулинга"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру файлов
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            user_file = admin_dir / "user.md"
            user_file.write_text("# Пользователи\n\nОписание пользователей.")

            # Создаем _category_.json
            category_file = admin_dir / "_category_.json"
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump({"label": "Администрирование"}, f, ensure_ascii=False)

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://example.com",
                site_docs_prefix="/docs"
            ))

            assert len(items) == 1
            item = items[0]

            assert isinstance(item, CrawlerItem)
            assert item.abs_path == user_file
            assert item.rel_path == "01-admin/user.md"
            assert item.dir_meta["current_label"] == "Администрирование"
            assert item.site_url == "https://example.com/docs/admin/user"

    def test_crawl_docs_multiple_files(self):
        """Тест краулинга нескольких файлов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру файлов
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            user_file = admin_dir / "user.md"
            user_file.write_text("# Пользователи")

            role_file = admin_dir / "role.md"
            role_file.write_text("# Роли")

            # Создаем _category_.json
            category_file = admin_dir / "_category_.json"
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump({"label": "Администрирование"}, f, ensure_ascii=False)

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://example.com",
                site_docs_prefix="/docs"
            ))

            assert len(items) == 2

            # Проверяем, что оба файла найдены
            rel_paths = [item.rel_path for item in items]
            assert "01-admin/user.md" in rel_paths
            assert "01-admin/role.md" in rel_paths

    def test_crawl_docs_ignore_non_markdown(self):
        """Тест игнорирования не-markdown файлов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем файлы разных типов
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            user_file = admin_dir / "user.md"
            user_file.write_text("# Пользователи")

            image_file = admin_dir / "image.png"
            image_file.write_bytes(b"fake image data")

            text_file = admin_dir / "readme.txt"
            text_file.write_text("Readme content")

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://example.com",
                site_docs_prefix="/docs"
            ))

            # Должен найти только .md файл
            assert len(items) == 1
            assert items[0].rel_path == "01-admin/user.md"

    def test_crawl_docs_nested_structure(self):
        """Тест краулинга вложенной структуры"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру: admin/user/settings
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            user_dir = admin_dir / "02-user"
            user_dir.mkdir()

            settings_file = user_dir / "settings.md"
            settings_file.write_text("# Настройки пользователя")

            # Создаем _category_.json файлы
            admin_category = admin_dir / "_category_.json"
            with open(admin_category, 'w', encoding='utf-8') as f:
                json.dump({"label": "Администрирование"}, f, ensure_ascii=False)

            user_category = user_dir / "_category_.json"
            with open(user_category, 'w', encoding='utf-8') as f:
                json.dump({"label": "Пользователи"}, f, ensure_ascii=False)

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://example.com",
                site_docs_prefix="/docs"
            ))

            assert len(items) == 1
            item = items[0]

            assert item.rel_path == "01-admin/02-user/settings.md"
            assert item.dir_meta["current_label"] == "Пользователи"
            assert "Администрирование" in item.dir_meta["labels"]
            assert "Пользователи" in item.dir_meta["labels"]
            assert item.site_url == "https://example.com/docs/admin/user/settings"

    def test_crawl_docs_drop_prefix_disabled(self):
        """Тест краулинга без удаления префиксов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру файлов
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            user_file = admin_dir / "user.md"
            user_file.write_text("# Пользователи")

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://example.com",
                site_docs_prefix="/docs",
                drop_prefix_all_levels=False
            ))

            assert len(items) == 1
            item = items[0]
            # Краулер всегда удаляет префиксы через fs_to_url
            assert item.site_url == "https://example.com/docs/admin/user"

    def test_crawl_docs_empty_directory(self):
        """Тест краулинга пустой директории"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем пустую директорию
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://example.com",
                site_docs_prefix="/docs"
            ))

            assert len(items) == 0

    def test_crawl_docs_mdx_files(self):
        """Тест краулинга .mdx файлов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру файлов
            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            user_file = admin_dir / "user.mdx"
            user_file.write_text("# Пользователи\n\n<CustomComponent />")

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://example.com",
                site_docs_prefix="/docs"
            ))

            assert len(items) == 1
            item = items[0]
            assert item.rel_path == "01-admin/user.mdx"
            assert item.site_url == "https://example.com/docs/admin/user"

    def test_crawler_item_dataclass(self):
        """Тест структуры CrawlerItem"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.md"
            file_path.write_text("# Test")

            item = CrawlerItem(
                abs_path=file_path,
                rel_path="test.md",
                dir_meta={"current_label": "Test"},
                mtime=1234567890.0,
                site_url="https://example.com/test"
            )

            assert item.abs_path == file_path
            assert item.rel_path == "test.md"
            assert item.dir_meta["current_label"] == "Test"
            assert item.mtime == 1234567890.0
            assert item.site_url == "https://example.com/test"


if __name__ == "__main__":
    pytest.main([__file__])
