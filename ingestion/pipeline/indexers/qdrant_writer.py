"""
Единый QdrantWriter для всех источников данных
"""

import time
import uuid
from typing import List, Dict, Any, Optional
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector, PayloadSchemaType, VectorParams, Distance, SparseVectorParams, UpdateCollection

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
            "batches_processed": 0,
            "zero_dense_vectors": 0,  # Подсчет нулевых dense векторов
            "last_upsert_points": 0  # Количество реально записанных точек в последний батч
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

        # Логируем долю нулевых dense векторов
        zero_ratio = 0.0
        if self.stats["processed_chunks"] > 0:
            zero_ratio = self.stats["zero_dense_vectors"] / self.stats["processed_chunks"]
            if zero_ratio > 0.1:  # Если больше 10% нулевых векторов
                logger.warning(f"⚠️ Высокая доля нулевых dense векторов: {zero_ratio:.1%}")

        logger.success(f"🎉 QdrantWriter завершен за {elapsed:.2f}s")
        logger.info(f"📊 Итоговая статистика:")
        logger.info(f"  📄 Всего чанков: {len(chunks)}")
        logger.info(f"  ✅ Успешно обработано: {total_processed}")
        logger.info(f"  ❌ Ошибок: {len(chunks) - total_processed}")
        logger.info(f"  🔢 Батчей обработано: {self.stats['batches_processed']}")
        logger.info(f"  🎯 Нулевых dense векторов: {self.stats['zero_dense_vectors']} ({zero_ratio:.1%})")
        logger.info(f"  💾 Последний upsert: {self.stats['last_upsert_points']} точек")

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

            # Валидация размерности dense векторов
            expected_dim = CONFIG.embedding_dim  # 1024 для BGE-M3
            if any(len(v) != expected_dim for v in dense_vecs):
                raise ValueError(f"dense dim mismatch: expected {expected_dim}, got {[len(v) for v in dense_vecs]}")

        except Exception as e:
            logger.error(f"Ошибка генерации эмбеддингов: {e}")
            # Fallback векторы
            dense_vecs = [[0.0] * CONFIG.embedding_dim] * len(texts)
            sparse_results = [{}] * len(texts)
            self.stats["zero_dense_vectors"] += len(dense_vecs)
            logger.warning(f"Используем {len(dense_vecs)} нулевых dense векторов в качестве фолбэка")

        # Создаем точки для Qdrant
        points = []
        for i, chunk in enumerate(chunks):
            try:
                # Получаем контекст для логирования
                doc_id = chunk.get("payload", {}).get("doc_id", "unknown") if isinstance(chunk, dict) else "unknown"
                site_url = chunk.get("payload", {}).get("site_url", "unknown") if isinstance(chunk, dict) else "unknown"

                point = self._create_point(chunk, dense_vecs[i], sparse_results[i])
                points.append(point)
            except Exception as e:
                logger.error(f"Ошибка создания точки для чанка {i} (doc_id={doc_id}, site_url={site_url}): {e}")
                continue

        # Записываем в Qdrant с ретраями
        if points:
            for attempt in range(3):
                try:
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=points,
                        wait=True
                    )
                    self.stats["last_upsert_points"] = len(points)
                    return len(points)
                except Exception as e:
                    logger.warning(f"upsert retry {attempt+1}/3: {e}")
                    if attempt < 2:  # Не ждем после последней попытки
                        time.sleep(1.5 * (attempt + 1))
                    else:
                        logger.error(f"Ошибка записи в Qdrant после 3 попыток: {e}")
                        logger.error(f"Не удалось записать {len(points)} точек в батч")
                        self.stats["last_upsert_points"] = 0

                        # Binary split для переживания "битых" точек
                        if len(chunks) > 1:
                            logger.info(f"Пробуем binary split: разбиваем {len(chunks)} чанков пополам")
                            mid = len(chunks) // 2
                            first_half = self._process_batch(chunks[:mid])
                            second_half = self._process_batch(chunks[mid:])
                            return first_half + second_half

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

        # Создаем векторы согласно официальной документации Qdrant
        vectors = {"dense": dense_vec}

        # Добавляем sparse вектор если есть (в том же поле vectors)
        if CONFIG.use_sparse and sparse_data:
            try:
                indices, values = self._convert_sparse_data(sparse_data)
                if indices:
                    # Sparse вектор добавляется в то же поле vectors с именем "sparse"
                    vectors["sparse"] = SparseVector(indices=indices, values=values)
            except Exception as e:
                doc_id = payload.get("doc_id", "unknown")
                site_url = payload.get("site_url", "unknown")
                logger.warning(f"Ошибка создания sparse вектора (doc_id={doc_id}, site_url={site_url}): {e}")

        # Создаем payload
        qdrant_payload = self._create_payload(chunk, text, payload)

        # Создаем структуру точки согласно официальной документации
        return PointStruct(
            id=point_id,
            vector=vectors,  # dense + sparse в одном поле vector (единственное число)
            payload=qdrant_payload
        )

    def _generate_point_id(self, chunk: Dict[str, Any], text: str) -> str:
        """Генерирует ID точки для Qdrant."""
        # Используем chunk_id из payload если есть
        if isinstance(chunk, dict) and "payload" in chunk:
            chunk_id = chunk["payload"].get("chunk_id")
            if chunk_id:
                # Используем полный chunk_id (включая chunk_index) для уникальности
                base_hash = text_hash(chunk_id)

                # Создаем UUID из хеша (берем первые 32 символа)
                hex32 = base_hash.replace("-", "")[:32]
                # Дополняем до 32 символов если нужно
                if len(hex32) < 32:
                    hex32 = hex32.ljust(32, '0')
                return str(uuid.UUID(hex=hex32))

        # Fallback 1: используем стабильный ключ doc_id#chunk_index
        if isinstance(chunk, dict) and "payload" in chunk:
            payload = chunk["payload"]
            doc_id = payload.get("doc_id")
            chunk_index = payload.get("chunk_index")
            if doc_id and chunk_index is not None:
                stable_key = f"{doc_id}#{chunk_index}"
                base_hash = text_hash(stable_key)
                hex32 = base_hash.replace("-", "")[:32]
                if len(hex32) < 32:
                    hex32 = hex32.ljust(32, '0')
                return str(uuid.UUID(hex=hex32))

        # Fallback 2: создаем детерминистический ID из текста
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
            # Быстрый путь для формата {"indices": [...], "values": [...]}
            if "indices" in sparse_data and "values" in sparse_data:
                indices = sparse_data["indices"]
                values = sparse_data["values"]
                # Фильтруем нулевые веса
                valid_pairs = [(idx, val) for idx, val in zip(indices, values) if val != 0.0]
                if valid_pairs:
                    # Сортируем по абсолютному значению веса (desc)
                    sorted_pairs = sorted(valid_pairs, key=lambda x: abs(x[1]), reverse=True)
                    # Ограничиваем количество
                    max_indices = 1000
                    if len(sorted_pairs) > max_indices:
                        sorted_pairs = sorted_pairs[:max_indices]
                    return [idx for idx, _ in sorted_pairs], [val for _, val in sorted_pairs]
                return [], []

            # Обычный формат lexical_weights: {"token_id": weight}
            valid_items = []
            for k, v in sparse_data.items():
                try:
                    idx = int(k)
                    weight = float(v) if not hasattr(v, 'item') else float(v.item())
                    if weight != 0.0:  # Фильтруем нулевые веса
                        valid_items.append((idx, weight))
                except ValueError:
                    logger.warning(f"sparse key is not int, got {k!r}; check embedder output")
                    continue

            # Сортируем по абсолютному значению веса (desc)
            sorted_items = sorted(valid_items, key=lambda x: abs(x[1]), reverse=True)

            # Ограничиваем количество для производительности
            max_indices = 1000
            if len(sorted_items) > max_indices:
                sorted_items = sorted_items[:max_indices]

            indices = [idx for idx, _ in sorted_items]
            values = [weight for _, weight in sorted_items]

            return indices, values

        return [], []

    def _clean_numpy_types(self, value: Any) -> Any:
        """Очищает numpy типы для сериализации в JSON."""
        try:
            import numpy as np
            if isinstance(value, np.ndarray):  # numpy array
                return value.tolist()
            elif isinstance(value, (np.float32, np.float64, np.int32, np.int64)):  # numpy scalar
                return value.item()
            elif isinstance(value, dict):
                return {k: self._clean_numpy_types(v) for k, v in value.items()}
            elif isinstance(value, (list, tuple)):
                return [self._clean_numpy_types(item) for item in value]
            else:
                return value
        except ImportError:
            # Если numpy не установлен, возвращаем как есть
            return value

    def _create_payload(self, chunk: Dict[str, Any], text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Создает payload для Qdrant."""
        qdrant_payload = {}

        # Копируем все поля из payload
        for key, value in payload.items():
            if value is not None:
                qdrant_payload[key] = self._clean_numpy_types(value)

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
            # Список индексов для создания с enum типами
            indexes = [
                {"field_name": "category", "field_schema": PayloadSchemaType.KEYWORD},
                {"field_name": "groups_path", "field_schema": PayloadSchemaType.KEYWORD},
                {"field_name": "title", "field_schema": PayloadSchemaType.TEXT},
                {"field_name": "source", "field_schema": PayloadSchemaType.KEYWORD},
                {"field_name": "content_type", "field_schema": PayloadSchemaType.KEYWORD},
                {"field_name": "site_url", "field_schema": PayloadSchemaType.KEYWORD},  # Исправлено: site_url вместо canonical_url
                {"field_name": "indexed_at", "field_schema": PayloadSchemaType.FLOAT},
                {"field_name": "doc_id", "field_schema": PayloadSchemaType.KEYWORD},  # Удобно фильтровать/переиндексировать конкретный документ
                {"field_name": "heading_path", "field_schema": PayloadSchemaType.KEYWORD},  # Для таргетных бустов/фильтров по разделам
                {"field_name": "page_type", "field_schema": PayloadSchemaType.KEYWORD},  # Для бустов по типу страницы
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

    def ensure_collection(self) -> None:
        """Создает коллекцию с нужной схемой если она не существует."""
        try:
            # Проверяем, существует ли коллекция
            info = self.client.get_collection(self.collection_name)
            logger.info(f"Коллекция {self.collection_name} уже существует")

            # Проверяем sparse векторы (может не быть в старых версиях Qdrant)
            try:
                # Более надежная проверка sparse векторов
                has_sparse = False
                if hasattr(info.config, 'sparse_vectors_config'):
                    sparse_config = info.config.sparse_vectors_config
                    has_sparse = sparse_config is not None and len(sparse_config) > 0

                if CONFIG.use_sparse and not has_sparse:
                    logger.info("Добавляем sparse_vectors_config для существующей коллекции")
                    self.client.update_collection(
                        collection_name=self.collection_name,
                        sparse_vectors_config={"sparse": SparseVectorParams()}
                    )
                    logger.success("✅ Добавлен sparse_vectors_config для существующей коллекции")
                elif CONFIG.use_sparse and has_sparse:
                    logger.info("✅ Sparse векторы уже настроены в коллекции")
            except Exception as e:
                logger.warning(f"Ошибка при проверке/добавлении sparse векторов: {e}")

            # Убеждаемся, что индексы есть
            self.create_payload_indexes()
            return

        except Exception as e:
            # Если коллекция не существует, создаем её
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                logger.info(f"Коллекция {self.collection_name} не существует, создаем новую")
            else:
                logger.warning(f"Ошибка при проверке коллекции {self.collection_name}: {e}")
                logger.info(f"Попытка создать коллекцию {self.collection_name} с гибридной схемой")

            # Создаем коллекцию с нуля
            logger.info(f"Создаем коллекцию {self.collection_name} с гибридной схемой")

            # Схема векторов: named dense + named sparse
            vectors_config = {
                "dense": VectorParams(
                    size=CONFIG.embedding_dim,  # 1024 для BGE-M3
                    distance=Distance.COSINE,
                    hnsw_config={
                        "m": CONFIG.qdrant_hnsw_m,
                        "ef_construct": CONFIG.qdrant_hnsw_ef_construct,
                        "full_scan_threshold": CONFIG.qdrant_hnsw_full_scan_threshold,
                    }
                )
            }

            # Sparse векторы настраиваются отдельно согласно документации
            sparse_vectors_config = {"sparse": SparseVectorParams()} if CONFIG.use_sparse else None

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=vectors_config,
                sparse_vectors_config=sparse_vectors_config
            )

            logger.success(f"✅ Коллекция {self.collection_name} создана с гибридной схемой")

            # Создаем индексы payload
            self.create_payload_indexes()

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику обработки."""
        return self.stats.copy()
