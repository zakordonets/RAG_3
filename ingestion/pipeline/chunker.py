"""
Единый чанкер для всех источников данных
"""

from typing import List, Dict, Any
from loguru import logger

from ingestion.adapters.base import PipelineStep, ParsedDoc
from ingestion.chunkers import UnifiedChunker, ChunkingStrategy


class UnifiedChunkerStep(PipelineStep):
    """
    Единый чанкер для всех типов документов.

    Использует UnifiedChunker с адаптивными стратегиями
    для разбиения документов на семантически осмысленные части.
    """

    def __init__(
        self,
        max_tokens: int = 600,
        overlap_tokens: int = 120,
        strategy: str = "simple"
    ):
        """
        Инициализирует чанкер.

        Args:
            max_tokens: Максимальное количество токенов в чанке
            overlap_tokens: Перекрытие между чанками в токенах
            strategy: Стратегия чанкинга ("simple", "adaptive")
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.strategy = ChunkingStrategy.SIMPLE if strategy == "simple" else ChunkingStrategy.ADAPTIVE

        self.chunker = UnifiedChunker(default_strategy=self.strategy)

    def process(self, data: ParsedDoc) -> List[Dict[str, Any]]:
        """
        Разбивает документ на чанки.

        Args:
            data: Парсированный документ

        Returns:
            Список чанков с текстом и метаданными
        """
        if not isinstance(data, ParsedDoc):
            logger.warning(f"UnifiedChunkerStep получил не ParsedDoc: {type(data)}")
            return []

        if not data.text.strip():
            logger.warning("Пустой текст документа, пропускаем чанкинг")
            return []

        try:
            # Разбиваем на чанки
            chunks = self.chunker.chunk_text(
                data.text,
                strategy=self.strategy,
                max_tokens=self.max_tokens,
                overlap_tokens=self.overlap_tokens
            )

            if not chunks:
                logger.warning("Чанкер не создал ни одного чанка, используем весь текст")
                chunks = [data.text]

            # Создаем структурированные чанки
            structured_chunks = []
            for i, chunk_text in enumerate(chunks):
                chunk = self._create_chunk(chunk_text, data, i, len(chunks))
                structured_chunks.append(chunk)

            logger.info(f"Создано {len(structured_chunks)} чанков из документа")
            return structured_chunks

        except Exception as e:
            logger.error(f"Ошибка при чанкинге документа: {e}")
            # Fallback: используем весь текст как один чанк
            fallback_chunk = self._create_chunk(data.text, data, 0, 1)
            return [fallback_chunk]

    def get_step_name(self) -> str:
        """Возвращает имя шага."""
        return "unified_chunker"

    def _create_chunk(self, chunk_text: str, parsed_doc: ParsedDoc, chunk_index: int, total_chunks: int) -> Dict[str, Any]:
        """Создает структурированный чанк."""
        # Создаем chunk_id
        doc_id = parsed_doc.metadata.get("canonical_url", parsed_doc.metadata.get("uri", "unknown"))
        chunk_id = f"{self._hash_string(doc_id)}#{chunk_index}"

        # Создаем payload
        payload = {
            "chunk_id": chunk_id,
            "chunk_text": chunk_text,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "doc_id": doc_id,
            "source": parsed_doc.metadata.get("source", "unknown"),
            "content_type": parsed_doc.metadata.get("content_type", "unknown"),
            "format": parsed_doc.format,
            "chunking_strategy": self.strategy.value,
            "max_tokens": self.max_tokens,
            "overlap_tokens": self.overlap_tokens
        }

        # Копируем метаданные документа
        for key, value in parsed_doc.metadata.items():
            if key not in payload and value is not None:
                payload[key] = value

        # Копируем frontmatter если есть
        if parsed_doc.frontmatter:
            for key, value in parsed_doc.frontmatter.items():
                if key not in payload and value is not None:
                    payload[f"frontmatter_{key}"] = value

        return {
            "text": chunk_text,
            "payload": payload
        }

    def _hash_string(self, text: str) -> str:
        """Создает хеш строки для ID."""
        import hashlib
        return hashlib.sha1(text.encode('utf-8')).hexdigest()
