"""
Тесты для функции apply_url_whitelist с поддержкой code blocks
"""

import pytest
from app.services.core.llm_router import apply_url_whitelist

pytestmark = pytest.mark.unit


class TestApplyURLWhitelist:
    """Тесты для функции apply_url_whitelist"""

    def test_preserve_urls_in_code_blocks(self):
        """Тест сохранения URL внутри markdown code blocks"""
        answer = """Для настройки используйте:

```kotlin
allprojects {
    repositories {
        google()
        mavenCentral()
        maven { url 'https://maven-pub.edna.ru/repository/maven-public/' }
    }
}
```

Подробнее: https://docs-sdk.edna.ru/android/getting-started/installation"""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # URL в code block должен быть сохранен
        assert "https://maven-pub.edna.ru/repository/maven-public/" in result
        # URL в обычном тексте должен быть сохранен (если в whitelist)
        assert "https://docs-sdk.edna.ru/android/getting-started/installation" in result

    def test_remove_non_whitelisted_urls_outside_code_blocks(self):
        """Тест удаления неразрешенных URL вне code blocks"""
        answer = """Смотрите документацию: https://example.com/not-allowed

```kotlin
maven { url 'https://maven-pub.edna.ru/repository/maven-public/' }
```

И еще: https://another-example.com"""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # URL в code block должен быть сохранен
        assert "https://maven-pub.edna.ru/repository/maven-public/" in result
        # URL вне code blocks должны быть удалены
        assert "https://example.com/not-allowed" not in result
        assert "https://another-example.com" not in result

    def test_multiple_code_blocks(self):
        """Тест обработки нескольких code blocks"""
        answer = """Первый блок:

```kotlin
maven { url 'https://maven-pub.edna.ru/repository/maven-public/' }
```

Второй блок:

```bash
curl https://api.example.com/endpoint
```

Третий блок:

```json
{
  "url": "https://api.example.com/config"
}
```"""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # Все URL в code blocks должны быть сохранены
        assert "https://maven-pub.edna.ru/repository/maven-public/" in result
        assert "https://api.example.com/endpoint" in result
        assert "https://api.example.com/config" in result

    def test_code_block_with_language_tag(self):
        """Тест code block с указанием языка"""
        answer = """```kotlin
allprojects {
    repositories {
        maven { url 'https://maven-pub.edna.ru/repository/maven-public/' }
    }
}
```"""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # URL должен быть сохранен
        assert "https://maven-pub.edna.ru/repository/maven-public/" in result
        # Code block должен сохранить структуру
        assert "```kotlin" in result
        assert "```" in result

    def test_nested_code_blocks_in_text(self):
        """Тест вложенных code blocks (если такие возможны)"""
        answer = """Текст до блока.

```kotlin
maven { url 'https://maven-pub.edna.ru/repository/maven-public/' }
```

Текст после блока с ссылкой https://docs-sdk.edna.ru/android/getting-started/installation"""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # URL в code block должен быть сохранен
        assert "https://maven-pub.edna.ru/repository/maven-public/" in result
        # URL в обычном тексте должен быть сохранен (если в whitelist)
        assert "https://docs-sdk.edna.ru/android/getting-started/installation" in result

    def test_empty_code_block(self):
        """Тест пустого code block"""
        answer = """Текст до блока.

```
```

Текст после блока."""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # Пустой code block должен быть сохранен
        assert "```" in result

    def test_markdown_links_in_code_blocks(self):
        """Тест markdown ссылок внутри code blocks (должны сохраняться)"""
        answer = """```markdown
[Ссылка](https://example.com/not-allowed)
```"""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # Markdown ссылка в code block должна быть сохранена полностью
        assert "[Ссылка](https://example.com/not-allowed)" in result

    def test_markdown_links_outside_code_blocks(self):
        """Тест markdown ссылок вне code blocks"""
        answer = """Смотрите [документацию](https://docs-sdk.edna.ru/android/getting-started/installation)

И [другую ссылку](https://example.com/not-allowed)"""

        sources = [
            {"url": "https://docs-sdk.edna.ru/android/getting-started/installation"}
        ]

        result = apply_url_whitelist(answer, sources)

        # Разрешенная ссылка должна быть сохранена
        assert "[документацию](https://docs-sdk.edna.ru/android/getting-started/installation)" in result
        # Неразрешенная ссылка должна быть удалена, но текст остаться
        assert "другую ссылку" in result
        assert "https://example.com/not-allowed" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
