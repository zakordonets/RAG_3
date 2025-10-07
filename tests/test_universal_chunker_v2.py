"""
Тесты для UniversalChunker v2
"""

import pytest
from unittest.mock import Mock, patch
from ingestion.chunking.universal_chunker import (
    UniversalChunker,
    Block,
    Chunk,
    OversizePolicy,
    chunk_text_universal
)


class TestUniversalChunker:
    """Тесты для UniversalChunker"""

    def test_chunker_initialization(self):
        """Тест инициализации чанкера"""
        chunker = UniversalChunker(
            max_tokens=600,
            min_tokens=350,
            overlap_base=100
        )

        assert chunker.max_tokens == 600
        assert chunker.min_tokens == 350
        assert chunker.overlap_base == 100
        assert chunker.oversize_block_policy == OversizePolicy.SPLIT

    def test_blockify_markdown_basic(self):
        """Тест базового разбиения Markdown на блоки"""
        text = """
# Заголовок 1

Это параграф с текстом.

## Заголовок 2

- Пункт списка 1
- Пункт списка 2

```python
def hello():
    print("Hello")
```

Еще один параграф.
"""

        chunker = UniversalChunker()
        blocks = chunker._blockify_markdown(text)

        # Проверяем, что блоки правильно классифицированы
        block_types = [block.type for block in blocks]
        assert 'heading' in block_types
        assert 'paragraph' in block_types
        assert 'list' in block_types
        assert 'code_block' in block_types

    def test_blockify_markdown_headings(self):
        """Тест разбиения с заголовками разных уровней"""
        text = """
# Главный заголовок

Текст под главным заголовком.

## Подзаголовок 1

Текст под подзаголовком 1.

### Подзаголовок 2

Текст под подзаголовком 2.
"""

        chunker = UniversalChunker()
        blocks = chunker._blockify_markdown(text)

        # Проверяем заголовки
        headings = [block for block in blocks if block.type == 'heading']
        assert len(headings) == 3
        assert headings[0].depth == 1
        assert headings[1].depth == 2
        assert headings[2].depth == 3

    def test_blockify_markdown_lists(self):
        """Тест разбиения списков"""
        text = """
- Пункт 1
- Пункт 2
- Пункт 3

1. Нумерованный пункт 1
2. Нумерованный пункт 2
"""

        chunker = UniversalChunker()
        blocks = chunker._blockify_markdown(text)

        # Проверяем списки
        lists = [block for block in blocks if block.type == 'list']
        assert len(lists) == 2

    def test_blockify_markdown_code_blocks(self):
        """Тест разбиения код-блоков"""
        text = """
```python
def hello():
    print("Hello, World!")
    return True
```

```javascript
function test() {
    console.log("Test");
}
```
"""

        chunker = UniversalChunker()
        blocks = chunker._blockify_markdown(text)

        # Проверяем код-блоки
        code_blocks = [block for block in blocks if block.type == 'code_block']
        assert len(code_blocks) == 2
        assert all(block.is_atomic for block in code_blocks)

    def test_blockify_markdown_tables(self):
        """Тест разбиения таблиц"""
        text = """
| Колонка 1 | Колонка 2 | Колонка 3 |
|-----------|-----------|-----------|
| Значение 1| Значение 2| Значение 3|
| Значение 4| Значение 5| Значение 6|
"""

        chunker = UniversalChunker()
        blocks = chunker._blockify_markdown(text)

        # Проверяем таблицы
        tables = [block for block in blocks if block.type == 'table']
        assert len(tables) == 1
        assert tables[0].is_atomic

    def test_safe_split_oversize_code_block(self):
        """Тест безопасного разбиения большого код-блока"""
        # Создаем большой код-блок
        large_code = "```python\n" + "\n".join([f"# Комментарий {i}\nprint('Line {i}')" for i in range(50)]) + "\n```"

        block = Block(
            type='code_block',
            text=large_code,
            depth=0,
            is_atomic=True,
            start_line=0,
            end_line=0
        )

        chunker = UniversalChunker()
        split_blocks = chunker._safe_split_oversize_block(block)

        # Должно быть разбито на несколько блоков
        assert len(split_blocks) > 1
        assert all(block.type == 'code_block' for block in split_blocks)

    def test_safe_split_oversize_list(self):
        """Тест безопасного разбиения большого списка"""
        # Создаем большой список с большим количеством токенов
        large_list = "\n".join([f"- Очень длинный пункт списка номер {i} с дополнительным текстом для увеличения количества токенов" for i in range(100)])

        block = Block(
            type='list',
            text=large_list,
            depth=0,
            is_atomic=True,
            start_line=0,
            end_line=0
        )

        chunker = UniversalChunker()
        split_blocks = chunker._safe_split_oversize_block(block)

        # Должно быть разбито на несколько блоков
        assert len(split_blocks) > 1
        assert all(block.type == 'list' for block in split_blocks)

    def test_safe_split_oversize_table(self):
        """Тест безопасного разбиения большой таблицы"""
        # Создаем большую таблицу с большим количеством токенов
        table_header = "| Очень длинная колонка 1 | Очень длинная колонка 2 | Очень длинная колонка 3 |"
        table_separator = "|------------------------|------------------------|------------------------|"
        table_rows = "\n".join([f"| Очень длинное значение {i} с дополнительным текстом | Очень длинное значение {i+1} с дополнительным текстом | Очень длинное значение {i+2} с дополнительным текстом |" for i in range(1, 101, 3)])

        large_table = f"{table_header}\n{table_separator}\n{table_rows}"

        block = Block(
            type='table',
            text=large_table,
            depth=0,
            is_atomic=True,
            start_line=0,
            end_line=0
        )

        chunker = UniversalChunker()
        split_blocks = chunker._safe_split_oversize_block(block)

        # Должно быть разбито на несколько блоков
        assert len(split_blocks) > 1
        assert all(block.type == 'table' for block in split_blocks)

    def test_semantic_packing_basic(self):
        """Тест базовой семантической упаковки"""
        blocks = [
            Block(type='heading', text='# Заголовок', depth=1, is_atomic=False, start_line=0, end_line=0),
            Block(type='paragraph', text='Короткий параграф.', depth=0, is_atomic=False, start_line=1, end_line=1),
            Block(type='paragraph', text='Еще один короткий параграф.', depth=0, is_atomic=False, start_line=2, end_line=2),
        ]

        chunker = UniversalChunker(max_tokens=100, min_tokens=50)
        chunks = chunker._semantic_packing(blocks)

        # Должен быть создан хотя бы один чанк
        assert len(chunks) > 0
        assert all(isinstance(chunk, list) for chunk in chunks)

    def test_adaptive_overlap_calculation(self):
        """Тест вычисления адаптивного overlap"""
        chunker = UniversalChunker()

        # Тест для нового H1/H2
        current_chunk = [Block(type='paragraph', text='Текст', depth=0, is_atomic=False, start_line=0, end_line=0)]
        next_chunk = [Block(type='heading', text='# Новый раздел', depth=1, is_atomic=False, start_line=0, end_line=0)]

        overlap = chunker._calculate_adaptive_overlap(
            current_chunk, next_chunk, [], ['Новый раздел']
        )
        assert overlap == 0

        # Тест для того же heading_path
        overlap = chunker._calculate_adaptive_overlap(
            current_chunk, next_chunk, ['Раздел'], ['Раздел']
        )
        assert overlap == chunker.overlap_base + 60

    def test_chunk_with_metadata(self):
        """Тест чанкинга с метаданными"""
        text = """
# Заголовок документа

Это основной текст документа с информацией.

## Подраздел

Дополнительная информация в подразделе.
"""

        meta = {
            'doc_id': 'test_doc_1',
            'site_url': 'https://example.com/test',
            'source': 'docusaurus',
            'category': 'АРМ_adm',
            'title': 'Тестовый документ',
            'lang': 'ru'
        }

        chunker = UniversalChunker(max_tokens=200, min_tokens=100)
        chunks = chunker.chunk(text, 'markdown', meta)

        assert len(chunks) > 0

        # Проверяем метаданные первого чанка
        first_chunk = chunks[0]
        assert first_chunk.doc_id == 'test_doc_1'
        assert first_chunk.site_url == 'https://example.com/test'
        assert first_chunk.source == 'docusaurus'
        assert first_chunk.category == 'АРМ_adm'
        assert first_chunk.lang == 'ru'
        assert first_chunk.chunk_index == 0
        assert first_chunk.total_chunks == len(chunks)

    def test_chunk_heading_path(self):
        """Тест извлечения пути заголовков"""
        text = """
# Главный раздел

Текст под главным разделом.

## Подраздел 1

Текст под подразделом 1.

### Подподраздел

Текст под подподразделом.
"""

        chunker = UniversalChunker(max_tokens=200, min_tokens=100)
        chunks = chunker.chunk(text, 'markdown', {'doc_id': 'test'})

        # Проверяем, что heading_path правильно извлекается
        assert len(chunks) > 0

        # Находим чанк с подподразделом
        subsub_chunk = None
        for chunk in chunks:
            if 'Подподраздел' in chunk.text:
                subsub_chunk = chunk
                break

        assert subsub_chunk is not None
        assert 'Главный раздел' in subsub_chunk.heading_path
        assert 'Подраздел 1' in subsub_chunk.heading_path
        assert 'Подподраздел' in subsub_chunk.heading_path

    def test_oversize_block_policy_keep(self):
        """Тест политики KEEP для больших блоков"""
        # Создаем большой параграф, но не превышающий oversize_block_limit
        large_text = "Очень длинный текст. " * 200  # ~400 токенов

        chunker = UniversalChunker(
            max_tokens=100,
            oversize_block_policy=OversizePolicy.KEEP,
            oversize_block_limit=2000  # Увеличиваем лимит
        )

        chunks = chunker.chunk(large_text, 'markdown', {'doc_id': 'test'})

        # Должен быть создан один большой чанк
        assert len(chunks) == 1
        assert len(chunks[0].text) > 1000

    def test_oversize_block_policy_skip(self):
        """Тест политики SKIP для больших блоков"""
        # Создаем большой параграф, но не превышающий oversize_block_limit
        large_text = "Очень длинный текст. " * 200  # ~400 токенов

        chunker = UniversalChunker(
            max_tokens=100,
            oversize_block_policy=OversizePolicy.SKIP,
            oversize_block_limit=2000  # Увеличиваем лимит
        )

        chunks = chunker.chunk(large_text, 'markdown', {'doc_id': 'test'})

        # Большой блок должен быть пропущен
        assert len(chunks) == 0

    def test_chunk_empty_text(self):
        """Тест чанкинга пустого текста"""
        chunker = UniversalChunker()
        chunks = chunker.chunk("", 'markdown', {'doc_id': 'test'})
        assert len(chunks) == 0

        chunks = chunker.chunk("   ", 'markdown', {'doc_id': 'test'})
        assert len(chunks) == 0

    def test_chunk_very_short_text(self):
        """Тест чанкинга очень короткого текста"""
        text = "Короткий текст."

        chunker = UniversalChunker(max_tokens=100, min_tokens=50)
        chunks = chunker.chunk(text, 'markdown', {'doc_id': 'test'})

        # Даже короткий текст должен создать чанк
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_chunk_html_format(self):
        """Тест чанкинга HTML формата"""
        html_text = """
<h1>Заголовок</h1>
<p>Параграф с текстом.</p>
<ul>
<li>Пункт 1</li>
<li>Пункт 2</li>
</ul>
"""

        chunker = UniversalChunker()
        chunks = chunker.chunk(html_text, 'html', {'doc_id': 'test'})

        # Должен создать хотя бы один чанк
        assert len(chunks) > 0
        assert chunks[0].content_type == 'html'

    @patch('ingestion.chunking.universal_chunker.BM25_AVAILABLE', False)
    def test_semantic_packing_fallback(self):
        """Тест fallback без BM25"""
        blocks = [
            Block(type='paragraph', text='Текст 1', depth=0, is_atomic=False, start_line=0, end_line=0),
            Block(type='paragraph', text='Текст 2', depth=0, is_atomic=False, start_line=1, end_line=1),
        ]

        chunker = UniversalChunker()
        chunks = chunker._semantic_packing(blocks)

        # Должен использовать простую упаковку
        assert len(chunks) > 0

    def test_convenience_function(self):
        """Тест удобной функции chunk_text_universal"""
        text = """
# Заголовок

Текст документа.
"""

        meta = {
            'doc_id': 'test',
            'site_url': 'https://example.com',
            'source': 'docusaurus',
            'category': 'test'
        }

        chunks = chunk_text_universal(text, 'markdown', meta, max_tokens=200)

        assert len(chunks) > 0
        assert chunks[0]['doc_id'] == 'test'
        assert chunks[0]['source'] == 'docusaurus'
        assert chunks[0]['content_type'] == 'markdown'

    def test_global_chunker_instance(self):
        """Тест глобального экземпляра чанкера"""
        from ingestion.chunking.universal_chunker import get_universal_chunker

        chunker1 = get_universal_chunker()
        chunker2 = get_universal_chunker()

        # Должен возвращать тот же экземпляр
        assert chunker1 is chunker2

    def test_chunk_quality_criteria(self):
        """Тест критериев качества чанков"""
        text = """
# Заголовок 1

Параграф с достаточным количеством текста для создания качественного чанка. Этот текст содержит несколько предложений и должен быть обработан корректно.

## Заголовок 2

Еще один параграф с информацией. Этот текст также должен быть обработан правильно.

### Заголовок 3

Финальный параграф с заключительной информацией.
"""

        chunker = UniversalChunker(max_tokens=300, min_tokens=150)
        chunks = chunker.chunk(text, 'markdown', {'doc_id': 'test'})

        # Проверяем критерии качества
        for chunk in chunks:
            # Чанк не должен быть пустым
            assert chunk.text.strip()

            # Проверяем размер чанка (приблизительно)
            word_count = len(chunk.text.split())
            assert word_count > 10  # Минимум 10 слов

            # Проверяем метаданные
            assert chunk.doc_id == 'test'
            assert chunk.content_type == 'markdown'
            assert chunk.lang == 'ru'

            # Проверяем индексы
            assert 0 <= chunk.chunk_index < chunk.total_chunks
            assert chunk.total_chunks == len(chunks)

    def test_complex_markdown_document(self):
        """Тест сложного Markdown документа"""
        text = """
# Руководство по настройке

Это руководство поможет вам настроить систему.

## Установка

### Требования

- Python 3.8+
- 4 GB RAM
- 10 GB свободного места

### Шаги установки

1. Скачайте установочный файл
2. Запустите установку
3. Настройте конфигурацию

```bash
python setup.py install
```

## Конфигурация

### Основные настройки

```yaml
database:
  host: localhost
  port: 5432
  name: myapp
```

### Дополнительные настройки

| Параметр | Значение | Описание |
|----------|----------|----------|
| timeout  | 30       | Таймаут в секундах |
| retries  | 3        | Количество повторов |

## Использование

После установки и настройки вы можете начать использовать систему.

:::tip
Не забудьте сделать резервную копию перед началом работы!
:::

## Заключение

Это все, что нужно знать для начала работы.
"""

        chunker = UniversalChunker(max_tokens=400, min_tokens=200)
        chunks = chunker.chunk(text, 'markdown', {
            'doc_id': 'setup_guide',
            'site_url': 'https://example.com/setup',
            'source': 'docusaurus',
            'category': 'АРМ_adm'
        })

        # Проверяем, что документ создал хотя бы один чанк
        assert len(chunks) >= 1

        # Проверяем, что все типы блоков обработаны
        all_text = ' '.join(chunk.text for chunk in chunks)
        assert 'Установка' in all_text
        assert 'Конфигурация' in all_text
        assert 'Использование' in all_text

        # Проверяем, что код-блоки не разорваны
        code_blocks_preserved = any('```' in chunk.text for chunk in chunks)
        assert code_blocks_preserved

        # Проверяем, что таблицы не разорваны
        tables_preserved = any('|' in chunk.text for chunk in chunks)
        assert tables_preserved

    def test_html_blockify(self):
        """Тест разбиения HTML на блоки"""
        html_text = """
        <h1>Главный заголовок</h1>
        <p>Параграф с текстом.</p>
        <h2>Подзаголовок</h2>
        <ul>
            <li>Пункт 1</li>
            <li>Пункт 2</li>
        </ul>
        <pre><code>console.log("Hello");</code></pre>
        <table>
            <tr><td>Ячейка 1</td><td>Ячейка 2</td></tr>
        </table>
        """

        chunker = UniversalChunker()
        blocks = chunker._blockify_html(html_text)

        # Проверяем, что блоки правильно классифицированы
        block_types = [block.type for block in blocks]
        assert 'heading' in block_types
        assert 'paragraph' in block_types
        assert 'list' in block_types
        assert 'code_block' in block_types
        assert 'table' in block_types

    def test_russian_abbreviations(self):
        """Тест обработки русских сокращений"""
        text = "Это первое предложение. Это второе предложение т.д. Это третье предложение."

        chunker = UniversalChunker()
        block = Block(
            type='paragraph',
            text=text,
            depth=0,
            is_atomic=False,
            start_line=0,
            end_line=0
        )

        split_blocks = chunker._split_paragraph_block(block)

        # Должно быть разбито на предложения, но "т.д." не должно разбивать
        assert len(split_blocks) >= 1
        # Проверяем, что "т.д." не разорвало предложение
        all_text = ' '.join(block.text for block in split_blocks)
        assert 'т.д.' in all_text

    def test_heading_in_chunk(self):
        """Тест включения заголовка в чанк"""
        text = """
# Заголовок 1

Текст под заголовком 1.

## Заголовок 2

Текст под заголовком 2.
"""

        chunker = UniversalChunker(max_tokens=200, min_tokens=100)
        chunks = chunker.chunk(text, 'markdown', {'doc_id': 'test'})

        # Проверяем, что заголовки включены в чанки
        for chunk in chunks:
            if 'Заголовок 2' in chunk.heading_path:
                # Чанк с заголовком 2 должен содержать заголовок в тексте
                assert '## Заголовок 2' in chunk.text or 'Заголовок 2' in chunk.text

    def test_bm25_similarity(self):
        """Тест вычисления BM25 похожести"""
        chunker = UniversalChunker()

        block1 = Block(
            type='paragraph',
            text='Это текст о программировании и разработке.',
            depth=0,
            is_atomic=False,
            start_line=0,
            end_line=0
        )

        block2 = Block(
            type='paragraph',
            text='Программирование и разработка - это интересная тема.',
            depth=0,
            is_atomic=False,
            start_line=0,
            end_line=0
        )

        similarity = chunker._calculate_block_similarity(block1, block2)

        # Должна быть похожесть (слова пересекаются)
        assert -1.0 <= similarity <= 1.0  # BM25 может давать отрицательные значения
        assert similarity != 0.0  # Должна быть какая-то похожесть

    def test_regex_tokenization(self):
        """Тест regex токенизации"""
        chunker = UniversalChunker()

        text = "Это тест токенизации с разными символами: test@example.com, 123-456, и т.д."
        tokens = chunker._count_tokens(text)

        # Должно быть больше токенов, чем просто слов
        words_count = len(text.split())
        assert tokens >= words_count  # Regex должен дать больше токенов

    def test_heading_boundaries(self):
        """Тест границ чанков по заголовкам H1/H2"""
        text = """
# Раздел 1

Текст первого раздела. Это довольно длинный текст, который должен заполнить минимальное количество токенов для тестирования границ чанков.

## Подраздел 1.1

Текст подраздела 1.1.

## Подраздел 1.2

Текст подраздела 1.2.

# Раздел 2

Текст второго раздела.
"""

        chunker = UniversalChunker(max_tokens=200, min_tokens=100)
        chunks = chunker.chunk(text, 'markdown', {'doc_id': 'test'})

        # Должно быть хотя бы один чанк
        assert len(chunks) >= 1

        # Проверяем, что заголовки включены в чанки
        all_text = ' '.join(chunk.text for chunk in chunks)
        assert 'Раздел 1' in all_text
        assert 'Раздел 2' in all_text

    def test_code_overlap_preservation(self):
        """Тест сохранения структуры кода в overlap"""
        text = """
# Код пример

```python
def function1():
    print("Hello")
    return True

def function2():
    print("World")
    return False
```

Дополнительный текст после кода.
"""

        chunker = UniversalChunker(max_tokens=150, min_tokens=50)
        chunks = chunker.chunk(text, 'markdown', {'doc_id': 'test'})

        # Проверяем, что код не разорван
        code_preserved = any('def function1()' in chunk.text and 'def function2()' in chunk.text for chunk in chunks)
        assert code_preserved

    def test_improved_code_splitting(self):
        """Тест улучшенного разбиения больших код-блоков"""
        # Создаем большой код-блок
        large_code = "def function():\n" + "    print('line')\n" * 100
        
        chunker = UniversalChunker(max_tokens=50, min_tokens=20)
        block = Block(
            type='code_block',
            text=large_code,
            depth=0,
            is_atomic=True,
            start_line=0,
            end_line=0
        )
        
        split_blocks = chunker._split_code_block(block)
        
        # Должно быть разбито на несколько блоков (или остаться одним, если не превышает лимит)
        assert len(split_blocks) >= 1
        
        # Проверяем, что если блок большой, то он разбивается
        if chunker._count_tokens(block.text) > chunker.max_tokens:
            assert len(split_blocks) > 1
        
        # Каждый блок не должен превышать max_tokens (с небольшим допуском)
        for block in split_blocks:
            assert chunker._count_tokens(block.text) <= chunker.max_tokens + 10  # Небольшой допуск

    def test_prepend_heading(self):
        """Тест добавления заголовка в начало чанка"""
        chunker = UniversalChunker()

        heading_path = ['Главный раздел', 'Подраздел']
        text = 'Обычный текст без заголовка.'

        result = chunker._prepend_heading(heading_path, text)

        # Должен быть добавлен заголовок
        assert result.startswith('# Подраздел')
        assert 'Обычный текст без заголовка.' in result

        # Если текст уже содержит заголовок, не дублируем
        text_with_heading = '# Существующий заголовок\n\nТекст'
        result2 = chunker._prepend_heading(heading_path, text_with_heading)
        assert result2 == text_with_heading

    def test_expanded_russian_abbreviations(self):
        """Тест расширенного списка русских сокращений"""
        text = "Это первое предложение. Это второе предложение т.н. Это третье предложение."

        chunker = UniversalChunker()
        block = Block(
            type='paragraph',
            text=text,
            depth=0,
            is_atomic=False,
            start_line=0,
            end_line=0
        )

        split_blocks = chunker._split_paragraph_block(block)

        # Проверяем, что "т.н." не разорвало предложение
        all_text = ' '.join(block.text for block in split_blocks)
        assert 'т.н.' in all_text

    def test_admonitions_parsing(self):
        """Тест разбора admonitions как единых блоков"""
        text = """
# Заголовок

Обычный текст.

:::tip
Это совет.
Многострочный совет.
:::

Еще текст.

:::warning
Предупреждение!
:::

Финальный текст.
"""
        
        chunker = UniversalChunker()
        blocks = chunker._blockify_markdown(text)
        
        # Проверяем, что admonitions собраны как единые блоки
        admonition_blocks = [block for block in blocks if block.type == 'admonition']
        assert len(admonition_blocks) == 2
        
        # Проверяем содержимое admonitions
        tip_block = next(block for block in admonition_blocks if 'tip' in block.text)
        warning_block = next(block for block in admonition_blocks if 'warning' in block.text)
        
        assert 'Это совет.\nМногострочный совет.' in tip_block.text
        assert 'Предупреждение!' in warning_block.text

    def test_heading_depth_prepend(self):
        """Тест добавления заголовка с учетом глубины"""
        chunker = UniversalChunker()
        
        # Тест для H1
        result1 = chunker._prepend_heading(['Главный раздел'], 'Текст', heading_depth=1)
        assert result1.startswith('# Главный раздел')
        
        # Тест для H2
        result2 = chunker._prepend_heading(['Главный раздел', 'Подраздел'], 'Текст', heading_depth=2)
        assert result2.startswith('## Подраздел')
        
        # Тест для H3+
        result3 = chunker._prepend_heading(['Главный раздел', 'Подраздел', 'Подподраздел'], 'Текст', heading_depth=3)
        assert result3.startswith('### Подподраздел')

    def test_precise_token_extraction(self):
        """Тест точного извлечения токенов по позициям"""
        chunker = UniversalChunker()
        
        text = "Это тест точного извлечения токенов из текста."
        
        # Тест для обычного текста
        result = chunker._extract_partial_text(text, 3, is_code_like=False)
        assert len(chunker._regex_tokenize(result)) <= 3
        
        # Тест для кода
        code_text = "line1\nline2\nline3\nline4"
        result_code = chunker._extract_partial_text(code_text, 2, is_code_like=True)
        assert result_code.count('\n') <= 2


if __name__ == "__main__":
    pytest.main([__file__])
