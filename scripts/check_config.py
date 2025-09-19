#!/usr/bin/env python3
"""
Проверка конфигурации
"""
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import CONFIG

# Настраиваем логирование
logger.remove()
logger.add(sys.stderr, level="INFO")

def check_config():
    """Проверяет конфигурацию"""

    logger.info("🔧 Проверка конфигурации")
    logger.info("=" * 60)

    logger.info(f"📋 CONFIG.use_sparse: {CONFIG.use_sparse}")
    logger.info(f"📋 CONFIG.embeddings_backend: {CONFIG.embeddings_backend}")
    logger.info(f"📋 CONFIG.embedding_device: {CONFIG.embedding_device}")
    logger.info(f"📋 CONFIG.embedding_normalize: {CONFIG.embedding_normalize}")
    logger.info(f"📋 CONFIG.embedding_use_fp16: {CONFIG.embedding_use_fp16}")

if __name__ == "__main__":
    check_config()
