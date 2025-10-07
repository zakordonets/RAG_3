"""
Единый QdrantWriter для всех источников данных
"""

import time
import uuid
from typing import List, Dict, Any, Optional
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

from app.config import CONFIG
from app.services.core.embeddings import embed_batch_optimized
from ingestion.adapters.base import PipelineStep
from ingestion.chunking import text_hash


class QdrantWriter(PipelineStep):
    """
    Единый писатель в Qdrant для всех источников данных.

    Принимает чанки в едином формате и записывает их в Qdrant
    с созданием dense и sparse векторов.
    """

    def __init__(self, collection_name: Optional[str] = None):
        """
        Инициализирует QdrantWriter.

        Args:
            collection_name: Имя коллекции в Qdrant (по умолчанию из CONFIG)
        """
        self.collection_name = collection_name or CONFIG.qdrant_collection
        self.client = QdrantClient(
            url=CONFIG.qdrant_url,
            api_key=CONFIG.qdrant_api_key or None
        )
        self.batch_size = CONFIG.embedding_batch_size or 16
        self.stats = {
            "total_chunks": 0,
            "processed_chunks": 0,
            "failed_chunks": 0,
            "batches_processed": 0
        }

    def process(self, data: Any) -> Any:
        """
        Обрабатывает чанки и записывает их в Qdrant.

        Args:
            data: Список чанков или одиночный чанк

        Returns:
            Статистика обработки
        """
        # Нормализуем входные данные
        if isinstance(data, list):
            chunks = data
        else:
            chunks = [data]

        if not chunks:
            return self.stats

        logger.info(f"QdrantWriter: начинаем обработку {len(chunks)} чанков")
        start_time = time.time()

        # Обрабатываем чанки батчами
        total_processed = 0
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size

            logger.info(f"Обрабатываем батч {batch_num}/{total_batches} ({len(batch)} чанков)")

            try:
                processed_count = self._process_batch(batch)
                total_processed += processed_count
                self.stats["batches_processed"] += 1

                logger.info(f"✅ Батч {batch_num}/{total_batches} обработан: {processed_count} чанков")

            except Exception as e:
                logger.error(f"❌ Ошибка в батче {batch_num}: {e}")
                self.stats["failed_chunks"] += len(batch)
                continue

        # Обновляем статистику
        elapsed = time.time() - start_time
        self.stats["total_chunks"] += len(chunks)
        self.stats["processed_chunks"] += total_processed

        logger.info(f"QdrantWriter завершен за {elapsed:.2f}s")
        logger.info(f"  Всего чанков: {len(chunks)}")
        logger.info(f"  Успешно обработано: {total_processed}")
        logger.info(f"  Ошибок: {len(chunks) - total_processed}")

        return self.stats

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "qdrant_writer"

    def _process_batch(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Обрабатывает один батч чанков.

        Args:
            chunks: Список чанков для обработки

        Returns:
            Количество успешно обработанных чанков
        """
        if not chunks:
            return 0

        # Извлекаем тексты для эмбеддингов
        texts = []
        for chunk in chunks:
            if isinstance(chunk, dict):
                text = chunk.get("text", "")
            else:
                text = str(chunk)
            texts.append(text)

        # Генерируем эмбеддинги
        try:
            embedding_results = embed_batch_optimized(
                texts,
                max_length=CONFIG.embedding_max_length_doc,
                return_dense=True,
                return_sparse=CONFIG.use_sparse,
                context="document"
            )

            dense_vecs = embedding_results.get('dense_vecs', [[0.0] * 1024] * len(texts))
            sparse_results = embedding_results.get('lexical_weights', [{}] * len(texts))

        except Exception as e:
            logger.error(f"Ошибка генерации эмбеддингов: {e}")
            # Fallback векторы
            dense_vecs = [[0.0] * 1024] * len(texts)
            sparse_results = [{}] * len(texts)

        # Создаем точки для Qdrant
        points = []
        for i, chunk in enumerate(chunks):
            try:
                point = self._create_point(chunk, dense_vecs[i], sparse_results[i])
                points.append(point)
            except Exception as e:
                logger.error(f"Ошибка создания точки для чанка {i}: {e}")
                continue

        # Записываем в Qdrant
        if points:
            try:
                self.client.upsert(collection_name=self.collection_name, points=points)
                return len(points)
            except Exception as e:
                logger.error(f"Ошибка записи в Qdrant: {e}")
                return 0

        return 0

    def _create_point(self, chunk: Dict[str, Any], dense_vec: List[float], sparse_data: Dict[str, Any]) -> PointStruct:
        """
        Создает точку для Qdrant из чанка.

        Args:
            chunk: Чанк с текстом и метаданными
            dense_vec: Плотный вектор
            sparse_data: Разреженные данные

        Returns:
            PointStruct для Qdrant
        """
        # Извлекаем данные из чанка
        if isinstance(chunk, dict):
            text = chunk.get("text", "")
            payload = chunk.get("payload", {})
        else:
            text = str(chunk)
            payload = {}

        # Генерируем ID
        point_id = self._generate_point_id(chunk, text)

        # Создаем вектор
        vector_dict = {"dense": dense_vec}

        # Добавляем sparse вектор если есть
        if CONFIG.use_sparse and sparse_data:
            try:
                indices, values = self._convert_sparse_data(sparse_data)
                if indices:
                    vector_dict["sparse"] = SparseVector(indices=indices, values=values)
            except Exception as e:
                logger.warning(f"Ошибка создания sparse вектора: {e}")

        # Создаем payload
        qdrant_payload = self._create_payload(chunk, text, payload)

        return PointStruct(
            id=point_id,
            vector=vector_dict,
            payload=qdrant_payload
        )

    def _generate_point_id(self, chunk: Dict[str, Any], text: str) -> str:
        """Генерирует ID точки для Qdrant."""
        # Используем chunk_id из payload если есть
        if isinstance(chunk, dict) and "payload" in chunk:
            chunk_id = chunk["payload"].get("chunk_id")
            if chunk_id:
                # Преобразуем chunk_id в UUID для Qdrant
                if "#" in chunk_id:
                    base_hash = text_hash(chunk_id.split("#")[0])
                else:
                    base_hash = text_hash(chunk_id)

                # Создаем UUID из хеша (берем первые 32 символа)
                hex32 = base_hash.replace("-", "")[:32]
                # Дополняем до 32 символов если нужно
                if len(hex32) < 32:
                    hex32 = hex32.ljust(32, '0')
                return str(uuid.UUID(hex=hex32))

        # Fallback: создаем детерминистический ID из текста
        raw_hash = text_hash(text)
        hex32 = raw_hash.replace("-", "")[:32]
        # Дополняем до 32 символов если нужно
        if len(hex32) < 32:
            hex32 = hex32.ljust(32, '0')
        return str(uuid.UUID(hex=hex32))

    def _convert_sparse_data(self, sparse_data: Dict[str, Any]) -> tuple[List[int], List[float]]:
        """Преобразует sparse данные в формат Qdrant."""
        if not sparse_data:
            return [], []

        # Если это уже словарь lexical_weights
        if isinstance(sparse_data, dict):
            # Сортируем по весам для лучшей производительности
            sorted_items = sorted(sparse_data.items(), key=lambda x: x[1], reverse=True)

            # Ограничиваем количество для производительности
            max_indices = 1000
            if len(sorted_items) > max_indices:
                sorted_items = sorted_items[:max_indices]

            indices = [int(k) for k, v in sorted_items]
            values = [float(v) for k, v in sorted_items]

            return indices, values

        return [], []

    def _create_payload(self, chunk: Dict[str, Any], text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Создает payload для Qdrant."""
        qdrant_payload = {}

        # Копируем все поля из payload
        for key, value in payload.items():
            if value is not None:
                qdrant_payload[key] = value

        # Добавляем обязательные поля
        qdrant_payload["text"] = text
        qdrant_payload["indexed_at"] = time.time()
        qdrant_payload["indexed_via"] = "unified_pipeline"

        # Очищаем тяжелые поля
        heavy_fields = ["content", "html", "raw", "raw_content", "dom"]
        for field in heavy_fields:
            qdrant_payload.pop(field, None)

        return qdrant_payload

    def create_payload_indexes(self) -> None:
        """Создает индексы для payload полей."""
        try:
            # Список индексов для создания
            indexes = [
                {"field_name": "category", "field_schema": "keyword"},
                {"field_name": "groups_path", "field_schema": "keyword"},
                {"field_name": "title", "field_schema": "text"},
                {"field_name": "source", "field_schema": "keyword"},
                {"field_name": "content_type", "field_schema": "keyword"},
                {"field_name": "canonical_url", "field_schema": "keyword"},
                {"field_name": "indexed_at", "field_schema": "float"},
            ]

            for index_config in indexes:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        **index_config
                    )
                    logger.info(f"Создан индекс для поля: {index_config['field_name']}")
                except Exception as e:
                    logger.warning(f"Не удалось создать индекс для {index_config['field_name']}: {e}")

        except Exception as e:
            logger.error(f"Ошибка создания индексов: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику обработки."""
        return self.stats.copy()
