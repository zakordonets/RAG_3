"""
Единый менеджер состояния для всех источников данных
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Set
from loguru import logger
from dataclasses import dataclass, asdict


@dataclass
class DocumentState:
    """Состояние документа в системе."""
    doc_id: str
    content_hash: str
    mtime: float
    source: str
    uri: str
    indexed_at: Optional[float] = None
    last_checked: Optional[float] = None


class StateManager:
    """
    Единый менеджер состояния для отслеживания изменений документов.

    Хранит информацию о всех проиндексированных документах в едином
    формате независимо от источника данных.
    """

    def __init__(self, state_file: str = "ingestion/state.json"):
        """
        Инициализирует менеджер состояния.

        Args:
            state_file: Путь к файлу состояния
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.documents: Dict[str, DocumentState] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Загружает состояние из файла."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Восстанавливаем документы
                for doc_id, doc_data in data.get("documents", {}).items():
                    self.documents[doc_id] = DocumentState(**doc_data)

                logger.info(f"Загружено состояние для {len(self.documents)} документов")
            else:
                logger.info("Файл состояния не найден, создаем новый")

        except Exception as e:
            logger.error(f"Ошибка загрузки состояния: {e}")
            self.documents = {}

    def _save_state(self) -> None:
        """Сохраняет состояние в файл."""
        try:
            # Подготавливаем данные для сохранения
            data = {
                "documents": {doc_id: asdict(doc_state) for doc_id, doc_state in self.documents.items()},
                "last_updated": time.time(),
                "version": "1.0"
            }

            # Сохраняем в файл
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Состояние сохранено: {len(self.documents)} документов")

        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}")

    def get_doc_id(self, uri: str, source: str) -> str:
        """
        Генерирует уникальный ID документа.

        Args:
            uri: URI документа
            source: Источник документа

        Returns:
            Уникальный ID документа
        """
        # Создаем детерминистический ID из URI и источника
        id_string = f"{source}:{uri}"
        return hashlib.sha1(id_string.encode('utf-8')).hexdigest()

    def get_content_hash(self, content: bytes) -> str:
        """
        Вычисляет хеш содержимого документа.

        Args:
            content: Содержимое документа в байтах

        Returns:
            SHA1 хеш содержимого
        """
        return hashlib.sha1(content).hexdigest()

    def is_document_changed(self, uri: str, source: str, content: bytes, mtime: float) -> bool:
        """
        Проверяет, изменился ли документ.

        Args:
            uri: URI документа
            source: Источник документа
            content: Содержимое документа
            mtime: Время модификации

        Returns:
            True если документ изменился или новый
        """
        doc_id = self.get_doc_id(uri, source)
        content_hash = self.get_content_hash(content)

        if doc_id not in self.documents:
            return True  # Новый документ

        doc_state = self.documents[doc_id]

        # Проверяем изменения
        if doc_state.content_hash != content_hash:
            return True  # Изменилось содержимое

        if doc_state.mtime != mtime:
            return True  # Изменилось время модификации

        return False  # Документ не изменился

    def update_document_state(
        self,
        uri: str,
        source: str,
        content: bytes,
        mtime: float,
        indexed_at: Optional[float] = None
    ) -> None:
        """
        Обновляет состояние документа.

        Args:
            uri: URI документа
            source: Источник документа
            content: Содержимое документа
            mtime: Время модификации
            indexed_at: Время индексации (по умолчанию - текущее время)
        """
        doc_id = self.get_doc_id(uri, source)
        content_hash = self.get_content_hash(content)

        if indexed_at is None:
            indexed_at = time.time()

        # Создаем или обновляем состояние документа
        self.documents[doc_id] = DocumentState(
            doc_id=doc_id,
            content_hash=content_hash,
            mtime=mtime,
            source=source,
            uri=uri,
            indexed_at=indexed_at,
            last_checked=time.time()
        )

        logger.debug(f"Обновлено состояние документа: {doc_id}")

    def get_changed_documents(self, source: str = None) -> Set[str]:
        """
        Возвращает множество ID документов, которые нужно переиндексировать.

        Args:
            source: Фильтр по источнику (если None - все источники)

        Returns:
            Множество ID документов для переиндексации
        """
        changed_docs = set()

        for doc_id, doc_state in self.documents.items():
            if source is None or doc_state.source == source:
                # Проверяем, нужно ли переиндексировать
                if self._should_reindex(doc_state):
                    changed_docs.add(doc_id)

        return changed_docs

    def _should_reindex(self, doc_state: DocumentState) -> bool:
        """Определяет, нужно ли переиндексировать документ."""
        # Переиндексируем если документ не был проиндексирован
        if doc_state.indexed_at is None:
            return True

        # Переиндексируем если прошло много времени с последней проверки
        if doc_state.last_checked is None:
            return True

        # Можно добавить другие условия (например, по времени)
        return False

    def cleanup_old_documents(self, max_age_days: int = 30) -> int:
        """
        Удаляет старые записи о документах.

        Args:
            max_age_days: Максимальный возраст записи в днях

        Returns:
            Количество удаленных записей
        """
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        old_docs = []
        for doc_id, doc_state in self.documents.items():
            if doc_state.last_checked is None:
                continue

            age = current_time - doc_state.last_checked
            if age > max_age_seconds:
                old_docs.append(doc_id)

        # Удаляем старые записи
        for doc_id in old_docs:
            del self.documents[doc_id]

        if old_docs:
            logger.info(f"Удалено {len(old_docs)} старых записей о документах")

        return len(old_docs)

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику состояния."""
        if not self.documents:
            return {"total_documents": 0}

        # Группируем по источникам
        sources = {}
        for doc_state in self.documents.values():
            source = doc_state.source
            if source not in sources:
                sources[source] = {"count": 0, "last_indexed": 0}

            sources[source]["count"] += 1
            if doc_state.indexed_at:
                sources[source]["last_indexed"] = max(
                    sources[source]["last_indexed"],
                    doc_state.indexed_at
                )

        return {
            "total_documents": len(self.documents),
            "sources": sources,
            "state_file": str(self.state_file)
        }

    def save(self) -> None:
        """Принудительно сохраняет состояние."""
        self._save_state()

    def __enter__(self):
        """Контекстный менеджер для автоматического сохранения."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматически сохраняет состояние при выходе из контекста."""
        self._save_state()


# Глобальный экземпляр менеджера состояния
_state_manager = None


def get_state_manager() -> StateManager:
    """Возвращает глобальный экземпляр менеджера состояния."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
