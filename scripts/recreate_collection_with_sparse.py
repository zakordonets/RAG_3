#!/usr/bin/env python3
"""
Полная замена коллекции с поддержкой sparse векторов
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def backup_collection_info():
    """Получает информацию о текущей коллекции"""
    logger.info("📊 Получение информации о текущей коллекции")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        logger.info(f"📋 Коллекция: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Количество точек: {collection_info.points_count}")
        logger.info(f"📊 Статус: {collection_info.status}")

        # Информация о векторах
        if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
            params = collection_info.config.params
            if hasattr(params, 'vectors'):
                vectors_config = params.vectors
                logger.info(f"📊 Конфигурация векторов: {vectors_config}")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при получении информации: {e}")
        return False

def delete_collection():
    """Удаляет старую коллекцию"""
    logger.info("\n🗑️ Удаление старой коллекции")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        # Проверяем, существует ли коллекция
        if client.collection_exists(CONFIG.qdrant_collection):
            logger.info(f"📋 Удаляем коллекцию: {CONFIG.qdrant_collection}")
            client.delete_collection(CONFIG.qdrant_collection)
            logger.success("✅ Коллекция успешно удалена")
        else:
            logger.info("ℹ️ Коллекция не существует")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при удалении коллекции: {e}")
        return False

def create_collection_with_sparse():
    """Создает новую коллекцию с поддержкой sparse векторов"""
    logger.info("\n🆕 Создание новой коллекции с sparse векторами")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        # Создаем коллекцию с поддержкой dense и sparse векторов
        # Используем отдельные параметры как в init_qdrant.py
        vectors_config = {"dense": VectorParams(size=CONFIG.embedding_dim, distance=Distance.COSINE)}
        sparse_vectors_config = {"sparse": SparseVectorParams()}

        logger.info(f"📋 Создаем коллекцию: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Dense векторы: {CONFIG.embedding_dim} измерений")
        logger.info(f"📊 Sparse векторы: включены")

        client.recreate_collection(
            collection_name=CONFIG.qdrant_collection,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config
        )

        logger.success("✅ Коллекция успешно создана с поддержкой sparse векторов")

        # Проверяем создание
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        logger.info(f"📊 Новая коллекция создана: {collection_info.status}")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при создании коллекции: {e}")
        return False

def verify_collection_config():
    """Проверяет конфигурацию новой коллекции"""
    logger.info("\n🔍 Проверка конфигурации коллекции")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        collection_info = client.get_collection(CONFIG.qdrant_collection)

        logger.info(f"📋 Коллекция: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Количество точек: {collection_info.points_count}")
        logger.info(f"📊 Статус: {collection_info.status}")

        # Проверяем конфигурацию векторов
        if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
            params = collection_info.config.params
            if hasattr(params, 'vectors'):
                vectors_config = params.vectors

                # Проверяем dense векторы
                if hasattr(vectors_config, 'dense'):
                    dense_config = vectors_config.dense
                    logger.success(f"✅ Dense векторы: {dense_config.size} измерений")

                # Проверяем sparse векторы
                if hasattr(vectors_config, 'sparse'):
                    sparse_config = vectors_config.sparse
                    logger.success("✅ Sparse векторы: включены")
                else:
                    logger.warning("⚠️ Sparse векторы: не найдены")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке коллекции: {e}")
        return False

def main():
    """Основная функция"""
    logger.info("🚀 Полная замена коллекции с sparse векторами")
    logger.info("=" * 60)

    # Шаг 1: Получаем информацию о текущей коллекции (если существует)
    try:
        backup_collection_info()
    except:
        logger.info("ℹ️ Коллекция не существует, пропускаем получение информации")

    # Подтверждение от пользователя
    logger.warning("\n⚠️ ВНИМАНИЕ: Это действие удалит все данные в коллекции!")
    response = input("Продолжить? (y/N): ").strip().lower()

    if response not in ['y', 'yes', 'да', 'д']:
        logger.info("❌ Операция отменена пользователем")
        return False

    # Шаг 2: Удаляем старую коллекцию
    if not delete_collection():
        logger.error("❌ Не удалось удалить старую коллекцию")
        return False

    # Шаг 3: Создаем новую коллекцию
    if not create_collection_with_sparse():
        logger.error("❌ Не удалось создать новую коллекцию")
        return False

    # Шаг 4: Проверяем конфигурацию
    if not verify_collection_config():
        logger.error("❌ Не удалось проверить конфигурацию")
        return False

    logger.success("\n🎉 Коллекция успешно заменена!")
    logger.info("📋 Следующие шаги:")
    logger.info("   1. Запустите полную переиндексацию: python scripts/full_reindex.py")
    logger.info("   2. Проверьте результат: python scripts/verify_sparse_coverage.py")

    return True

if __name__ == "__main__":
    main()
