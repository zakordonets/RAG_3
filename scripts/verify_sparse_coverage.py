#!/usr/bin/env python3
"""
Проверка покрытия sparse векторами в коллекции
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG
from qdrant_client import QdrantClient

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def check_sparse_coverage():
    """Проверяет, сколько точек содержат sparse векторы"""
    logger.info("🔍 Проверка покрытия sparse векторами")
    logger.info("=" * 60)

    client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)

    try:
        # Получаем информацию о коллекции
        collection_info = client.get_collection(CONFIG.qdrant_collection)
        total_points = collection_info.points_count

        logger.info(f"📋 Коллекция: {CONFIG.qdrant_collection}")
        logger.info(f"📊 Всего точек: {total_points}")

        if total_points == 0:
            logger.warning("⚠️ Коллекция пуста")
            return False

        # Проверяем первые 100 точек на наличие sparse векторов
        sample_size = min(100, total_points)
        logger.info(f"📊 Проверяем образец из {sample_size} точек...")

        # Получаем точки с векторами
        points = client.scroll(
            collection_name=CONFIG.qdrant_collection,
            limit=sample_size,
            with_vectors=True,
            with_payload=True
        )[0]

        sparse_count = 0
        dense_only_count = 0

        for i, point in enumerate(points):
            if hasattr(point, 'vector') and point.vector:
                if isinstance(point.vector, dict):
                    vector_types = list(point.vector.keys())
                    if 'sparse' in vector_types and 'dense' in vector_types:
                        sparse_count += 1
                    elif 'dense' in vector_types:
                        dense_only_count += 1
                else:
                    dense_only_count += 1

        logger.info(f"\n📊 Результаты проверки {sample_size} точек:")
        logger.info(f"   ✅ С dense + sparse: {sparse_count}")
        logger.info(f"   ⚠️ Только dense: {dense_only_count}")

        # Вычисляем процент покрытия
        coverage_percent = (sparse_count / sample_size) * 100

        if coverage_percent == 100:
            logger.success(f"🎉 Отличное покрытие: {coverage_percent:.1f}%")
        elif coverage_percent >= 90:
            logger.success(f"✅ Хорошее покрытие: {coverage_percent:.1f}%")
        elif coverage_percent >= 50:
            logger.warning(f"⚠️ Частичное покрытие: {coverage_percent:.1f}%")
        else:
            logger.error(f"❌ Низкое покрытие: {coverage_percent:.1f}%")

        # Проверяем конфигурацию коллекции
        logger.info(f"\n🔧 Проверка конфигурации коллекции:")

        if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
            params = collection_info.config.params
            if hasattr(params, 'vectors'):
                vectors_config = params.vectors

                # Проверяем dense векторы
                if hasattr(vectors_config, 'dense'):
                    dense_config = vectors_config.dense
                    logger.info(f"   ✅ Dense векторы: {dense_config.size} измерений")
                else:
                    logger.error("   ❌ Dense векторы не настроены")

                # Проверяем sparse векторы
                if hasattr(vectors_config, 'sparse'):
                    logger.info("   ✅ Sparse векторы: настроены")
                else:
                    logger.error("   ❌ Sparse векторы не настроены")

        return coverage_percent >= 90

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Основная функция"""
    success = check_sparse_coverage()

    if success:
        logger.success("\n🎉 Проверка завершена успешно!")
        logger.info("📋 Sparse векторы работают корректно")
    else:
        logger.error("\n❌ Проблемы с sparse векторами обнаружены")
        logger.info("📋 Рекомендации:")
        logger.info("   1. Убедитесь, что CONFIG.use_sparse = True")
        logger.info("   2. Проверьте, что CONFIG.embeddings_backend поддерживает sparse")
        logger.info("   3. Перезапустите переиндексацию")

    return success

if __name__ == "__main__":
    main()
