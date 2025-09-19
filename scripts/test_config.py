#!/usr/bin/env python3
"""
Тест конфигурации chunker'а.
"""

import sys
import os

# Добавляем корневую папку проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import CONFIG
from loguru import logger

logger.info(f"chunk_min_tokens: {CONFIG.chunk_min_tokens}")
logger.info(f"chunk_max_tokens: {CONFIG.chunk_max_tokens}")

# Рассчитываем оптимальные диапазоны
optimal_min = max(CONFIG.chunk_min_tokens, int(CONFIG.chunk_max_tokens * 0.5))
optimal_max = int(CONFIG.chunk_max_tokens * 0.8)

logger.info(f"optimal_min: {optimal_min}")
logger.info(f"optimal_max: {optimal_max}")
