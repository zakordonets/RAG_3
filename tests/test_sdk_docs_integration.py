"""
Интеграционные тесты для SDK документации загрузчика
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

from ingestion.adapters.docusaurus import DocusaurusAdapter
from ingestion.crawlers.docusaurus_fs_crawler import crawl_docs

pytestmark = pytest.mark.integration


class TestSDKDocsAdapter:
    """Интеграционные тесты для DocusaurusAdapter с SDK документацией"""

    def test_adapter_with_top_level_meta_single_platform(self):
        """Тест адаптера с top_level_meta для одной платформы"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру Android SDK
            android_dir = docs_root / "android"
            android_dir.mkdir()
            getting_started = android_dir / "getting-started"
            getting_started.mkdir()

            installation_file = getting_started / "installation.md"
            installation_file.write_text("# Android Installation Guide")

            top_level_meta = {
                "android": {
                    "sdk_platform": "android",
                    "product": "sdk"
                }
            }

            adapter = DocusaurusAdapter(
                docs_root=str(docs_root),
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix="",
                top_level_meta=top_level_meta
            )

            documents = list(adapter.iter_documents())

            assert len(documents) == 1
            doc = documents[0]

            # Проверяем метаданные
            assert doc.meta["top_level_dir"] == "android"
            assert doc.meta["sdk_platform"] == "android"
            assert doc.meta["product"] == "sdk"
            assert doc.meta["site_url"] == "https://docs-sdk.edna.ru/android/getting-started/installation"
            assert doc.meta["source"] == "docusaurus"

    def test_adapter_with_top_level_meta_multiple_platforms(self):
        """Тест адаптера с несколькими платформами"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру для Android
            android_dir = docs_root / "android"
            android_dir.mkdir()
            android_file = android_dir / "intro.md"
            android_file.write_text("# Android SDK")

            # Создаем структуру для iOS
            ios_dir = docs_root / "ios"
            ios_dir.mkdir()
            ios_file = ios_dir / "intro.md"
            ios_file.write_text("# iOS SDK")

            # Создаем структуру для Web
            web_dir = docs_root / "web"
            web_dir.mkdir()
            web_file = web_dir / "intro.md"
            web_file.write_text("# Web SDK")

            top_level_meta = {
                "android": {
                    "sdk_platform": "android",
                    "product": "sdk"
                },
                "ios": {
                    "sdk_platform": "ios",
                    "product": "sdk"
                },
                "web": {
                    "sdk_platform": "web",
                    "product": "sdk"
                }
            }

            adapter = DocusaurusAdapter(
                docs_root=str(docs_root),
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix="",
                top_level_meta=top_level_meta
            )

            documents = list(adapter.iter_documents())

            assert len(documents) == 3

            # Проверяем, что все платформы обработаны
            platforms = {doc.meta["sdk_platform"] for doc in documents}
            assert platforms == {"android", "ios", "web"}

            # Проверяем URL для каждой платформы
            urls = {doc.meta["site_url"] for doc in documents}
            assert "https://docs-sdk.edna.ru/android/intro" in urls
            assert "https://docs-sdk.edna.ru/ios/intro" in urls
            assert "https://docs-sdk.edna.ru/web/intro" in urls

    def test_adapter_with_category_json_and_top_level_meta(self):
        """Тест адаптера с _category_.json и top_level_meta"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру Android с категориями
            android_dir = docs_root / "android"
            android_dir.mkdir()

            guides_dir = android_dir / "guides"
            guides_dir.mkdir()

            # Создаем _category_.json
            category_file = guides_dir / "_category_.json"
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump({"label": "Руководства"}, f, ensure_ascii=False)

            guide_file = guides_dir / "quickstart.md"
            guide_file.write_text("# Quick Start")

            top_level_meta = {
                "android": {
                    "sdk_platform": "android",
                    "product": "sdk"
                }
            }

            adapter = DocusaurusAdapter(
                docs_root=str(docs_root),
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix="",
                top_level_meta=top_level_meta
            )

            documents = list(adapter.iter_documents())

            assert len(documents) == 1
            doc = documents[0]

            # Проверяем, что top_level_meta добавлены
            assert doc.meta["top_level_dir"] == "android"
            assert doc.meta["sdk_platform"] == "android"
            assert doc.meta["product"] == "sdk"

            # Проверяем, что метаданные из _category_.json тоже присутствуют
            assert "dir_meta" in doc.meta
            assert doc.meta["dir_meta"]["current_label"] == "Руководства"

    def test_adapter_without_top_level_meta(self):
        """Тест адаптера без top_level_meta (обратная совместимость)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            admin_dir = docs_root / "01-admin"
            admin_dir.mkdir()

            user_file = admin_dir / "user.md"
            user_file.write_text("# Users")

            adapter = DocusaurusAdapter(
                docs_root=str(docs_root),
                site_base_url="https://docs-chatcenter.edna.ru",
                site_docs_prefix="/docs"
            )

            documents = list(adapter.iter_documents())

            assert len(documents) == 1
            doc = documents[0]

            # Проверяем, что базовые метаданные присутствуют
            assert "site_url" in doc.meta
            assert doc.meta["site_url"] == "https://docs-chatcenter.edna.ru/docs/admin/user"
            assert doc.meta["source"] == "docusaurus"

            # top_level_dir должен быть в dir_meta, но не в корне meta
            if "top_level_dir" in doc.meta.get("dir_meta", {}):
                assert doc.meta["dir_meta"]["top_level_dir"] == "01-admin"

    def test_adapter_empty_prefix_urls(self):
        """Тест корректности URL без префикса /docs"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            android_dir = docs_root / "android"
            android_dir.mkdir()

            nested_dir = android_dir / "api" / "reference"
            nested_dir.mkdir(parents=True)

            api_file = nested_dir / "methods.md"
            api_file.write_text("# API Methods")

            adapter = DocusaurusAdapter(
                docs_root=str(docs_root),
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix=""
            )

            documents = list(adapter.iter_documents())

            assert len(documents) == 1
            doc = documents[0]

            # URL не должен содержать префикс /docs (проверяем, что путь не начинается с /docs/)
            assert doc.meta["site_url"] == "https://docs-sdk.edna.ru/android/api/reference/methods"
            # Проверяем, что URL не начинается с базового URL + /docs/
            assert not doc.meta["site_url"].startswith("https://docs-sdk.edna.ru/docs/")
            # Проверяем, что путь начинается сразу с платформы
            assert "/android/api/reference/methods" in doc.meta["site_url"]

    def test_adapter_max_pages_limit(self):
        """Тест ограничения количества страниц через max_pages"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем 5 файлов
            for i in range(5):
                file_path = docs_root / f"file_{i}.md"
                file_path.write_text(f"# File {i}")

            adapter = DocusaurusAdapter(
                docs_root=str(docs_root),
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix="",
                max_pages=3
            )

            documents = list(adapter.iter_documents())

            # Должно быть обработано только 3 файла
            assert len(documents) == 3


class TestSDKDocsCrawlerIntegration:
    """Интеграционные тесты для crawler с SDK структурой"""

    def test_crawler_sdk_structure_without_category_json(self):
        """Тест краулера со структурой SDK без _category_.json в корне"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            # Создаем структуру android/getting-started/installation.md
            android_dir = docs_root / "android"
            android_dir.mkdir()

            getting_started = android_dir / "getting-started"
            getting_started.mkdir()

            # Создаем _category_.json только во вложенной папке
            category_file = getting_started / "_category_.json"
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump({"label": "Начало работы"}, f, ensure_ascii=False)

            installation_file = getting_started / "installation.md"
            installation_file.write_text("# Installation")

            top_level_meta = {
                "android": {
                    "sdk_platform": "android",
                    "product": "sdk"
                }
            }

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix="",
                top_level_meta=top_level_meta
            ))

            assert len(items) == 1
            item = items[0]

            # Проверяем метаданные
            assert item.dir_meta["top_level_dir"] == "android"
            assert item.dir_meta["sdk_platform"] == "android"
            assert item.dir_meta["product"] == "sdk"
            assert item.dir_meta["current_label"] == "Начало работы"
            assert item.site_url == "https://docs-sdk.edna.ru/android/getting-started/installation"

    def test_crawler_meta_priority(self):
        """Тест приоритета метаданных: top_level_meta не перезаписывает _category_.json"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_root = Path(temp_dir)

            android_dir = docs_root / "android"
            android_dir.mkdir()

            # Создаем _category_.json с полем, которое может конфликтовать
            category_file = android_dir / "_category_.json"
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump({"label": "Android SDK"}, f, ensure_ascii=False)

            intro_file = android_dir / "intro.md"
            intro_file.write_text("# Intro")

            top_level_meta = {
                "android": {
                    "sdk_platform": "android",
                    "product": "sdk"
                }
            }

            items = list(crawl_docs(
                docs_root=docs_root,
                site_base_url="https://docs-sdk.edna.ru",
                site_docs_prefix="",
                top_level_meta=top_level_meta
            ))

            assert len(items) == 1
            item = items[0]

            # Проверяем, что оба типа метаданных присутствуют
            assert item.dir_meta["top_level_dir"] == "android"
            assert item.dir_meta["sdk_platform"] == "android"
            assert item.dir_meta["product"] == "sdk"
            assert item.dir_meta["current_label"] == "Android SDK"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
