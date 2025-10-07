"""
Единый эмбеддер для всех источников данных
"""

from typing import List, Dict, Any
from loguru import logger

from ingestion.adapters.base import PipelineStep
from app.services.core.embeddings import embed_batch_optimized
from app.config import CONFIG


class Embedder(PipelineStep):
    """
    Единый эмбеддер для генерации векторов.

    Использует BGE-M3 для создания dense и sparse векторов
    для всех типов документов.
    """

    def __init__(self, batch_size: int = None):
        """
        Инициализирует эмбеддер.

        Args:
            batch_size: Размер батча для обработки (по умолчанию из CONFIG)
        """
        self.batch_size = batch_size or CONFIG.embedding_batch_size or 16
        self.stats = {
            "total_chunks": 0,
            "processed_chunks": 0,
            "failed_chunks": 0,
            "batches_processed": 0
        }

    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Генерирует эмбеддинги для чанков.

        Args:
            data: Список чанков

        Returns:
            Список чанков с добавленными векторами
        """
        if not isinstance(data, list):
            logger.warning(f"Embedder получил не список: {type(data)}")
            return []

        if not data:
            return []

        logger.info(f"Embedder: начинаем обработку {len(data)} чанков")

        # Обрабатываем батчами
        embedded_chunks = []
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(data) + self.batch_size - 1) // self.batch_size

            logger.info(f"Обрабатываем батч {batch_num}/{total_batches} ({len(batch)} чанков)")

            try:
                embedded_batch = self._process_batch(batch)
                embedded_chunks.extend(embedded_batch)
                self.stats["batches_processed"] += 1

                logger.info(f"✅ Батч {batch_num}/{total_batches} обработан")

            except Exception as e:
                logger.error(f"❌ Ошибка в батче {batch_num}: {e}")
                self.stats["failed_chunks"] += len(batch)
                continue

        # Обновляем статистику
        self.stats["total_chunks"] += len(data)
        self.stats["processed_chunks"] += len(embedded_chunks)

        logger.info(f"Embedder завершен: {len(embedded_chunks)}/{len(data)} чанков обработано")
        return embedded_chunks

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "embedder"

    def _process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Обрабатывает один батч чанков.

        Args:
            batch: Батч чанков

        Returns:
            Список чанков с добавленными векторами
        """
        # Извлекаем тексты
        texts = []
        for chunk in batch:
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

            dense_vecs = embedding_results.get('dense_vecs', [])
            sparse_results = embedding_results.get('lexical_weights', [])

        except Exception as e:
            logger.error(f"Ошибка генерации эмбеддингов: {e}")
            # Fallback векторы
            dense_vecs = [[0.0] * 1024] * len(texts)
            sparse_results = [{}] * len(texts)

        # Добавляем векторы к чанкам
        embedded_chunks = []
        for i, chunk in enumerate(batch):
            try:
                embedded_chunk = self._add_vectors_to_chunk(
                    chunk,
                    dense_vecs[i] if i < len(dense_vecs) else [0.0] * 1024,
                    sparse_results[i] if i < len(sparse_results) else {}
                )
                embedded_chunks.append(embedded_chunk)
            except Exception as e:
                logger.error(f"Ошибка добавления векторов к чанку {i}: {e}")
                continue

        return embedded_chunks

    def _add_vectors_to_chunk(self, chunk: Dict[str, Any], dense_vec: List[float], sparse_data: Dict[str, Any]) -> Dict[str, Any]:
        """Добавляет векторы к чанку."""
        if not isinstance(chunk, dict):
            return chunk

        # Создаем копию чанка
        embedded_chunk = chunk.copy()

        # Добавляем векторы в payload
        if "payload" not in embedded_chunk:
            embedded_chunk["payload"] = {}

        embedded_chunk["payload"]["dense_vector"] = dense_vec
        embedded_chunk["payload"]["sparse_data"] = sparse_data
        embedded_chunk["payload"]["embedded"] = True

        return embedded_chunk

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику обработки."""
        return self.stats.copy()
