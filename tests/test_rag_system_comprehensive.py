#!/usr/bin/env python3
"""
Комплексный тест RAG системы с проверкой всех компонентов
"""
import pytest
import sys
import os
from typing import Dict, List, Any

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.bge_embeddings import embed_unified, embed_dense, embed_sparse_optimized
from app.services.retrieval import hybrid_search
from app.services.metadata_aware_indexer import MetadataAwareIndexer
from app.config import CONFIG


class TestRAGSystemComprehensive:
    """Комплексное тестирование RAG системы"""

    @pytest.fixture(autouse=True)
    def setup_encoding(self):
        """Настройка кодировки для тестов"""
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'

    def test_embedding_generation_dense(self):
        """Тест генерации dense векторов"""
        test_text = "Как настроить агента в системе?"

        result = embed_dense(text=test_text)

        assert result is not None, "Dense embedding не должен быть None"
        assert isinstance(result, list), "Dense embedding должен быть списком"
        assert len(result) == 1024, f"Dense вектор должен иметь 1024 измерений"

        dense_vector = result
        assert isinstance(dense_vector, list), "Dense вектор должен быть списком"
        assert len(dense_vector) > 0, "Dense вектор не должен быть пустым"
        assert len(dense_vector) == 1024, f"Dense вектор должен иметь 1024 измерений"

        # Проверяем, что вектор не состоит из нулей
        non_zero_count = sum(1 for x in dense_vector if abs(x) > 1e-6)
        assert non_zero_count > 0, "Dense вектор не должен состоять из нулей"

        print(f"✅ Dense вектор: {len(dense_vector)} измерений, {non_zero_count} ненулевых значений")

    def test_embedding_generation_sparse(self):
        """Тест генерации sparse векторов"""
        test_text = "Как настроить агента в системе?"

        result = embed_sparse_optimized(text=test_text)

        assert result is not None, "Sparse embedding не должен быть None"

        # Sparse результат может быть словарем или списком словарей
        if isinstance(result, dict):
            # Если это словарь с индексами и значениями
            assert 'indices' in result, "Sparse результат должен содержать 'indices'"
            assert 'values' in result, "Sparse результат должен содержать 'values'"
            assert len(result['indices']) > 0, "Sparse вектор не должен быть пустым"
            sparse_vector = result
        else:
            # Если это список словарей
            assert isinstance(result, list), "Sparse embedding должен быть списком"
            assert len(result) == 1, "Должен быть один sparse вектор"
            sparse_vector = result[0]
            assert isinstance(sparse_vector, dict), "Sparse вектор должен быть словарем"
            assert len(sparse_vector) > 0, "Sparse вектор не должен быть пустым"

        # Проверяем структуру sparse вектора
        if 'indices' in sparse_vector and 'values' in sparse_vector:
            # Формат с индексами и значениями
            indices = sparse_vector['indices']
            values = sparse_vector['values']
            assert len(indices) == len(values), "Количество индексов должно совпадать с количеством значений"
            assert len(indices) > 0, "Sparse вектор не должен быть пустым"
            print(f"✅ Sparse вектор: {len(indices)} токенов")
        else:
            # Формат словарь токен->вес
            for token, weight in sparse_vector.items():
                assert isinstance(token, (str, int)), "Токены должны быть строками или числами"
                assert isinstance(weight, (int, float)), "Веса должны быть числами"
                assert weight > 0, "Веса должны быть положительными"
            print(f"✅ Sparse вектор: {len(sparse_vector)} токенов")

    def test_embedding_generation_unified(self):
        """Тест генерации unified эмбеддингов"""
        test_text = "Как настроить агента в системе?"

        result = embed_unified(
            text=test_text,
            max_length=512,
            return_dense=True,
            return_sparse=True,
            context="query"
        )

        assert result is not None, "Unified embedding не должен быть None"
        assert isinstance(result, dict), "Unified embedding должен быть словарем"

        # Проверяем dense векторы
        dense_vecs = result.get('dense_vecs')
        assert dense_vecs is not None, "Должны быть dense векторы"
        assert isinstance(dense_vecs, list), "Dense векторы должны быть списком"
        assert len(dense_vecs) == 1, "Должен быть один dense вектор"

        dense_vector = dense_vecs[0]
        assert len(dense_vector) > 0, "Dense вектор не должен быть пустым"

        # Проверяем sparse векторы
        sparse_vecs = result.get('lexical_weights')
        assert sparse_vecs is not None, "Должны быть sparse векторы"
        assert isinstance(sparse_vecs, list), "Sparse векторы должны быть списком"
        assert len(sparse_vecs) == 1, "Должен быть один sparse вектор"

        sparse_vector = sparse_vecs[0]
        assert len(sparse_vector) > 0, "Sparse вектор не должен быть пустым"

        print(f"✅ Unified embedding: dense={len(dense_vector)}D, sparse={len(sparse_vector)} токенов")

    def test_collection_status(self):
        """Тест статуса коллекции Qdrant"""
        indexer = MetadataAwareIndexer()

        # Получаем информацию о коллекции
        info = indexer.client.get_collection(CONFIG.qdrant_collection)

        assert info.status == "green", f"Статус коллекции должен быть green, получен: {info.status}"
        assert info.points_count > 0, "Коллекция должна содержать точки"
        assert info.points_count >= 20, f"Ожидалось минимум 20 точек, получено: {info.points_count}"

        print(f"✅ Коллекция: {info.points_count} точек, статус: {info.status}")

    def test_search_functionality(self):
        """Тест функциональности поиска"""
        test_queries = [
            "Как настроить агента?",
            "Что такое WebSocket?",
            "API для интеграции"
        ]

        for query in test_queries:
            # Генерируем эмбеддинги
            embedding_result = embed_unified(
                text=query,
                max_length=512,
                return_dense=True,
                return_sparse=True,
                context="query"
            )

            dense_vec = embedding_result['dense_vecs'][0]
            sparse_vec = embedding_result['lexical_weights'][0]

            # Выполняем поиск
            results = hybrid_search(
                query_dense=dense_vec,
                query_sparse=sparse_vec,
                k=5
            )

            assert results is not None, f"Результаты поиска не должны быть None для запроса: {query}"
            assert isinstance(results, list), "Результаты должны быть списком"
            assert len(results) > 0, f"Должны быть найдены результаты для запроса: {query}"
            assert len(results) <= 5, "Не должно быть больше 5 результатов"

            # Проверяем структуру результатов
            for i, result in enumerate(results):
                assert isinstance(result, dict), f"Результат {i} должен быть словарем"
                assert 'score' in result, f"Результат {i} должен содержать score"
                assert 'payload' in result, f"Результат {i} должен содержать payload"
                assert 'id' in result, f"Результат {i} должен содержать id"

                score = result['score']
                assert isinstance(score, (int, float)), f"Score должен быть числом в результате {i}"
                assert 0 <= score <= 1, f"Score должен быть между 0 и 1 в результате {i}"

                payload = result['payload']
                assert isinstance(payload, dict), f"Payload должен быть словарем в результате {i}"

                # Проверяем обязательные поля в payload
                assert 'url' in payload, f"Payload должен содержать url в результате {i}"
                assert 'title' in payload, f"Payload должен содержать title в результате {i}"
                assert 'text' in payload, f"Payload должен содержать text в результате {i}"

                url = payload['url']
                title = payload['title']
                text = payload['text']

                assert url is not None and url != "", f"URL не должен быть пустым в результате {i}"
                assert title is not None and title != "", f"Title не должен быть пустым в результате {i}"
                assert text is not None and text != "", f"Text не должен быть пустым в результате {i}"

                assert len(text) > 10, f"Text должен содержать достаточно текста в результате {i}"

                print(f"  ✅ Результат {i+1}: score={score:.3f}, title='{title[:50]}...', text_len={len(text)}")

            print(f"✅ Поиск для '{query}': {len(results)} результатов")

    def test_metadata_completeness(self):
        """Тест полноты метаданных"""
        # Выполняем поиск
        query = "Настройка производительности"
        embedding_result = embed_unified(
            text=query,
            max_length=512,
            return_dense=True,
            return_sparse=True,
            context="query"
        )

        results = hybrid_search(
            query_dense=embedding_result['dense_vecs'][0],
            query_sparse=embedding_result['lexical_weights'][0],
            k=3
        )

        for i, result in enumerate(results):
            payload = result['payload']

            # Проверяем обязательные поля (адаптируем под текущую структуру)
            required_fields = [
                'url', 'title', 'text', 'page_type',
                'chunk_index'
            ]

            for field in required_fields:
                assert field in payload, f"Поле '{field}' отсутствует в результате {i}"
                assert payload[field] is not None, f"Поле '{field}' не должно быть None в результате {i}"
                assert payload[field] != "", f"Поле '{field}' не должно быть пустым в результате {i}"

            # Проверяем типы данных
            assert isinstance(payload['url'], str), f"URL должен быть строкой в результате {i}"
            assert isinstance(payload['title'], str), f"Title должен быть строкой в результате {i}"
            assert isinstance(payload['text'], str), f"Text должен быть строкой в результате {i}"
            assert isinstance(payload['page_type'], str), f"Page type должен быть строкой в результате {i}"
            assert isinstance(payload['chunk_index'], int), f"Chunk index должен быть числом в результате {i}"

            # Проверяем логические ограничения
            assert payload['chunk_index'] >= 0, f"Chunk index должен быть >= 0 в результате {i}"

            print(f"  ✅ Метаданные результата {i+1}: {payload['page_type']}, chunk {payload['chunk_index']}")

        print(f"✅ Все метаданные корректны для {len(results)} результатов")

    def test_russian_text_processing(self):
        """Тест обработки русского текста"""
        russian_queries = [
            "Как настроить агента?",
            "Что такое веб-сокет?",
            "Настройка производительности системы",
            "Аутентификация пользователей"
        ]

        for query in russian_queries:
            # Генерируем эмбеддинги для русского текста
            embedding_result = embed_unified(
                text=query,
                max_length=512,
                return_dense=True,
                return_sparse=True,
                context="query"
            )

            dense_vec = embedding_result['dense_vecs'][0]
            sparse_vec = embedding_result['lexical_weights'][0]

            # Проверяем, что эмбеддинги не пустые
            assert len(dense_vec) > 0, f"Dense вектор пустой для запроса: {query}"
            assert len(sparse_vec) > 0, f"Sparse вектор пустой для запроса: {query}"

            # Выполняем поиск
            results = hybrid_search(
                query_dense=dense_vec,
                query_sparse=sparse_vec,
                k=3
            )

            assert len(results) > 0, f"Нет результатов для русского запроса: {query}"

            # Проверяем, что результаты содержат русский текст
            for result in results:
                payload = result['payload']
                title = payload.get('title', '')
                text = payload.get('text', '')

                # Проверяем наличие русских символов
                has_russian = any('\u0400' <= char <= '\u04FF' for char in title + text)
                assert has_russian, f"Результат должен содержать русский текст для запроса: {query}"

            print(f"✅ Русский запрос '{query}': {len(results)} результатов с русским текстом")

    def test_performance_benchmark(self):
        """Тест производительности системы"""
        import time

        query = "API для интеграции с внешними системами"

        # Измеряем время генерации эмбеддингов
        start_time = time.time()
        embedding_result = embed_unified(
            text=query,
            max_length=512,
            return_dense=True,
            return_sparse=True,
            context="query"
        )
        embedding_time = time.time() - start_time

        # Измеряем время поиска
        start_time = time.time()
        results = hybrid_search(
            query_dense=embedding_result['dense_vecs'][0],
            query_sparse=embedding_result['lexical_weights'][0],
            k=5
        )
        search_time = time.time() - start_time

        total_time = embedding_time + search_time

        # Проверяем производительность
        assert embedding_time < 5.0, f"Генерация эмбеддингов слишком медленная: {embedding_time:.2f}s"
        assert search_time < 2.0, f"Поиск слишком медленный: {search_time:.2f}s"
        assert total_time < 6.0, f"Общее время слишком большое: {total_time:.2f}s"

        assert len(results) > 0, "Должны быть найдены результаты"

        print(f"✅ Производительность: embedding={embedding_time:.2f}s, search={search_time:.2f}s, total={total_time:.2f}s")


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v", "--tb=short"])
