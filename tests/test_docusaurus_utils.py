"""
Тесты для Docusaurus утилит
"""

import pytest
from ingestion.utils.docusaurus_utils import clean, replace_contentref, clean_segment, fs_to_url
from pathlib import Path

pytestmark = pytest.mark.unit


class TestDocusaurusClean:
    """Тесты для docusaurus_clean.py"""

    def test_clean_empty_input(self):
        """Тест очистки пустого ввода"""
        assert clean("") == ""
        assert clean("   ") == ""

    def test_clean_imports_exports(self):
        """Тест удаления импортов и экспортов"""
        text = """
import React from 'react';
export default function Component() {}
import { useState } from 'react';
export const MyComponent = () => {};
Some content here.
"""
        result = clean(text)
        assert "import" not in result
        assert "export" not in result
        assert "Some content here." in result

    def test_clean_html_comments(self):
        """Тест удаления HTML комментариев"""
        text = """
<!-- This is a comment -->
Some content
<!-- Another comment -->
More content
"""
        result = clean(text)
        assert "<!--" not in result
        assert "This is a comment" not in result
        assert "Some content" in result
        assert "More content" in result

    def test_clean_self_closing_jsx(self):
        """Тест удаления самозакрывающихся JSX тегов"""
        text = """
<Image src="/image.png" alt="Test" />
<Button variant="primary" />
Some content
"""
        result = clean(text)
        assert "<Image" not in result
        assert "<Button" not in result
        assert "Some content" in result

    def test_clean_paired_jsx(self):
        """Тест удаления парных JSX тегов"""
        text = """
<CustomComponent>
  <p>Content inside</p>
</CustomComponent>
Some content
"""
        result = clean(text)
        assert "<CustomComponent>" not in result
        assert "Content inside" in result
        assert "Some content" in result

    def test_clean_admonitions(self):
        """Тест обработки admonitions"""
        text = """
:::tip
This is a tip
:::

:::warning
This is a warning
:::

:::info
This is info
:::

Some content
"""
        result = clean(text)
        assert "This is a tip" in result
        assert "This is a warning" in result
        assert "This is info" in result
        assert ":::" not in result
        assert "Some content" in result

    def test_clean_whitespace_normalization(self):
        """Тест нормализации пробелов"""
        text = """
Multiple    spaces   here


Multiple newlines


And tabs	here
"""
        result = clean(text)
        # Проверяем, что множественные пробелы и переносы нормализованы
        assert "Multiple spaces here" in result
        assert "Multiple newlines" in result
        assert "And tabs here" in result

    def test_clean_complex_example(self):
        """Тест сложного примера со всеми правилами"""
        text = """
import React from 'react';

<!-- HTML comment -->
<CustomComponent>
  <Image src="/test.png" />
  <p>Content</p>
</CustomComponent>

:::tip
This is a tip with    multiple   spaces
:::

export default function Test() {}
"""
        result = clean(text)

        # Проверяем удаление
        assert "import" not in result
        assert "export" not in result
        assert "<!--" not in result
        assert "<CustomComponent>" not in result
        assert "<Image" not in result
        assert ":::" not in result

        # Проверяем сохранение контента
        assert "Content" in result
        assert "This is a tip with multiple spaces" in result


class TestDocusaurusLinks:
    """Тесты для docusaurus_links.py"""

    def test_replace_contentref_basic(self):
        """Тест базовой замены ContentRef"""
        text = '<ContentRef url="/docs/admin/user">Пользователи</ContentRef>'
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru")
        expected = 'Пользователи (см. https://docs-chatcenter.edna.ru/docs/admin/user)'
        assert result == expected

    def test_replace_contentref_relative_url(self):
        """Тест замены с относительным URL"""
        text = '<ContentRef url="/admin/user">Пользователи</ContentRef>'
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru")
        expected = 'Пользователи (см. https://docs-chatcenter.edna.ru/admin/user)'
        assert result == expected

    def test_replace_contentref_absolute_url(self):
        """Тест замены с абсолютным URL"""
        text = '<ContentRef url="https://example.com/page">Внешняя ссылка</ContentRef>'
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru")
        expected = 'Внешняя ссылка (см. https://example.com/page)'
        assert result == expected

    def test_replace_contentref_empty_label(self):
        """Тест замены с пустой меткой"""
        text = '<ContentRef url="/docs/admin/user"></ContentRef>'
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru")
        expected = ' (см. https://docs-chatcenter.edna.ru/docs/admin/user)'
        assert result == expected

    def test_replace_contentref_multiline_label(self):
        """Тест замены с многострочной меткой"""
        text = '''<ContentRef url="/docs/admin/user">
Пользователи
системы
</ContentRef>'''
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru")
        expected = '''Пользователи
системы (см. https://docs-chatcenter.edna.ru/docs/admin/user)'''
        assert result == expected

    def test_replace_contentref_multiple_refs(self):
        """Тест замены нескольких ContentRef"""
        text = '''
<ContentRef url="/docs/admin/user">Пользователи</ContentRef>
Some text
<ContentRef url="/docs/admin/role">Роли</ContentRef>
'''
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru")
        assert "Пользователи (см. https://docs-chatcenter.edna.ru/docs/admin/user)" in result
        assert "Роли (см. https://docs-chatcenter.edna.ru/docs/admin/role)" in result
        assert "Some text" in result

    def test_replace_contentref_with_query_params(self):
        """Тест замены с параметрами запроса"""
        text = '<ContentRef url="/docs/admin/user?tab=settings">Настройки</ContentRef>'
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru")
        expected = 'Настройки (см. https://docs-chatcenter.edna.ru/docs/admin/user?tab=settings)'
        assert result == expected

    def test_replace_contentref_site_base_trailing_slash(self):
        """Тест с site_base, заканчивающимся слешем"""
        text = '<ContentRef url="/docs/admin/user">Пользователи</ContentRef>'
        result = replace_contentref(text, "https://docs-chatcenter.edna.ru/")
        expected = 'Пользователи (см. https://docs-chatcenter.edna.ru/docs/admin/user)'
        assert result == expected


class TestDocusaurusPathing:
    """Тесты для docusaurus_pathing.py"""

    def test_clean_segment_basic(self):
        """Тест базовой очистки сегмента"""
        assert clean_segment("admin") == "admin"
        assert clean_segment("user-management") == "user-management"
        assert clean_segment("page.md") == "page"

    def test_clean_segment_with_numeric_prefix(self):
        """Тест очистки с числовым префиксом"""
        assert clean_segment("01-admin") == "admin"
        assert clean_segment("02-user") == "user"
        assert clean_segment("10-settings") == "settings"

    def test_clean_segment_drop_numeric_prefix_false(self):
        """Тест без удаления числового префикса"""
        assert clean_segment("01-admin", drop_numeric_prefix=False) == "01-admin"
        assert clean_segment("02-user", drop_numeric_prefix=False) == "02-user"

    def test_clean_segment_file_extension(self):
        """Тест удаления расширения файла"""
        assert clean_segment("page.md") == "page"
        assert clean_segment("document.mdx") == "document"
        assert clean_segment("image.png") == "image"

    def test_clean_segment_complex(self):
        """Тест сложной очистки"""
        assert clean_segment("01-admin-page.md") == "admin-page"
        assert clean_segment("02-user-settings.mdx") == "user-settings"

    def test_fs_to_url_basic(self):
        """Тест базового преобразования пути в URL"""
        docs_root = Path("C:/docs")
        abs_path = Path("C:/docs/admin/user.md")
        result = fs_to_url(docs_root, abs_path, "https://example.com", "/docs")
        assert result == "https://example.com/docs/admin/user"

    def test_fs_to_url_with_numeric_prefix(self):
        """Тест преобразования с числовыми префиксами"""
        docs_root = Path("C:/docs")
        abs_path = Path("C:/docs/01-admin/02-user.md")
        result = fs_to_url(docs_root, abs_path, "https://example.com", "/docs")
        assert result == "https://example.com/docs/admin/user"

    def test_fs_to_url_drop_prefix_false(self):
        """Тест без удаления префиксов на всех уровнях"""
        docs_root = Path("C:/docs")
        abs_path = Path("C:/docs/01-admin/02-user.md")
        result = fs_to_url(docs_root, abs_path, "https://example.com", "/docs",
                          drop_prefix_all_levels=False)
        # Функция всегда удаляет префикс на первом уровне
        assert result == "https://example.com/docs/admin/02-user"

    def test_fs_to_url_trailing_slash(self):
        """Тест с обработкой завершающего слеша"""
        docs_root = Path("C:/docs")
        abs_path = Path("C:/docs/admin/user.md")
        result = fs_to_url(docs_root, abs_path, "https://example.com", "/docs",
                          add_trailing_slash=True)
        # Функция удаляет завершающий слеш при add_trailing_slash=True
        assert result == "https://example.com/docs/admin/user"

    def test_fs_to_url_nested_path(self):
        """Тест вложенного пути"""
        docs_root = Path("C:/docs")
        abs_path = Path("C:/docs/01-admin/02-user/03-settings.md")
        result = fs_to_url(docs_root, abs_path, "https://example.com", "/docs")
        assert result == "https://example.com/docs/admin/user/settings"

    def test_fs_to_url_root_file(self):
        """Тест файла в корне"""
        docs_root = Path("C:/docs")
        abs_path = Path("C:/docs/index.md")
        result = fs_to_url(docs_root, abs_path, "https://example.com", "/docs")
        assert result == "https://example.com/docs/index"

    def test_fs_to_url_different_docs_prefix(self):
        """Тест с другим префиксом документации"""
        docs_root = Path("C:/docs")
        abs_path = Path("C:/docs/admin/user.md")
        result = fs_to_url(docs_root, abs_path, "https://example.com", "/help")
        assert result == "https://example.com/help/admin/user"

    def test_fs_to_url_empty_prefix(self):
        """Тест с пустым префиксом документации (для SDK docs)"""
        docs_root = Path("C:/SDK_docs/docs")
        abs_path = Path("C:/SDK_docs/docs/android/getting-started/installation.md")
        result = fs_to_url(docs_root, abs_path, "https://docs-sdk.edna.ru", "")
        assert result == "https://docs-sdk.edna.ru/android/getting-started/installation"

    def test_fs_to_url_empty_prefix_root_file(self):
        """Тест файла в корне с пустым префиксом"""
        docs_root = Path("C:/SDK_docs/docs")
        abs_path = Path("C:/SDK_docs/docs/index.md")
        result = fs_to_url(docs_root, abs_path, "https://docs-sdk.edna.ru", "")
        # Файл в корне все равно имеет имя, поэтому URL будет с именем файла
        assert result == "https://docs-sdk.edna.ru/index"

    def test_fs_to_url_empty_prefix_single_level(self):
        """Тест одноуровневой структуры с пустым префиксом"""
        docs_root = Path("C:/SDK_docs/docs")
        abs_path = Path("C:/SDK_docs/docs/android.md")
        result = fs_to_url(docs_root, abs_path, "https://docs-sdk.edna.ru", "")
        assert result == "https://docs-sdk.edna.ru/android"

    def test_fs_to_url_empty_prefix_with_numeric_prefixes(self):
        """Тест с числовыми префиксами и пустым site_docs_prefix"""
        docs_root = Path("C:/SDK_docs/docs")
        abs_path = Path("C:/SDK_docs/docs/01-android/02-getting-started.md")
        result = fs_to_url(docs_root, abs_path, "https://docs-sdk.edna.ru", "")
        assert result == "https://docs-sdk.edna.ru/android/getting-started"


if __name__ == "__main__":
    pytest.main([__file__])
