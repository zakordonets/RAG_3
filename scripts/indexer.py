#!/usr/bin/env python3
"""
Production модуль для индексации и переиндексации документации edna Chat Center

Единая точка входа для всех операций индексации в production среде.
Поддерживает различные режимы работы и автоматическую диагностику.
"""

import sys
import os
import argparse
from typing import Optional, Dict, Any
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from qdrant_client import QdrantClient
from urllib.parse import urlparse

from app.config import CONFIG
from ingestion.pipeline import crawl_and_index


class Indexer:
    """Production класс для управления индексацией"""

    def __init__(self):
        self.client = self._get_qdrant_client()

    def _get_qdrant_client(self) -> QdrantClient:
        """Создает клиент Qdrant"""
        parsed = urlparse(CONFIG.qdrant_url)
        return QdrantClient(
            host=parsed.hostname,
            port=parsed.port or 6333,
            prefer_grpc=CONFIG.qdrant_grpc
        )

    def status(self) -> Dict[str, Any]:
        """Проверяет текущее состояние системы"""
        try:
            # Информация о коллекции
            collection_info = self.client.get_collection(CONFIG.qdrant_collection)

            # Проверяем sparse векторы в последних точках
            points = self.client.scroll(
                collection_name=CONFIG.qdrant_collection,
                limit=10,
                with_vectors=True
            )[0]

            sparse_coverage = 0
            if points:
                sparse_count = sum(
                    1 for p in points
                    if hasattr(p, 'vector') and isinstance(p.vector, dict) and 'sparse' in p.vector
                )
                sparse_coverage = (sparse_count / len(points)) * 100

            # Безопасно извлекаем размерность эмбеддингов
            embedding_dim = "unknown"
            has_sparse_config = False

            try:
                # Проверяем named vectors (новая структура)
                if hasattr(collection_info.config.params, 'vectors') and collection_info.config.params.vectors:
                    vectors_config = collection_info.config.params.vectors
                    if hasattr(vectors_config, 'get'):
                        # Это dict
                        if "dense" in vectors_config:
                            embedding_dim = vectors_config["dense"].size
                        has_sparse_config = "sparse" in vectors_config
                    else:
                        # Это VectorParams (старая структура)
                        embedding_dim = vectors_config.size
            except Exception:
                # Fallback - пытаемся получить размерность из первой точки
                if points:
                    try:
                        if hasattr(points[0], 'vector'):
                            if isinstance(points[0].vector, dict) and 'dense' in points[0].vector:
                                embedding_dim = len(points[0].vector['dense'])
                            elif isinstance(points[0].vector, list):
                                embedding_dim = len(points[0].vector)
                    except Exception:
                        pass

            return {
                "collection_exists": True,
                "total_points": collection_info.points_count,
                "sparse_coverage": sparse_coverage,
                "embedding_dim": embedding_dim,
                "has_sparse_config": has_sparse_config,
                "backend": CONFIG.embeddings_backend,
                "use_sparse": CONFIG.use_sparse,
                "chunk_config": f"{CONFIG.chunk_min_tokens}-{CONFIG.chunk_max_tokens} tokens"
            }
        except Exception as e:
            return {
                "collection_exists": False,
                "error": str(e)
            }

    def reindex(self,
                mode: str = "auto",
                strategy: str = "jina",
                use_cache: bool = True,
                max_pages: Optional[int] = None,
                force_full: bool = False,
                sparse: bool = True,
                backend: str = "auto") -> Dict[str, Any]:
        """
        Выполняет переиндексацию

        Args:
            mode: Режим переиндексации (auto, full, incremental, cache_only)
            strategy: Стратегия краулинга (jina, browser, http)
            use_cache: Использовать кеш
            max_pages: Ограничение количества страниц (для тестирования)
            force_full: Принудительная полная переиндексация (совместимость с API)
            sparse: Включить sparse векторы
            backend: Backend для эмбеддингов (auto, onnx, bge, hybrid)
        """
        logger.info(f"🚀 Начинаем переиндексацию в режиме '{mode}'")
        logger.info(f"📋 Параметры: strategy={strategy}, use_cache={use_cache}, max_pages={max_pages}")
        logger.info(f"⚙️ Конфигурация: sparse={sparse}, backend={backend}")

        # Устанавливаем переменные окружения
        import os
        # Sparse векторы всегда включены в production
        os.environ["USE_SPARSE"] = "true"
        if backend != "auto":
            os.environ["EMBEDDINGS_BACKEND"] = backend

        # Показываем текущую конфигурацию
        logger.info(f"📊 Конфигурация эмбеддингов:")
        logger.info(f"  EMBEDDINGS_BACKEND: {CONFIG.embeddings_backend}")
        logger.info(f"  EMBEDDING_DEVICE: {CONFIG.embedding_device}")
        logger.info(f"  USE_SPARSE: {CONFIG.use_sparse}")
        logger.info(f"  EMBEDDING_MAX_LENGTH_DOC: {CONFIG.embedding_max_length_doc}")
        logger.info(f"  EMBEDDING_BATCH_SIZE: {CONFIG.embedding_batch_size}")

        # Определяем параметры для crawl_and_index
        if mode == "full" or force_full:
            incremental = False
            reindex_mode = "auto"
        elif mode == "incremental":
            incremental = True
            reindex_mode = "auto"
        elif mode == "cache_only":
            incremental = True
            reindex_mode = "cache_only"
        else:  # auto
            incremental = True
            reindex_mode = "auto"

        try:
            result = crawl_and_index(
                incremental=incremental,
                strategy=strategy,
                use_cache=use_cache,
                reindex_mode=reindex_mode,
                max_pages=max_pages
            )

            # Проверяем результат
            new_status = self.status()

            logger.success("✅ Переиндексация завершена!")
            logger.info(f"📊 Результат: {result}")
            logger.info(f"📈 Новое состояние: {new_status['total_points']} документов")

            return {
                "success": True,
                "result": result,
                "new_status": new_status
            }

        except Exception as e:
            logger.error(f"❌ Ошибка при переиндексации: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def init_collection(self, recreate: bool = False) -> Dict[str, Any]:
        """Инициализирует коллекцию Qdrant"""
        try:
            if recreate:
                logger.info("🔄 Пересоздаем коллекцию...")
                from scripts.init_qdrant import main as init_main
                init_main()
                logger.success("✅ Коллекция пересоздана")
            else:
                logger.info("🔧 Инициализируем коллекцию...")
                from scripts.init_qdrant import main as init_main
                init_main()
                logger.success("✅ Коллекция инициализирована")

            return {"success": True}

        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации: {e}")
            return {"success": False, "error": str(e)}


def main():
    """Главная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Production модуль для индексации edna Chat Center",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Проверить статус системы
  python scripts/indexer.py status

  # Полная переиндексация (рекомендуется)
  python scripts/indexer.py reindex --mode full

  # Инкрементальное обновление
  python scripts/indexer.py reindex --mode incremental

  # Использовать только кешированные страницы
  python scripts/indexer.py reindex --mode cache_only

  # Инициализировать коллекцию
  python scripts/indexer.py init

  # Пересоздать коллекцию
  python scripts/indexer.py init --recreate

  # Тестовая переиндексация (только 5 страниц)
  python scripts/indexer.py reindex --mode full --max-pages 5
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')

    # Команда status
    status_parser = subparsers.add_parser('status', help='Проверить статус системы')

    # Команда reindex
    reindex_parser = subparsers.add_parser('reindex', help='Выполнить переиндексацию')
    reindex_parser.add_argument(
        '--mode',
        choices=['auto', 'full', 'incremental', 'cache_only'],
        default='auto',
        help='Режим переиндексации (по умолчанию: auto)'
    )
    reindex_parser.add_argument(
        '--strategy',
        choices=['jina', 'browser', 'http'],
        default='jina',
        help='Стратегия краулинга (по умолчанию: jina)'
    )
    reindex_parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Не использовать кеш'
    )
    reindex_parser.add_argument(
        '--max-pages',
        type=int,
        help='Ограничить количество страниц (для тестирования)'
    )
    reindex_parser.add_argument(
        '--sparse',
        action='store_true',
        default=True,
        help='Включить sparse векторы (всегда включено)'
    )
    reindex_parser.add_argument(
        '--backend',
        choices=['auto', 'onnx', 'bge', 'hybrid'],
        default='auto',
        help='Backend для эмбеддингов (по умолчанию: auto)'
    )
    reindex_parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Размер батча для обработки (по умолчанию: 16)'
    )
    reindex_parser.add_argument(
        '--max-length',
        type=int,
        default=1024,
        help='Максимальная длина документов (по умолчанию: 1024)'
    )

    # Команда init
    init_parser = subparsers.add_parser('init', help='Инициализировать коллекцию')
    init_parser.add_argument(
        '--recreate',
        action='store_true',
        help='Пересоздать коллекцию'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Настраиваем логирование
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    indexer = Indexer()

    try:
        if args.command == 'status':
            status = indexer.status()

            print("\n📊 Статус системы индексации")
            print("=" * 50)

            if status.get("collection_exists"):
                print(f"✅ Коллекция: {CONFIG.qdrant_collection}")
                print(f"📈 Документов: {status['total_points']}")
                print(f"🎯 Sparse покрытие: {status['sparse_coverage']:.1f}%")
                print(f"📏 Размерность: {status['embedding_dim']}")
                print(f"⚙️ Backend: {status['backend']}")
                print(f"🔧 Sparse векторы: {'включены' if status['use_sparse'] else 'отключены'}")
                print(f"📝 Chunking: {status['chunk_config']}")

                if status['sparse_coverage'] < 100:
                    print("\n⚠️ Рекомендуется полная переиндексация для 100% sparse покрытия")
                else:
                    print("\n✅ Система готова к работе")
            else:
                print(f"❌ Ошибка: {status.get('error', 'Неизвестная ошибка')}")
                print("\n💡 Попробуйте: python scripts/indexer.py init")
                return 1

        elif args.command == 'reindex':
            # Устанавливаем переменные окружения для batch-size и max-length
            os.environ["EMBEDDING_BATCH_SIZE"] = str(args.batch_size)
            os.environ["EMBEDDING_MAX_LENGTH_DOC"] = str(args.max_length)

            result = indexer.reindex(
                mode=args.mode,
                strategy=args.strategy,
                use_cache=not args.no_cache,
                max_pages=args.max_pages,
                sparse=args.sparse,
                backend=args.backend
            )

            if result['success']:
                print("\n✅ Переиндексация завершена успешно!")
                return 0
            else:
                print(f"\n❌ Ошибка: {result['error']}")
                return 1

        elif args.command == 'init':
            result = indexer.init_collection(recreate=args.recreate)

            if result['success']:
                print("\n✅ Коллекция инициализирована!")
                return 0
            else:
                print(f"\n❌ Ошибка: {result['error']}")
                return 1

    except KeyboardInterrupt:
        logger.warning("⏹️ Операция прервана пользователем")
        return 130
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
