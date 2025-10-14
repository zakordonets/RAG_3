import pytest

from ingestion.utils.docusaurus_utils import clean

pytestmark = pytest.mark.unit


def test_clean_admonitions_and_jsx():
    src = """:::tip
Полезный совет
:::
import X from '/img/icon.svg';
<SupportButton />
"""
    out = clean(src)
    assert "Полезный совет" in out
    assert "import" not in out
    assert "SupportButton" not in out


def test_clean_empty_input():
    """Тест пустого ввода"""
    assert clean("") == ""
    assert clean("   ") == ""
    assert clean("\n\n\n") == ""


def test_clean_imports_and_exports():
    """Тест удаления импортов и экспортов"""
    src = """import React from 'react';
export { Button } from './Button';
import './styles.css';

# Заголовок
Текст документации.
"""
    result = clean(src)
    assert "import" not in result
    assert "export" not in result
    assert "Заголовок" in result
    assert "Текст документации" in result


def test_clean_html_comments():
    """Тест удаления HTML комментариев"""
    src = """<!-- Это комментарий -->
# Заголовок
Текст <!-- еще комментарий --> продолжение
"""
    result = clean(src)
    assert "комментарий" not in result
    assert "Заголовок" in result
    assert "продолжение" in result


def test_clean_self_closing_jsx():
    """Тест удаления самозакрывающихся JSX компонентов"""
    src = """<SupportButton />
<Icon name="help" />
<Image src="/path/to/image.png" alt="Description" />

# Заголовок
Текст документации.
"""
    result = clean(src)
    assert "SupportButton" not in result
    assert "Icon" not in result
    assert "Image" not in result
    assert "Заголовок" in result
    assert "Текст документации" in result


def test_clean_paired_jsx():
    """Тест удаления парных JSX компонентов"""
    src = """<Tabs>
<TabItem value="tab1">
Содержимое первой вкладки
</TabItem>
<TabItem value="tab2">
Содержимое второй вкладки
</TabItem>
</Tabs>

# Заголовок
Текст документации.
"""
    result = clean(src)
    assert "Tabs" not in result
    assert "TabItem" not in result
    assert "Содержимое первой вкладки" in result
    assert "Содержимое второй вкладки" in result
    assert "Заголовок" in result


def test_clean_admonitions():
    """Тест обработки admonitions"""
    src = """:::tip
Это полезный совет
:::

:::warning
Это предупреждение
:::

:::info
Это информация
:::

:::note
Это заметка
:::

:::caution
Это осторожность
:::

:::danger
Это опасность
:::

# Заголовок
Текст документации.
"""
    result = clean(src)
    assert "Это полезный совет" in result
    assert "Это предупреждение" in result
    assert "Это информация" in result
    assert "Это заметка" in result
    assert "Это осторожность" in result
    assert "Это опасность" in result
    assert "Заголовок" in result
    assert ":::" not in result


def test_clean_whitespace_normalization():
    """Тест нормализации пробелов и переносов строк"""
    src = """#   Заголовок   с   лишними   пробелами


Текст    с    множественными    пробелами.




Много пустых строк.
"""
    result = clean(src)
    # Проверяем, что множественные пробелы схлопнуты
    assert "   " not in result
    # Проверяем, что множественные пустые строки схлопнуты
    assert "\n\n\n" not in result
    assert "Заголовок с лишними пробелами" in result
    assert "Текст с множественными пробелами" in result


def test_clean_complex_example():
    """Комплексный тест с различными элементами"""
    src = """import React from 'react';
<!-- HTML комментарий -->
export { Component } from './Component';

# Заголовок документа

:::tip
Полезный совет для пользователей
:::

<SupportButton />
<Tabs>
<TabItem value="example">
Пример использования
</TabItem>
</Tabs>

Текст документации с    лишними   пробелами.




Много пустых строк.
"""
    result = clean(src)
    # Проверяем удаление импортов/экспортов
    assert "import" not in result
    assert "export" not in result
    # Проверяем удаление комментариев
    assert "комментарий" not in result
    # Проверяем удаление JSX
    assert "SupportButton" not in result
    assert "Tabs" not in result
    assert "TabItem" not in result
    # Проверяем сохранение содержимого
    assert "Заголовок документа" in result
    assert "Полезный совет для пользователей" in result
    assert "Пример использования" in result
    assert "Текст документации с лишними пробелами" in result
    # Проверяем нормализацию пробелов
    assert "   " not in result
    assert "\n\n\n" not in result
