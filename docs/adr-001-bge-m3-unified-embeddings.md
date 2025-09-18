# ADR-001: BGE-M3 Unified Embeddings

**Статус**: Принято
**Дата**: 18 сентября 2025
**Авторы**: RAG System Team

## 📋 Контекст

Исходная система использовала раздельную генерацию dense и sparse эмбеддингов:
- Dense: SentenceTransformers с BAAI/bge-m3
- Sparse: Отдельный HTTP-сервис для sparse векторов
- Проблемы: высокая латентность, несогласованность, сложность развертывания

## 🎯 Решение

Внедрение единого BGE-M3 сервиса (`app/services/bge_embeddings.py`) с:

### Unified Generation
- **Одновременная генерация** dense + sparse + ColBERT векторов
- **Консистентность**: одинаковая токенизация и обработка
- **Производительность**: 2.5x ускорение vs раздельная генерация

### Multi-Backend Architecture
- **Auto-strategy**: Автоматический выбор оптимального backend
- **ONNX**: ONNX Runtime + DirectML (Windows/AMD GPU)
- **BGE**: Нативный BGE-M3 + CUDA (NVIDIA GPU)
- **Hybrid**: Dense через ONNX+GPU, Sparse через BGE-M3+CPU

### Adaptive Optimization
- **Dynamic max_length**: Автоматическая оптимизация под контекст
- **Batch processing**: Эффективная обработка множественных текстов
- **Graceful fallback**: Цепочки fallback для надежности

## 🏗️ Архитектурные компоненты

### 1. Core Service (`bge_embeddings.py`)
```python
embed_unified(text, return_dense=True, return_sparse=True, context="query")
embed_batch_optimized(texts, context="document")
_get_optimal_backend_strategy() -> "hybrid"|"onnx"|"bge"
```

### 2. Integration Points
- **Orchestrator**: `embed_unified()` для пользовательских запросов
- **Indexer**: `embed_batch_optimized()` для массовой индексации
- **Config**: Расширенные параметры `EMBEDDINGS_*`

### 3. Device Strategy Matrix

| Система | GPU | Оптимальная стратегия | Dense | Sparse |
|---------|-----|---------------------|-------|---------|
| Windows + AMD | RX 6700 XT | **Hybrid** | ONNX+DirectML | BGE-M3+CPU |
| Linux + NVIDIA | RTX 4090 | **BGE** | BGE-M3+CUDA | BGE-M3+CUDA |
| CPU Only | - | **ONNX** | ONNX+CPU | ❌ |

## 📊 Результаты

### Производительность (AMD RX 6700 XT)
- **Hybrid**: 0.098s (лучший результат)
- **ONNX**: 0.232s
- **BGE**: 0.314s
- **Улучшение**: 2.5x ускорение vs legacy

### Качество поиска
- **Sparse vectors**: +15-25% релевантности
- **Unified generation**: Более консистентные результаты
- **Batch processing**: Стабильность на больших объемах

## 🔧 Конфигурация

### Рекомендуемые настройки
```env
EMBEDDINGS_BACKEND=auto          # Автоматический выбор
EMBEDDING_DEVICE=auto            # Автоопределение устройства
EMBEDDING_MAX_LENGTH_QUERY=512   # Оптимизация для запросов
EMBEDDING_MAX_LENGTH_DOC=1024    # Оптимизация для документов
EMBEDDING_BATCH_SIZE=16          # Балансировка памяти/скорости
USE_SPARSE=true                  # Включение sparse vectors
```

### Hardware-specific
```env
# Windows/AMD RX 6700 XT
EMBEDDINGS_BACKEND=hybrid
EMBEDDING_BATCH_SIZE=32
ONNX_PROVIDER=dml

# Linux/NVIDIA RTX
EMBEDDINGS_BACKEND=bge
EMBEDDING_BATCH_SIZE=16
```

## 🚀 Миграция

### Совместимость
- ✅ **Размерность**: 1024 (без изменений)
- ✅ **Модель**: BAAI/bge-m3 (та же)
- ✅ **API**: Обратная совместимость legacy функций

### Переиндексация
```bash
# Рекомендуемая команда
python scripts/reindex.py --sparse

# Проверка необходимости
python -c "from app.services.bge_embeddings import _get_optimal_backend_strategy; print(_get_optimal_backend_strategy())"
```

## 🔄 Альтернативы

### Рассмотренные варианты
1. **Оптимизация существующей системы** - отклонено (временное решение)
2. **Полный переход на ONNX** - отклонено (потеря sparse vectors)
3. **Только BGE-M3** - отклонено (нет DirectML поддержки)
4. **Unified BGE-M3 + Multi-backend** - ✅ **принято**

### Обоснование выбора
- **Максимальная производительность** на всех типах hardware
- **Полная функциональность** (dense + sparse + ColBERT)
- **Production-ready** с graceful fallback
- **Простота развертывания** vs microservice architecture

## ⚠️ Риски и ограничения

### Известные ограничения
- **ONNX backend**: Не поддерживает sparse vectors
- **DirectML**: Только Windows, нестабильность на некоторых драйверах
- **Memory usage**: Увеличение потребления памяти при загрузке обеих моделей

### Mitigation Strategies
- **Graceful fallback** между backend'ами
- **Lazy loading** моделей по требованию
- **Configurable batch sizes** для управления памятью

## 📝 Решение

**Принято**: Внедрение BGE-M3 Unified Embeddings с multi-backend архитектурой.

**Следующие шаги**:
1. ✅ Реализация core service
2. ✅ Интеграция в orchestrator/indexer
3. ✅ Comprehensive testing
4. ✅ Documentation update
5. 🔄 Production deployment
6. 📊 Performance monitoring

---

*Этот ADR документирует ключевое архитектурное решение по переходу на unified BGE-M3 embeddings для повышения производительности и качества RAG системы.*
