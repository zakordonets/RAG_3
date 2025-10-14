#!/usr/bin/env python3
"""
Тесты для универсального чанкера из новой структуры ingestion.

Legacy-модуль AdaptiveChunker был удалён вместе с рефакторингом пайплайна, поэтому
тесты переведены на актуальный `UniversalChunker`. Проверяем, что базовые сценарии
(короткие/длинные документы, структурный парсинг Markdown) работают штатно.
"""

from ingestion.chunking.universal_chunker import (
    Block,
    OversizePolicy,
    UniversalChunker,
)


class TestUniversalChunkerCompatibility:
    """Адаптированные тесты, обеспечивающие совместимость c новой структурой."""

    def setup_method(self) -> None:
        self.chunker = UniversalChunker(
            max_tokens=600,
            min_tokens=350,
            overlap_base=100,
            oversize_block_policy=OversizePolicy.SPLIT,
            oversize_block_limit=1200,
        )

    def test_chunker_initialization(self):
        """Проверяем, что параметры передаются в UniversalChunker без изменений."""
        assert self.chunker.max_tokens == 600
        assert self.chunker.min_tokens == 350
        assert self.chunker.overlap_base == 100
        assert self.chunker.oversize_block_policy == OversizePolicy.SPLIT
        assert self.chunker.oversize_block_limit == 1200

    def test_chunk_markdown_short_text(self):
        """Короткий Markdown возвращает один чанк."""
        text = "# Заголовок\n\nЭто короткий документ для теста."
        chunks = self.chunker.chunk(text, "markdown", {"doc_id": "short-doc"})
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.chunk_index == 0
        assert chunk.total_chunks == 1
        assert "Заголовок" in chunk.text

    def test_chunk_markdown_long_text(self):
        """Длинный Markdown разбивается на несколько чанков."""
        paragraph = (
            "# Заголовок\n\n"
            + "Это довольно длинный параграф, который повторяется много раз. "
            * 120
        )
        chunks = self.chunker.chunk(paragraph, "markdown", {"doc_id": "long-doc"})
        assert len(chunks) >= 2
        assert all(isinstance(chunk.chunk_index, int) for chunk in chunks)
        assert chunks[0].total_chunks == len(chunks)

    def test_blockify_markdown_detects_structure(self):
        """Внутренний разбор Markdown распознаёт заголовки, списки и параграфы."""
        text = """
# Заголовок 1

Это параграф.

- Список
- Из двух элементов

```python
print("code block")
```
"""
        blocks = self.chunker._blockify_markdown(text)  # pylint: disable=protected-access
        types = {block.type for block in blocks}
        assert {"heading", "paragraph", "list", "code_block"} <= types
        assert any(isinstance(block, Block) for block in blocks)

    def test_oversize_policy_split(self):
        """Политика SPLIT гарантирует, что oversize блоки разбиваются на части."""
        large_list = "\n".join(f"- Пункт {i}" for i in range(500))
        blocks = self.chunker._safe_split_oversize_block(  # pylint: disable=protected-access
            Block(
                type="list",
                text=large_list,
                depth=0,
                is_atomic=True,
                start_line=0,
                end_line=0,
            )
        )
        assert len(blocks) > 1
        assert all(block.type == "list" for block in blocks)

    def test_chunk_handles_empty_text(self):
        """Пустой текст не приводит к исключению и возвращает пустой список."""
        assert self.chunker.chunk("", "markdown", {"doc_id": "empty"}) == []
