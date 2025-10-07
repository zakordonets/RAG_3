import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from ingestion.indexer import create_payload_indexes, upsert_chunks
from ingestion.run import run_docusaurus_indexing


def test_create_payload_indexes():
    """Тест создания индексов payload"""
    with patch('ingestion.indexer.client') as mock_client:
        mock_client.create_payload_index.return_value = None

        # Тест создания индексов
        create_payload_indexes("test_collection")

        # Проверяем, что были вызваны методы создания индексов
        assert mock_client.create_payload_index.call_count >= 5  # Минимум 5 индексов

        # Проверяем, что были созданы индексы для ключевых полей
        called_fields = [call[1]['field_name'] for call in mock_client.create_payload_index.call_args_list]
        assert "category" in called_fields
        assert "groups_path" in called_fields
        assert "title" in called_fields
        assert "source" in called_fields
        assert "content_type" in called_fields


def test_upsert_chunks_with_chunk_id():
    """Тест upsert_chunks с использованием chunk_id из payload"""
    with patch('ingestion.indexer.client') as mock_client, \
         patch('ingestion.indexer.embed_batch_optimized') as mock_embed:

        # Настраиваем моки
        mock_client.upsert.return_value = None
        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024, [0.2] * 1024],
            'lexical_weights': [{}, {}]
        }

        # Создаем тестовые чанки с chunk_id
        chunks = [
            {
                "text": "Тестовый текст 1",
                "payload": {
                    "chunk_id": "doc1#0",
                    "title": "Тест 1",
                    "category": "АРМ_adm",
                    "source": "docusaurus"
                }
            },
            {
                "text": "Тестовый текст 2",
                "payload": {
                    "chunk_id": "doc1#1",
                    "title": "Тест 2",
                    "category": "АРМ_adm",
                    "source": "docusaurus"
                }
            }
        ]

        # Вызываем функцию
        result = upsert_chunks(chunks)

        # Проверяем результат
        assert result == 2
        mock_client.upsert.assert_called_once()

        # Проверяем, что были переданы правильные ID
        call_args = mock_client.upsert.call_args
        points = call_args[1]['points']
        assert len(points) == 2
        assert points[0].id == "doc1#0"
        assert points[1].id == "doc1#1"


def test_upsert_chunks_fallback_id():
    """Тест upsert_chunks с fallback ID когда нет chunk_id"""
    with patch('ingestion.indexer.client') as mock_client, \
         patch('ingestion.indexer.embed_batch_optimized') as mock_embed, \
         patch('ingestion.indexer.text_hash') as mock_hash, \
         patch('ingestion.indexer.uuid') as mock_uuid:

        # Настраиваем моки
        mock_client.upsert.return_value = None
        mock_embed.return_value = {
            'dense_vecs': [[0.1] * 1024],
            'lexical_weights': [{}]
        }
        mock_hash.return_value = "test_hash_123456789012345678901234567890123456789012345678901234567890"
        mock_uuid.UUID.return_value = "fallback-uuid-123"

        # Создаем тестовый чанк без chunk_id
        chunks = [
            {
                "text": "Тестовый текст",
                "payload": {
                    "title": "Тест",
                    "category": "АРМ_adm"
                }
            }
        ]

        # Вызываем функцию
        result = upsert_chunks(chunks)

        # Проверяем результат
        assert result == 1
        mock_client.upsert.assert_called_once()

        # Проверяем, что был использован fallback ID
        call_args = mock_client.upsert.call_args
        points = call_args[1]['points']
        assert len(points) == 1
        assert points[0].id == "fallback-uuid-123"


def test_run_docusaurus_indexing_basic():
    """Базовый тест индексации Docusaurus"""
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
        md_file.write_text("""---
title: "Админ виджет"
category: "АРМ_adm"
---

# Админ виджет

Описание функций админ виджета.

## Функции

- Функция 1
- Функция 2

<ContentRef url="/docs/admin/user">Пользователи</ContentRef>
""", encoding="utf-8")

        with patch('ingestion.run.upsert_chunks') as mock_upsert, \
             patch('ingestion.run.create_payload_indexes') as mock_indexes:

            # Настраиваем моки
            mock_upsert.return_value = 3  # 3 чанка
            mock_indexes.return_value = None

            # Запускаем индексацию
            result = run_docusaurus_indexing(
                docs_root=str(temp_path),
                site_base_url="https://test.com",
                collection_name="test_collection"
            )

            # Проверяем результат
            assert result["success"] is True
            assert result["files_processed"] == 1
            assert result["total_files"] == 1
            assert result["chunks_indexed"] == 3

            # Проверяем, что были вызваны нужные функции
            mock_indexes.assert_called_once_with("test_collection")
            mock_upsert.assert_called_once()


def test_run_docusaurus_indexing_category_filter():
    """Тест индексации с фильтром по категории"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем структуру документации
        admin_dir = temp_path / "40-admin"
        admin_dir.mkdir()

        # Создаем два файла с разными категориями
        file1 = admin_dir / "admin-file.md"
        file1.write_text("""---
title: "Админ файл"
category: "АРМ_adm"
---

# Админ файл

Содержимое админ файла.
""", encoding="utf-8")

        file2 = admin_dir / "sv-file.md"
        file2.write_text("""---
title: "SV файл"
category: "АРМ_sv"
---

# SV файл

Содержимое SV файла.
""", encoding="utf-8")

        with patch('ingestion.run.upsert_chunks') as mock_upsert, \
             patch('ingestion.run.create_payload_indexes') as mock_indexes:

            # Настраиваем моки
            mock_upsert.return_value = 1  # 1 чанк (только админ файл)
            mock_indexes.return_value = None

            # Запускаем индексацию с фильтром по категории
            result = run_docusaurus_indexing(
                docs_root=str(temp_path),
                site_base_url="https://test.com",
                collection_name="test_collection",
                category_filter="АРМ_adm"
            )

            # Проверяем результат
            assert result["success"] is True
            assert result["files_processed"] == 1  # Только один файл прошел фильтр
            assert result["total_files"] == 2  # Всего файлов было 2
            assert result["chunks_indexed"] == 1


def test_run_docusaurus_indexing_no_files():
    """Тест индексации когда нет файлов"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Создаем пустую директорию
        empty_dir = temp_path / "empty"
        empty_dir.mkdir()

        with patch('ingestion.run.create_payload_indexes') as mock_indexes:
            mock_indexes.return_value = None

            # Запускаем индексацию
            result = run_docusaurus_indexing(
                docs_root=str(temp_path),
                site_base_url="https://test.com",
                collection_name="test_collection"
            )

            # Проверяем результат
            assert result["success"] is False
            assert result["files_processed"] == 0
            assert result["total_files"] == 0
            assert result["chunks_indexed"] == 0
            assert "Нет чанков для индексации" in result["error"]


def test_run_docusaurus_indexing_invalid_path():
    """Тест индексации с несуществующим путем"""
    with patch('ingestion.run.create_payload_indexes') as mock_indexes:
        mock_indexes.return_value = None

        # Запускаем индексацию с несуществующим путем
        try:
            result = run_docusaurus_indexing(
                docs_root="/nonexistent/path",
                site_base_url="https://test.com",
                collection_name="test_collection"
            )
            assert False, "Должно было быть исключение"
        except ValueError as e:
            assert "не существует" in str(e)
