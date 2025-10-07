"""
Единый чанкер для всех источников данных
"""

from typing import List, Dict, Any
from loguru import logger

from ingestion.adapters.base import PipelineStep, ParsedDoc
from ingestion.chunking import UniversalChunker, OversizePolicy


class UnifiedChunkerStep(PipelineStep):
    """
    Единый чанкер для всех типов документов.

    Использует UniversalChunker с структурно-осознанным алгоритмом
    для разбиения документов на семантически осмысленные части.
    """

    def __init__(
        self,
        max_tokens: int = 600,
        min_tokens: int = 350,
        overlap_base: int = 100,
        oversize_block_policy: str = "split",
        oversize_block_limit: int = 1200
    ):
        """
        Инициализирует чанкер.

        Args:
            max_tokens: Максимальное количество токенов в чанке
            min_tokens: Минимальное количество токенов в чанке
            overlap_base: Базовое перекрытие между чанками в токенах
            oversize_block_policy: Политика обработки больших блоков ("keep", "split", "skip")
            oversize_block_limit: Лимит для принудительного разбиения
        """
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_base = overlap_base

        # Преобразуем строку в enum
        if oversize_block_policy == "keep":
            policy = OversizePolicy.KEEP
        elif oversize_block_policy == "skip":
            policy = OversizePolicy.SKIP
        else:
            policy = OversizePolicy.SPLIT

        self.oversize_block_policy = policy
        self.oversize_block_limit = oversize_block_limit

        self.chunker = UniversalChunker(
            max_tokens=max_tokens,
            min_tokens=min_tokens,
            overlap_base=overlap_base,
            oversize_block_policy=policy,
            oversize_block_limit=oversize_block_limit
        )

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
            # Подготавливаем метаданные для UniversalChunker
            meta = {
                'doc_id': data.metadata.get("canonical_url", data.metadata.get("uri", "unknown")),
                'site_url': data.metadata.get("site_url", ""),
                'source': data.metadata.get("source", "unknown"),
                'category': data.metadata.get("category", ""),
                'title': data.metadata.get("title", ""),
                'lang': data.metadata.get("lang", "ru")
            }

            # Определяем формат документа
            fmt = "markdown" if data.format in ["markdown", "md", "mdx"] else "html"

            # Разбиваем на чанки с помощью UniversalChunker
            chunks = self.chunker.chunk(data.text, fmt, meta)

            if not chunks:
                logger.warning("UniversalChunker не создал ни одного чанка, используем весь текст")
                # Создаем fallback чанк
                fallback_chunk = self._create_chunk_from_universal(
                    data.text, data, 0, 1, [], meta
                )
                return [fallback_chunk]

            # Преобразуем чанки UniversalChunker в формат пайплайна
            structured_chunks = []
            for chunk in chunks:
                structured_chunk = self._create_chunk_from_universal(
                    chunk.text, data, chunk.chunk_index, chunk.total_chunks,
                    chunk.heading_path, meta
                )
                structured_chunks.append(structured_chunk)

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

    def _create_chunk_from_universal(
        self,
        chunk_text: str,
        parsed_doc: ParsedDoc,
        chunk_index: int,
        total_chunks: int,
        heading_path: List[str],
        meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Создает структурированный чанк из UniversalChunker."""
        # Создаем chunk_id
        doc_id = meta.get("doc_id", "unknown")
        chunk_id = f"{self._hash_string(doc_id)}#{chunk_index}"

        # Создаем payload
        payload = {
            "chunk_id": chunk_id,
            "chunk_text": chunk_text,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "doc_id": doc_id,
            "source": meta.get("source", "unknown"),
            "content_type": parsed_doc.metadata.get("content_type", "unknown"),
            "format": parsed_doc.format,
            "chunking_strategy": "universal",
            "max_tokens": self.max_tokens,
            "min_tokens": self.min_tokens,
            "overlap_base": self.overlap_base,
            "heading_path": heading_path,
            "site_url": meta.get("site_url", ""),
            "category": meta.get("category", ""),
            "title": meta.get("title", ""),
            "lang": meta.get("lang", "ru")
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

    def _create_chunk(self, chunk_text: str, parsed_doc: ParsedDoc, chunk_index: int, total_chunks: int) -> Dict[str, Any]:
        """Создает структурированный чанк (fallback метод)."""
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
            "chunking_strategy": "fallback",
            "max_tokens": self.max_tokens,
            "min_tokens": self.min_tokens,
            "overlap_base": self.overlap_base
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
