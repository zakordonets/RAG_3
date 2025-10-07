from pathlib import Path
from ingestion.utils.docusaurus_utils import fs_to_url, clean_segment


def test_fs_to_url_basic():
    url = fs_to_url(
        Path(r"C:\\CC_RAG\\docs"),
        Path(r"C:\\CC_RAG\\docs\\40-admin\\02-widget\\01-admin-widget-features.md"),
        "https://docs-chatcenter.edna.ru",
        "/docs",
        drop_prefix_all_levels=True,
    )
    assert url == "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features"


def test_fs_to_url_first_level_only():
    """Тест удаления префикса только на первом уровне"""
    url = fs_to_url(
        Path(r"C:\\CC_RAG\\docs"),
        Path(r"C:\\CC_RAG\\docs\\40-admin\\02-widget\\01-admin-widget-features.md"),
        "https://docs-chatcenter.edna.ru",
        "/docs",
        drop_prefix_all_levels=False,
    )
    assert url == "https://docs-chatcenter.edna.ru/docs/admin/02-widget/01-admin-widget-features"


def test_fs_to_url_with_trailing_slash():
    """Тест с добавлением trailing slash"""
    url = fs_to_url(
        Path(r"C:\\CC_RAG\\docs"),
        Path(r"C:\\CC_RAG\\docs\\40-admin\\02-widget\\01-admin-widget-features.md"),
        "https://docs-chatcenter.edna.ru",
        "/docs",
        drop_prefix_all_levels=True,
        add_trailing_slash=True,
    )
    assert url == "https://docs-chatcenter.edna.ru/docs/admin/widget/admin-widget-features"


def test_clean_segment_with_prefix():
    """Тест очистки сегмента с числовым префиксом"""
    assert clean_segment("01-admin-widget-features.md") == "admin-widget-features"
    assert clean_segment("40-admin") == "admin"
    assert clean_segment("02-widget") == "widget"


def test_clean_segment_without_prefix():
    """Тест очистки сегмента без числового префикса"""
    assert clean_segment("admin-widget-features.md") == "admin-widget-features"
    assert clean_segment("widget") == "widget"


def test_clean_segment_no_drop_prefix():
    """Тест без удаления префикса"""
    assert clean_segment("01-admin-widget-features.md", drop_numeric_prefix=False) == "01-admin-widget-features"
    assert clean_segment("40-admin", drop_numeric_prefix=False) == "40-admin"


def test_fs_to_url_simple_path():
    """Тест простого пути без префиксов"""
    url = fs_to_url(
        Path(r"C:\\CC_RAG\\docs"),
        Path(r"C:\\CC_RAG\\docs\\getting-started.md"),
        "https://docs-chatcenter.edna.ru",
        "/docs",
        drop_prefix_all_levels=True,
    )
    assert url == "https://docs-chatcenter.edna.ru/docs/getting-started"


def test_fs_to_url_nested_structure():
    """Тест вложенной структуры"""
    url = fs_to_url(
        Path(r"C:\\CC_RAG\\docs"),
        Path(r"C:\\CC_RAG\\docs\\10-guide\\20-advanced\\30-troubleshooting\\debug.md"),
        "https://docs-chatcenter.edna.ru",
        "/docs",
        drop_prefix_all_levels=True,
    )
    assert url == "https://docs-chatcenter.edna.ru/docs/guide/advanced/troubleshooting/debug"
