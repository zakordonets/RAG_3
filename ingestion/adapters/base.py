"""
Базовые контракты для адаптеров источников данных
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Dict, Any
import time


@dataclass
class RawDoc:
    """
    Сырой документ от адаптера источника.

    Attributes:
        uri: Канонический URI документа (file:// или https://)
        abs_path: Абсолютный путь к файлу (для локальных источников)
        fetched_at: Время получения документа
        bytes: Сырые байты содержимого
        meta: Метаданные, известные на этапе загрузки
    """
    uri: str
    abs_path: Optional[Path] = None
    fetched_at: float = None
    bytes: bytes = b""
    meta: Dict[str, Any] = None

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = time.time()
        if self.meta is None:
            self.meta = {}


@dataclass
class ParsedDoc:
    """
    Парсированный документ после обработки парсером.

    Attributes:
        text: Основной текст документа
        format: Формат документа ("markdown", "html", "text")
        frontmatter: YAML frontmatter (для Markdown)
        dom: DOM объект (для HTML)
        metadata: Дополнительные метаданные
    """
    text: str
    format: str  # "markdown" | "html" | "text"
    frontmatter: Optional[Dict[str, Any]] = None
    dom: Optional[Any] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SourceAdapter(ABC):
    """
    Базовый интерфейс для адаптеров источников данных.

    Каждый адаптер должен реализовать метод iter_documents(),
    который возвращает поток сырых документов из своего источника.
    """

    @abstractmethod
    def iter_documents(self) -> Iterable[RawDoc]:
        """
        Возвращает поток сырых документов из источника.

        Yields:
            RawDoc: Сырой документ с содержимым и метаданными
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Возвращает имя источника для логирования и метрик.

        Returns:
            str: Имя источника (например, "docusaurus", "website")
        """
        pass


class PipelineStep(ABC):
    """
    Базовый интерфейс для шагов пайплайна обработки.

    Каждый шаг принимает данные на входе и возвращает
    обработанные данные на выходе.
    """

    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        Обрабатывает данные на текущем шаге пайплайна.

        Args:
            data: Входные данные (RawDoc, ParsedDoc, или другой тип)

        Returns:
            Обработанные данные для следующего шага
        """
        pass

    @abstractmethod
    def get_step_name(self) -> str:
        """
        Возвращает имя шага для логирования.

        Returns:
            str: Имя шага (например, "parser", "normalizer")
        """
        pass
