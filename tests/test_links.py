import pytest

from ingestion.utils.docusaurus_utils import replace_contentref

pytestmark = pytest.mark.unit


def test_contentref():
    src = '<ContentRef url="/docs/supervisor/dashboards/sv-dashboard-default">Дашборд</ContentRef>'
    out = replace_contentref(src, "https://docs-chatcenter.edna.ru")
    assert "https://docs-chatcenter.edna.ru/docs/supervisor/dashboards/sv-dashboard-default" in out


def test_contentref_basic():
    """Базовый тест замены ContentRef"""
    src = '<ContentRef url="/docs/x/y">Label</ContentRef>'
    result = replace_contentref(src, "https://host")
    expected = "Label (см. https://host/docs/x/y)"
    assert result == expected


def test_contentref_relative_url():
    """Тест с относительным URL"""
    src = '<ContentRef url="/docs/admin/widget">Админ виджет</ContentRef>'
    result = replace_contentref(src, "https://docs-chatcenter.edna.ru")
    expected = "Админ виджет (см. https://docs-chatcenter.edna.ru/docs/admin/widget)"
    assert result == expected


def test_contentref_absolute_url():
    """Тест с абсолютным URL"""
    src = '<ContentRef url="https://external.com/page">Внешняя ссылка</ContentRef>'
    result = replace_contentref(src, "https://docs-chatcenter.edna.ru")
    expected = "Внешняя ссылка (см. https://external.com/page)"
    assert result == expected


def test_contentref_empty_label():
    """Тест с пустым лейблом"""
    src = '<ContentRef url="/docs/page"></ContentRef>'
    result = replace_contentref(src, "https://host")
    expected = " (см. https://host/docs/page)"
    assert result == expected


def test_contentref_multiline_label():
    """Тест с многострочным лейблом"""
    src = '''<ContentRef url="/docs/guide">
Многострочный
лейбл
</ContentRef>'''
    result = replace_contentref(src, "https://host")
    expected = "Многострочный\nлейбл (см. https://host/docs/guide)"
    assert result == expected


def test_contentref_multiple_refs():
    """Тест с несколькими ContentRef в одном тексте"""
    src = '''Смотрите <ContentRef url="/docs/page1">первую страницу</ContentRef>
и <ContentRef url="/docs/page2">вторую страницу</ContentRef> для подробностей.'''
    result = replace_contentref(src, "https://host")
    assert "первую страницу (см. https://host/docs/page1)" in result
    assert "вторую страницу (см. https://host/docs/page2)" in result


def test_contentref_with_quotes():
    """Тест с кавычками в URL"""
    src = '<ContentRef url="/docs/page?param=value">Страница с параметрами</ContentRef>'
    result = replace_contentref(src, "https://host")
    expected = "Страница с параметрами (см. https://host/docs/page?param=value)"
    assert result == expected


def test_contentref_site_base_trailing_slash():
    """Тест с site_base, заканчивающимся на слэш"""
    src = '<ContentRef url="/docs/page">Страница</ContentRef>'
    result = replace_contentref(src, "https://host/")
    expected = "Страница (см. https://host/docs/page)"
    assert result == expected


def test_contentref_no_contentref():
    """Тест текста без ContentRef"""
    src = "Обычный текст без ContentRef ссылок."
    result = replace_contentref(src, "https://host")
    assert result == src


def test_contentref_complex_example():
    """Комплексный тест с различными типами ссылок"""
    src = '''Документация содержит несколько ссылок:
<ContentRef url="/docs/admin">Админ панель</ContentRef>
<ContentRef url="https://external.com">Внешний ресурс</ContentRef>
<ContentRef url="/docs/guide/troubleshooting">Решение проблем</ContentRef>
И обычный текст.'''

    result = replace_contentref(src, "https://docs-chatcenter.edna.ru")

    assert "Админ панель (см. https://docs-chatcenter.edna.ru/docs/admin)" in result
    assert "Внешний ресурс (см. https://external.com)" in result
    assert "Решение проблем (см. https://docs-chatcenter.edna.ru/docs/guide/troubleshooting)" in result
    assert "И обычный текст." in result
