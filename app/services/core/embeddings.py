"""
Сервис унифицированных эмбеддингов BGE-M3

Предоставляет унифицированную генерацию плотных и разреженных эмбеддингов
с использованием модели BAAI/bge-m3. Поддерживает CPU, CUDA и DirectML
(Windows/AMD) бэкенды с автоматическими fallback'ами.

Основные возможности:
- Генерация плотных векторов (1024 размерности)
- Генерация разреженных векторов (lexical weights)
- Генерация ColBERT векторов для реранкинга
- Поддержка batch обработки для оптимизации производительности
- Автоматический выбор оптимального бэкенда
- Кэширование результатов для ускорения повторных запросов
"""
from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional, Any

from loguru import logger

try:
    # Финализаторы FlagEmbedding могут выполняться во время завершения интерпретатора, когда модули уже очищены.
    from FlagEmbedding.abc.inference import AbsEmbedder
except ModuleNotFoundError:  # pragma: no cover - опциональная зависимость не установлена
    AbsEmbedder = None
else:  # pragma: no cover - защитный патч от ошибок завершения библиотеки
    def _safe_abs_embedder_del(self) -> None:
        try:
            self.stop_self_pool()
        except Exception:
            # Во время завершения интерпретатора модули как gc могут быть уже очищены.
            pass

    AbsEmbedder.__del__ = _safe_abs_embedder_del  # type: ignore[assignment]

from app.config import CONFIG
from app.infrastructure import cache_embedding

# Совместимость с Windows для HuggingFace Hub
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

# Глобальные экземпляры моделей (singleton pattern)
_bge_model = None  # Экземпляр BGE-M3 модели
_bge_lock = threading.Lock()  # Блокировка для thread-safe доступа к BGE модели

# Fallback для различных бэкендов
_onnx_embedder = None  # ONNX инференс сессия
_onnx_tokenizer = None  # ONNX токенизатор
_onnx_lock = threading.Lock()  # Блокировка для thread-safe доступа к ONNX компонентам


def _determine_device() -> str:
    """
    Определяет оптимальное устройство на основе конфигурации и доступности.

    Returns:
        str: Название устройства ('cpu', 'cuda', 'directml')
    """
    device_config = CONFIG.embedding_device

    if device_config == "auto":
        # Логика автоматического определения устройства
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

        # Проверка доступности DirectML (Windows/AMD)
        try:
            import onnxruntime as ort
            if "DmlExecutionProvider" in ort.get_available_providers():
                logger.info("DirectML обнаружен, но BGE-M3 не поддерживает DirectML напрямую. Используем CPU для BGE-M3.")
                return "cpu"
        except ImportError:
            pass

        return "cpu"

    # Явная конфигурация устройства
    if device_config in ["cuda", "cpu"]:
        return device_config
    elif device_config == "directml":
        logger.warning("DirectML не поддерживается напрямую BGE-M3. Переключаемся на CPU.")
        return "cpu"
    else:
        logger.warning(f"Неизвестное устройство '{device_config}'. Переключаемся на CPU.")
        return "cpu"


def _get_optimal_backend_strategy() -> str:
    """
    Определяет оптимальную стратегию бэкенда на основе возможностей системы.

    Returns:
        str: Рекомендуемый бэкенд ('onnx', 'bge', или 'hybrid')
    """
    # Если пользователь явно установил бэкенд, уважаем его выбор
    if CONFIG.embeddings_backend != "auto":
        return CONFIG.embeddings_backend

    # Логика автоматического определения оптимальной стратегии
    has_cuda = False
    has_directml = False

    # Проверка доступности CUDA
    try:
        import torch
        has_cuda = torch.cuda.is_available()
        if has_cuda:
            logger.info("CUDA обнаружен - BGE-M3 может использовать GPU ускорение")
    except ImportError:
        pass

    # Проверка доступности DirectML
    try:
        import onnxruntime as ort
        has_directml = "DmlExecutionProvider" in ort.get_available_providers()
        if has_directml:
            logger.info("DirectML обнаружен - ONNX может использовать GPU ускорение")
    except ImportError:
        pass

    # Определение оптимальной стратегии
    if has_cuda:
        # NVIDIA GPU: BGE-M3 может использовать CUDA напрямую
        logger.info("Оптимальная стратегия: BGE бэкенд (CUDA ускорение)")
        return "bge"
    elif has_directml:
        # AMD GPU на Windows: Гибридный подход (ONNX+DML для плотных, BGE+CPU для разреженных)
        logger.info("Оптимальная стратегия: Гибридный бэкенд (DirectML + CPU)")
        return "hybrid"
    else:
        # Только CPU: Используем ONNX для консистентности
        logger.info("Оптимальная стратегия: ONNX бэкенд (только CPU)")
        return "onnx"


def _get_bge_model():
    """
    Получает singleton экземпляр BGE-M3 модели с оптимизированными настройками.

    Returns:
        BGEM3FlagModel: Экземпляр BGE-M3 модели или None в случае ошибки
    """
    global _bge_model
    if _bge_model is None:
        with _bge_lock:
            if _bge_model is None:
                try:
                    from FlagEmbedding import BGEM3FlagModel

                    device = _determine_device()
                    logger.info(f"Загружаем BGE-M3 модель на устройство: {device}")

                    _bge_model = BGEM3FlagModel(
                        'BAAI/bge-m3',
                        use_fp16=CONFIG.embedding_use_fp16 and device != "cpu",  # FP16 только на GPU
                        device=device,
                        normalize_embeddings=CONFIG.embedding_normalize,
                        query_instruction_for_retrieval=None,  # Не нужно для документации
                        passage_instruction_for_retrieval=None
                    )
                    logger.info(f"BGE-M3 модель успешно загружена на {device}")

                except Exception as e:
                    logger.error(f"Не удалось загрузить BGE-M3 модель: {e}")
                    logger.info("BGE-M3 модель будет недоступна. Fallback на ONNX если настроен.")
                    _bge_model = None

    return _bge_model


def _get_onnx_embedder():
    """
    Получает ONNX эмбеддер как запасной вариант (из существующей реализации).

    Returns:
        tuple: (InferenceSession, AutoTokenizer) или (None, None) в случае ошибки
    """
    global _onnx_embedder, _onnx_tokenizer
    if _onnx_embedder is None:
        with _onnx_lock:
            if _onnx_embedder is None:
                try:
                    from transformers import AutoTokenizer
                    import onnxruntime as ort
                    from onnxruntime.capi.onnxruntime_inference_collection import InferenceSession
                    import numpy as np

                    model_path = "models/onnx/bge-m3"
                    if not os.path.exists(os.path.join(model_path, "model.onnx")):
                        logger.error(f"ONNX модель не найдена в {model_path}. Запустите скрипт экспорта сначала.")
                        return None, None

                    logger.info(f"Загружаем ONNX эмбеддер из {model_path}...")

                    # Определяем ONNX Runtime провайдер на основе конфигурации
                    providers = []
                    if CONFIG.onnx_provider == "dml" or (CONFIG.onnx_provider == "auto" and "DmlExecutionProvider" in ort.get_available_providers()):
                        providers.append("DmlExecutionProvider")
                        logger.info("Используем DmlExecutionProvider для ONNX эмбеддингов.")
                    providers.append("CPUExecutionProvider")  # Всегда добавляем CPU как запасной вариант

                    _onnx_embedder = InferenceSession(
                        os.path.join(model_path, "model.onnx"),
                        providers=providers
                    )
                    _onnx_tokenizer = AutoTokenizer.from_pretrained(model_path)
                    logger.info("ONNX эмбеддер успешно загружен.")

                except Exception as e:
                    logger.error(f"Не удалось загрузить ONNX эмбеддер: {e}")
                    _onnx_embedder = None
                    _onnx_tokenizer = None

    return _onnx_embedder, _onnx_tokenizer


def get_optimal_max_length(text: str, context: str = "query") -> int:
    """
    Автоматически выбирает оптимальную max_length на основе текста и контекста.

    Args:
        text: Входной текст
        context: Контекст использования ("query" или "document")

    Returns:
        int: Оптимальная максимальная длина в токенах
    """
    text_len = len(text)

    if context == "query":
        if text_len < 100:
            return 256    # Очень короткие запросы
        elif text_len < 300:
            return 512   # Обычные запросы
        else:
            return 1024  # Длинные запросы

    elif context == "document":
        if text_len < 500:
            return 512    # Короткие чанки
        elif text_len < 2000:
            return 1024  # Средние чанки
        else:
            return 2048  # Длинные чанки

    return 1024  # Fallback


@cache_embedding(ttl=3600)
def embed_unified(
    text: str,
    max_length: Optional[int] = None,
    return_dense: bool = True,
    return_sparse: bool = True,
    return_colbert: bool = False,
    context: str = "query"
) -> Dict[str, Any]:
    """
    Унифицированная генерация всех типов эмбеддингов BGE-M3.

    Args:
        text: Входной текст
        max_length: Максимальная длина в токенах (None = автоопределение)
        return_dense: Генерировать плотные векторы (1024 размерности)
        return_sparse: Генерировать разреженные векторы
        return_colbert: Генерировать ColBERT векторы (для реранкинга)
        context: Подсказка контекста для оптимизации ("query" или "document")

    Returns:
        Dict с ключами: dense_vecs, lexical_weights, colbert_vecs
    """
    # Определяем бэкенд на основе конфигурации и возможностей системы
    backend = _get_optimal_backend_strategy()

    if backend == "onnx":
        return _embed_unified_onnx(text, max_length, return_dense, return_sparse, context)
    elif backend == "bge":
        return _embed_unified_bge(text, max_length, return_dense, return_sparse, return_colbert, context)
    elif backend == "hybrid":
        return _embed_unified_hybrid(text, max_length, return_dense, return_sparse, return_colbert, context)
    else:
        logger.error(f"Неизвестный бэкенд эмбеддингов: {backend}")
        return _get_empty_result(return_dense, return_sparse, return_colbert)


def _embed_unified_onnx(
    text: str,
    max_length: Optional[int],
    return_dense: bool,
    return_sparse: bool,
    context: str
) -> Dict[str, Any]:
    """Генерация эмбеддингов только через ONNX, используя общую логику обработки."""
    if max_length is None:
        max_length = get_optimal_max_length(text, context)

    # Используем общую логику обработки ONNX
    result = _process_onnx_embedding([text], max_length, return_dense, return_sparse)

    # Преобразуем в формат одного элемента для совместимости
    return {
        "dense_vecs": result["dense_vecs"],
        "lexical_weights": result["lexical_weights"],
        "colbert_vecs": None
    }


def _embed_unified_bge(
    text: str,
    max_length: Optional[int],
    return_dense: bool,
    return_sparse: bool,
    return_colbert: bool,
    context: str
) -> Dict[str, Any]:
    """Генерация эмбеддингов через нативный BGE-M3, используя общую логику обработки."""
    if max_length is None:
        max_length = get_optimal_max_length(text, context)

    # Используем общую логику обработки BGE
    return _process_bge_embedding([text], max_length, return_dense, return_sparse, return_colbert)


def _embed_unified_hybrid(
    text: str,
    max_length: Optional[int],
    return_dense: bool,
    return_sparse: bool,
    return_colbert: bool,
    context: str
) -> Dict[str, Any]:
    """Гибридный подход: ONNX для плотных (GPU), BGE-M3 для разреженных (CPU)."""
    if max_length is None:
        max_length = get_optimal_max_length(text, context)

    result = {"dense_vecs": None, "lexical_weights": None, "colbert_vecs": None}

    # Плотные через ONNX (может использовать DirectML на Windows/AMD)
    if return_dense:
        onnx_result = _process_onnx_embedding([text], max_length, True, False)
        result["dense_vecs"] = onnx_result["dense_vecs"]

    # Разреженные через BGE-M3 (CPU)
    if return_sparse or return_colbert:
        bge_result = _process_bge_embedding([text], max_length, False, return_sparse, return_colbert)
        result["lexical_weights"] = bge_result["lexical_weights"]
        result["colbert_vecs"] = bge_result["colbert_vecs"]

        # Преобразуем lexical_weights в формат sparse векторов для поиска
        if "lexical_weights" in bge_result and bge_result["lexical_weights"]:
            lexical_weights = bge_result["lexical_weights"][0]
            if isinstance(lexical_weights, dict) and lexical_weights:
                # Преобразуем словарь в indices/values формат
                indices = list(lexical_weights.keys())
                values = list(lexical_weights.values())
                result["sparse_vecs"] = [{"indices": indices, "values": values}]

    return result


def _get_empty_result(return_dense: bool, return_sparse: bool, return_colbert: bool) -> Dict[str, Any]:
    """Генерирует пустую структуру результата для запасных случаев."""
    return {
        'dense_vecs': [[0.0] * 1024] if return_dense else None,
        'lexical_weights': [{}] if return_sparse else None,
        'colbert_vecs': [[[0.0] * 1024]] if return_colbert else None
    }


def _normalize_texts(texts: List[str]) -> List[str]:
    """Нормализует и валидирует входные тексты для безопасной обработки."""
    safe_texts = []
    for text in texts:
        if not isinstance(text, str):
            text = str(text)
        try:
            # Проверяем и исправляем кодировку
            text.encode('utf-8')
            safe_texts.append(text)
        except UnicodeEncodeError:
            # Исправляем проблемные символы
            safe_text = text.encode('utf-8', errors='ignore').decode('utf-8')
            safe_texts.append(safe_text)
        except Exception:
            # Последний запасной вариант
            safe_texts.append(str(text).encode('utf-8', errors='ignore').decode('utf-8'))
    return safe_texts


def _process_onnx_embedding(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """Общая логика обработки ONNX эмбеддингов для одиночного и пакетного режимов."""
    results = {'dense_vecs': [], 'lexical_weights': []}

    if not return_dense:
        if return_sparse:
            results['lexical_weights'] = [{}] * len(texts)
        return results

    embedder, tokenizer = _get_onnx_embedder()
    if embedder is None or tokenizer is None:
        logger.error("ONNX embedder not available")
        if return_dense:
            results['dense_vecs'] = [[0.0] * 1024] * len(texts)
        if return_sparse:
            results['lexical_weights'] = [{}] * len(texts)
        return results

    try:
        import numpy as np

        # Нормализуем тексты для безопасной обработки
        safe_texts = _normalize_texts(texts)

        inputs = tokenizer(
            safe_texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="np"
        )

        # Подготавливаем словарь входных данных - обеспечиваем int64 для ONNX
        input_dict = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }
        # Добавляем token_type_ids только если они есть в выводе токенизатора
        if "token_type_ids" in inputs:
            input_dict["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)

        outputs = embedder.run(None, input_dict)
        embeddings = outputs[0]

        # Среднее пулинга для получения финальных эмбеддингов
        input_mask_expanded = np.expand_dims(inputs["attention_mask"], axis=-1).astype(float)
        sum_embeddings = np.sum(embeddings * input_mask_expanded, axis=1)
        sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_embeddings = sum_embeddings / sum_mask

        # Нормализуем эмбеддинги если настроено
        if CONFIG.embedding_normalize:
            norm = np.linalg.norm(mean_embeddings, axis=1, keepdims=True)
            mean_embeddings = mean_embeddings / norm

        # Преобразуем в формат списка
        dense_vecs = []
        for i in range(len(mean_embeddings)):
            dense_vecs.append(mean_embeddings[i].tolist())
        results['dense_vecs'] = dense_vecs

        logger.debug(f"ONNX обработка эмбеддингов завершена: {len(texts)} текстов, max_length={max_length}")

    except Exception as e:
        logger.error(f"ONNX обработка эмбеддингов не удалась: {e}")
        if return_dense:
            results['dense_vecs'] = [[0.0] * 1024] * len(texts)
        if return_sparse:
            results['lexical_weights'] = [{}] * len(texts)

    if return_sparse:
        logger.warning("ONNX бэкенд не поддерживает разреженные эмбеддинги")
        results['lexical_weights'] = [{}] * len(texts)

    return results


def _process_bge_embedding(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool, return_colbert: bool = False) -> Dict[str, List]:
    """Общая логика обработки BGE-M3 эмбеддингов для одиночного и пакетного режимов."""
    model = _get_bge_model()
    if model is None:
        logger.error("BGE-M3 модель недоступна")
        return _get_empty_result(return_dense, return_sparse, return_colbert)

    try:
        output = model.encode(
            texts,
            max_length=max_length,
            return_dense=return_dense,
            return_sparse=return_sparse,
            return_colbert_vecs=return_colbert
        )

        logger.debug(f"BGE-M3 кодирование завершено: {len(texts)} текстов, max_length={max_length}, "
                    f"dense={return_dense}, sparse={return_sparse}, colbert={return_colbert}")

        return output

    except Exception as e:
        logger.error(f"BGE-M3 кодирование не удалось: {e}")
        return _get_empty_result(return_dense, return_sparse, return_colbert)


def embed_dense_optimized(text: str, max_length: Optional[int] = None) -> List[float]:
    """Оптимизированная генерация плотных эмбеддингов."""
    result = embed_unified(text, max_length=max_length, return_dense=True, return_sparse=False, context="query")
    return result['dense_vecs'][0] if result['dense_vecs'] else [0.0] * 1024


def embed_sparse_optimized(text: str, max_length: Optional[int] = None) -> Dict[str, List]:
    """Оптимизированная генерация разреженных эмбеддингов."""
    result = embed_unified(text, max_length=max_length, return_dense=False, return_sparse=True, context="query")

    if not result.get('lexical_weights') or not result['lexical_weights'][0]:
        return {"indices": [], "values": []}

    # Преобразуем в формат Qdrant
    lex_weights = result['lexical_weights'][0]
    indices = list(lex_weights.keys())
    values = list(lex_weights.values())

    return {"indices": indices, "values": values}


def embed_batch_optimized(
    texts: List[str],
    max_length: Optional[int] = None,
    return_dense: bool = True,
    return_sparse: bool = True,
    context: str = "document"
) -> Dict[str, List]:
    """Пакетная генерация эмбеддингов для максимальной эффективности."""
    if not texts:
        return {'dense_vecs': [], 'lexical_weights': []}

    backend = _get_optimal_backend_strategy()

    # Автооптимизация max_length для пакетной обработки
    if max_length is None:
        avg_length = sum(len(text) for text in texts) / len(texts)
        max_length = get_optimal_max_length("x" * int(avg_length), context)

    if backend == "bge":
        return _embed_batch_bge(texts, max_length, return_dense, return_sparse)
    elif backend == "onnx":
        return _embed_batch_onnx(texts, max_length, return_dense, return_sparse)
    elif backend == "hybrid":
        return _embed_batch_hybrid(texts, max_length, return_dense, return_sparse)
    else:
        logger.error(f"Неизвестный бэкенд для пакетной обработки: {backend}")
        return {'dense_vecs': [], 'lexical_weights': []}


def _embed_batch_bge(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """BGE-M3 пакетная обработка, используя общую логику обработки."""
    result = _process_bge_embedding(texts, max_length, return_dense, return_sparse, False)
    logger.info(f"BGE-M3 пакетное кодирование завершено: {len(texts)} текстов, max_length={max_length}")
    return result


def _embed_batch_onnx(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """ONNX пакетная обработка, используя общую логику обработки."""
    result = _process_onnx_embedding(texts, max_length, return_dense, return_sparse)
    logger.info(f"ONNX пакетная обработка завершена: {len(texts)} текстов")
    return result


def _embed_batch_hybrid(texts: List[str], max_length: int, return_dense: bool, return_sparse: bool) -> Dict[str, List]:
    """Гибридная пакетная обработка, используя общую логику обработки."""
    results = {'dense_vecs': [], 'lexical_weights': []}

    # Плотные через ONNX
    if return_dense:
        onnx_result = _process_onnx_embedding(texts, max_length, True, False)
        results['dense_vecs'] = onnx_result['dense_vecs']

    # Разреженные через BGE-M3
    if return_sparse:
        bge_result = _process_bge_embedding(texts, max_length, False, True, False)
        results['lexical_weights'] = bge_result['lexical_weights']

    return results


# Функции обратной совместимости
def embed_dense(text: str) -> List[float]:
    """Legacy функция для обратной совместимости."""
    return embed_dense_optimized(text)
