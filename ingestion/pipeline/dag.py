"""
Единый DAG пайплайна обработки документов
"""

from typing import List, Iterable, Any, Dict
from loguru import logger
import time

from ingestion.adapters.base import PipelineStep, RawDoc


class PipelineDAG:
    """
    Единый DAG для обработки документов из любых источников.

    Выполняет последовательность шагов:
    Parse → Normalize → Chunk → Embed → Index

    Каждый шаг принимает данные на входе и возвращает обработанные
    данные для следующего шага.
    """

    def __init__(self, steps: List[PipelineStep]):
        """
        Инициализирует DAG с заданными шагами.

        Args:
            steps: Список шагов пайплайна в порядке выполнения
        """
        self.steps = steps
        self.stats = {
            "total_docs": 0,
            "processed_docs": 0,
            "failed_docs": 0,
            "step_times": {}
        }

    def run(self, raw_docs_iterable: Iterable[RawDoc]) -> Dict[str, Any]:
        """
        Запускает обработку потока сырых документов через все шаги DAG.

        Args:
            raw_docs_iterable: Поток сырых документов от адаптера

        Returns:
            Dict с статистикой обработки
        """
        logger.info(f"Запуск DAG с {len(self.steps)} шагами")
        start_time = time.time()

        for step in self.steps:
            logger.info(f"  - {step.get_step_name()}")

        # Сбрасываем статистику
        self.stats = {
            "total_docs": 0,
            "processed_docs": 0,
            "failed_docs": 0,
            "step_times": {step.get_step_name(): 0.0 for step in self.steps}
        }

        try:
            for raw_doc in raw_docs_iterable:
                self.stats["total_docs"] += 1

                try:
                    # Проходим через все шаги пайплайна
                    data = raw_doc

                    for step in self.steps:
                        step_start = time.time()
                        data = step.process(data)
                        step_time = time.time() - step_start

                        # Накапливаем время выполнения шага
                        step_name = step.get_step_name()
                        self.stats["step_times"][step_name] += step_time

                    self.stats["processed_docs"] += 1

                    # Логируем прогресс
                    if self.stats["processed_docs"] % 50 == 0:
                        logger.info(f"Обработано документов: {self.stats['processed_docs']}")

                except Exception as e:
                    self.stats["failed_docs"] += 1
                    logger.error(f"Ошибка при обработке документа {raw_doc.uri}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Критическая ошибка в DAG: {e}")
            raise

        # Финальная статистика
        total_time = time.time() - start_time
        self.stats["total_time"] = total_time

        logger.info(f"DAG завершен за {total_time:.2f}s")
        logger.info(f"  Всего документов: {self.stats['total_docs']}")
        logger.info(f"  Успешно обработано: {self.stats['processed_docs']}")
        logger.info(f"  Ошибок: {self.stats['failed_docs']}")

        # Время по шагам
        for step_name, step_time in self.stats["step_times"].items():
            percentage = (step_time / total_time) * 100 if total_time > 0 else 0
            logger.info(f"  {step_name}: {step_time:.2f}s ({percentage:.1f}%)")

        return self.stats

    def get_step_names(self) -> List[str]:
        """Возвращает список имен шагов в порядке выполнения."""
        return [step.get_step_name() for step in self.steps]

    def add_step(self, step: PipelineStep, position: int = None):
        """
        Добавляет шаг в пайплайн.

        Args:
            step: Шаг для добавления
            position: Позиция в списке (по умолчанию - в конец)
        """
        if position is None:
            self.steps.append(step)
        else:
            self.steps.insert(position, step)

        # Обновляем статистику
        self.stats["step_times"][step.get_step_name()] = 0.0
