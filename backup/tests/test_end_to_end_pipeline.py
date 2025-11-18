#!/usr/bin/env python3
"""
End-to-end тесты pipeline для автотестов
"""

import pytest
import time
from pathlib import Path
import sys

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

# Import data sources first to register them
from app.sources import edna_docs_source

from app.abstractions.data_source import plugin_manager
from app.services.indexing.optimized_pipeline import OptimizedPipeline, run_optimized_indexing
from app.services.indexing.metadata_aware_indexer import MetadataAwareIndexer
from ingestion.chunkers import chunk_text
from app.config import CONFIG


class TestEndToEndPipeline:
    """Тесты полного pipeline от извлечения до записи в Qdrant"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Настройка для каждого теста"""
        self.test_marker = f"test_run_{int(time.time())}"

    def test_single_document_extraction_and_chunking(self):
        """Тест извлечения и chunking одного документа"""
        # Шаг 1: Извлечение документа
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": False,
            "max_pages": 1
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        crawl_result = source.fetch_pages(max_pages=1)

        # Проверяем, что документ извлечен
        assert crawl_result.pages, "Документ не извлечен"

        page = crawl_result.pages[0]
        assert len(page.content) > 0, "Контент документа пустой"
        assert page.title, "Заголовок документа пустой"
        assert page.url, "URL документа пустой"

        # Шаг 2: Chunking
        chunks = chunk_text(page.content)
        assert len(chunks) > 0, "Чанки не сгенерированы"

        # Проверяем качество чанков
        total_chars = sum(len(chunk) for chunk in chunks)
        avg_chars = total_chars / len(chunks)

        # Чанки не должны быть слишком короткими или длинными
        # Для fallback chunker допускаем больший размер
        assert 50 <= avg_chars <= 10000, f"Средняя длина чанка {avg_chars} не оптимальна"

    def test_adaptive_chunking_strategies(self):
        """Тест адаптивных стратегий chunking"""
        # Получаем документ
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": False,
            "max_pages": 1
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        crawl_result = source.fetch_pages(max_pages=1)

        if not crawl_result.pages or len(crawl_result.pages[0].content) == 0:
            pytest.skip("Не удалось получить документ с контентом")

        page = crawl_result.pages[0]
        pipeline = OptimizedPipeline()

        # Тестируем адаптивный chunking
        adaptive_chunks = pipeline._adaptive_chunk_page(page)
        assert len(adaptive_chunks) > 0, "Адаптивный chunking не работает"

        # Тестируем стандартный chunking
        standard_chunks = pipeline._standard_chunk_page(page)
        assert len(standard_chunks) > 0, "Стандартный chunking не работает"

        # Проверяем, что чанки содержат необходимые поля
        for chunk in adaptive_chunks[:2]:
            assert 'text' in chunk, "Чанк не содержит текст"
            assert 'payload' in chunk, "Чанк не содержит payload"
            assert 'url' in chunk['payload'], "Payload не содержит URL"
            assert 'title' in chunk['payload'], "Payload не содержит заголовок"

    @pytest.mark.slow
    def test_full_pipeline_indexing(self):
        """Тест полного pipeline с индексацией (медленный тест)"""
        # Запускаем полный pipeline
        result = run_optimized_indexing(
            source_name="edna_docs",
            max_pages=2,  # Небольшое количество для теста
            chunk_strategy="adaptive"
        )

        # Проверяем успешность
        assert result['success'], f"Pipeline не выполнился успешно: {result.get('error', 'Unknown error')}"
        assert result.get('pages', 0) > 0, "Не обработано ни одной страницы"
        assert result.get('chunks', 0) > 0, "Не проиндексировано ни одного чанка"
        assert result.get('duration', 0) > 0, "Время выполнения не зафиксировано"

    def test_metadata_aware_indexing(self):
        """Тест индексации с enhanced metadata"""
        # Создаем тестовый чанк
        test_chunk = {
            "text": "Это тестовый текст для проверки enhanced metadata indexing. " * 10,
            "payload": {
                "url": "https://test.com/test",
                "title": "Test Document",
                "page_type": "guide",
                "source": "test",
                "language": "ru",
                "chunk_index": 0,
                "content_length": 500,
                "test_marker": self.test_marker
            }
        }

        # Индексируем
        indexer = MetadataAwareIndexer()
        indexed_count = indexer.index_chunks_with_metadata([test_chunk])

        assert indexed_count == 1, "Чанк не проиндексирован"

        # Проверяем запись в Qdrant
        from app.retrieval.retrieval import client, COLLECTION

        # Ищем по URL, который должен быть уникальным
        search_result = client.scroll(
            collection_name=COLLECTION,
            scroll_filter={"must": [{"key": "url", "match": {"value": "https://test.com/test"}}]},
            limit=1,
            with_payload=True,
            with_vectors=False
        )

        found_chunks = search_result[0]
        assert len(found_chunks) == 1, f"Тестовый чанк не найден в Qdrant. Найдено: {len(found_chunks)}"

        # Проверяем enhanced metadata
        payload = found_chunks[0].payload
        assert 'complexity_score' in payload, "Enhanced metadata не добавлено"
        assert 'semantic_density' in payload, "Semantic density не добавлено"
        assert 'boost_factor' in payload, "Boost factor не добавлено"

        # Очищаем тестовые данные
        client.delete(
            collection_name=COLLECTION,
            points_selector=[str(found_chunks[0].id)]
        )

    def test_config_validation(self):
        """Тест валидации конфигурации"""
        # Проверяем, что конфигурация валидна
        assert CONFIG.chunk_min_tokens < CONFIG.chunk_max_tokens, "Некорректные настройки chunking"
        assert CONFIG.chunk_min_tokens > 0, "chunk_min_tokens должен быть положительным"
        assert CONFIG.chunk_max_tokens > 0, "chunk_max_tokens должен быть положительным"
        assert CONFIG.embedding_max_length_doc > 0, "embedding_max_length_doc должен быть положительным"
        assert CONFIG.crawler_strategy in ["jina", "http", "browser"], "Некорректная стратегия crawler"

    def test_plugin_manager(self):
        """Тест системы плагинов"""
        # Проверяем, что источники данных зарегистрированы
        sources = plugin_manager.list_sources()
        assert "edna_docs" in sources, "Источник edna_docs не зарегистрирован"

        # Проверяем создание источника
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": True
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        assert source is not None, "Не удалось создать источник edna_docs"
        assert source.get_source_name() == "edna-docs", "Некорректное имя источника"

    def test_chunking_quality_metrics(self):
        """Тест метрик качества chunking"""
        # Получаем документ
        edna_config = {
            "base_url": "https://docs-chatcenter.edna.ru/",
            "strategy": "jina",
            "use_cache": False,
            "max_pages": 1
        }

        source = plugin_manager.get_source("edna_docs", edna_config)
        crawl_result = source.fetch_pages(max_pages=1)

        if not crawl_result.pages or len(crawl_result.pages[0].content) == 0:
            pytest.skip("Не удалось получить документ с контентом")

        page = crawl_result.pages[0]
        chunks = chunk_text(page.content)

        # Проверяем метрики качества
        assert len(chunks) > 0, "Не сгенерировано чанков"

        # Проверяем, что чанки не пустые
        for chunk in chunks:
            assert len(chunk.strip()) > 0, "Обнаружен пустой чанк"

        # Проверяем, что общая длина текста сохранена
        original_length = len(page.content)
        chunked_length = sum(len(chunk) for chunk in chunks)

        # Допускаем потерю из-за обработки (HTML парсинг может терять много текста)
        assert chunked_length >= original_length * 0.25, f"Слишком большая потеря текста при chunking: {chunked_length} < {original_length * 0.25}"

    @pytest.mark.integration
    def test_connection_pool(self):
        """Тест connection pooling"""
        from app.services.infrastructure.connection_pool import get_connection_pool, close_connection_pool

        # Получаем pool
        pool = get_connection_pool()

        # Проверяем статистику
        stats = pool.get_stats()
        assert 'active_sessions' in stats, "Статистика pool не содержит active_sessions"
        assert 'max_sessions' in stats, "Статистика pool не содержит max_sessions"
        assert stats['max_sessions'] > 0, "Максимальное количество сессий должно быть положительным"

        # Очищаем pool
        close_connection_pool()

    @pytest.mark.slow
    def test_optimized_pipeline_end_to_end(self):
        """Тест оптимизированного pipeline end-to-end"""
        print("🚀 ТЕСТ ОПТИМИЗИРОВАННОГО PIPELINE END-TO-END")
        print("=" * 60)

        try:
            # Используем run_optimized_indexing для полного теста
            result = run_optimized_indexing(
                source_name="edna_docs",
                max_pages=2,  # Ограничиваем для теста
                chunk_strategy="adaptive"
            )

            # Проверяем результат
            assert result["success"], f"Оптимизированная индексация не удалась: {result.get('error', 'Unknown error')}"
            assert result["pages"] > 0, "Не было обработано ни одной страницы"
            assert result["chunks"] > 0, "Не было создано ни одного чанка"

            print(f"✅ Оптимизированная индексация завершена:")
            print(f"   Страниц: {result['pages']}")
            print(f"   Чанков: {result['chunks']}")
            print(f"   Время: {result.get('duration', 'N/A')}s")

        except Exception as e:
            print(f"❌ Ошибка в оптимизированном pipeline: {e}")
            raise

    def test_chunking_quality_analysis(self):
        """Тест анализа качества chunking"""
        print("🔍 ТЕСТ АНАЛИЗА КАЧЕСТВА CHUNKING")
        print("=" * 60)

        try:
            # Получаем документ для анализа
            edna_config = {
                "base_url": "https://docs-chatcenter.edna.ru/",
                "strategy": "jina",
                "use_cache": False,
                "max_pages": 1
            }

            source = plugin_manager.get_source("edna_docs", edna_config)
            crawl_result = source.fetch_pages(max_pages=1)

            assert crawl_result.pages, "Не удалось получить документ"

            page = crawl_result.pages[0]
            print(f"📄 Анализируем chunking для: {page.title}")
            print(f"   Длина контента: {len(page.content)} символов")

            # Тестируем разные стратегии chunking
            strategies = ["adaptive", "standard"]
            pipeline = OptimizedPipeline()

            for strategy in strategies:
                print(f"\n🔧 Стратегия: {strategy}")

                if strategy == "adaptive":
                    chunks = pipeline._adaptive_chunk_page(page)
                else:
                    chunks = pipeline._standard_chunk_page(page)

                print(f"   Чанков: {len(chunks)}")

                if chunks:
                    total_chars = sum(len(chunk['text']) for chunk in chunks)
                    avg_chars = total_chars / len(chunks)

                    print(f"   Общая длина: {total_chars} символов")
                    print(f"   Средняя длина чанка: {avg_chars:.0f} символов")

                    # Проверяем качество chunking
                    assert len(chunks) > 0, f"Стратегия {strategy} не создала чанков"
                    assert avg_chars > 50, f"Слишком короткие чанки для стратегии {strategy}"
                    assert avg_chars < 2000, f"Слишком длинные чанки для стратегии {strategy}"

                    print(f"   ✅ Качество chunking: OK")
                else:
                    print(f"   ❌ Стратегия {strategy} не создала чанков")

            print("✅ Анализ качества chunking завершен")

        except Exception as e:
            print(f"❌ Ошибка в анализе качества chunking: {e}")
            raise


# Конфигурация pytest
def pytest_configure(config):
    """Конфигурация pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


def pytest_collection_modifyitems(config, items):
    """Модификация тестов для добавления маркеров"""
    for item in items:
        # Помечаем медленные тесты
        if "full_pipeline" in item.name or "indexing" in item.name:
            item.add_marker(pytest.mark.slow)

        # Помечаем интеграционные тесты
        if "connection_pool" in item.name or "metadata_aware" in item.name:
            item.add_marker(pytest.mark.integration)
