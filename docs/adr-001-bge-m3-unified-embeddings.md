# ADR-001: BGE-M3 Unified Embeddings

## Статус
✅ **Принято и реализовано**

## Метаданные
- **Дата решения**: 18 сентября 2024
- **Дата реализации**: Октябрь 2024
- **Версия**: v4.2.0+
- **Авторы**: RAG System Team

---

## Контекст и проблема

### Исходная ситуация

Система использовала **раздельную генерацию** embeddings:

| Тип | Технология | Проблемы |
|-----|------------|----------|
| **Dense** | SentenceTransformers + BGE-M3 | Отдельный процесс |
| **Sparse** | Внешний HTTP-сервис | Сетевая латентность, отказоустойчивость |

### Критические проблемы

1. **Производительность**: 2x latency из-за раздельных вызовов
2. **Несогласованность**: Разная токенизация dense vs sparse
3. **Сложность**: Два сервиса вместо одного
4. **Отказоустойчивость**: Single point of failure (sparse service)

---

## Решение

### Unified BGE-M3 Service

**Одновременная генерация** dense + sparse векторов через единый сервис.

**Архитектура**:
```python
# app/services/core/embeddings.py

def embed_unified(text, return_dense=True, return_sparse=True):
    """
    Единый вызов для dense + sparse.
    Использует одну модель BGE-M3 для обоих типов векторов.
    """
    # Dense: 1024 dim vector
    # Sparse: {indices: [...], values: [...]}
    return {"dense": dense_vec, "sparse": sparse_vec}
```

### Multi-Backend Support

| Backend | GPU | Использование |
|---------|-----|---------------|
| **ONNX + DirectML** | AMD/Intel | Windows оптимизация |
| **BGE + CUDA** | NVIDIA | Linux production |
| **Hybrid** | Mixed | Dense GPU + Sparse CPU |

**Auto-selection** на основе доступного hardware.

---

## Обоснование

### Почему unified подход?

1. **Производительность**: 2.5x ускорение (single model load)
2. **Консистентность**: Одинаковая токенизация и preprocessing
3. **Простота**: Один сервис вместо двух
4. **Надежность**: Меньше точек отказа

### Почему BGE-M3?

- ✅ State-of-the-art качество (MTEB benchmark)
- ✅ Поддержка dense + sparse natively
- ✅ Multilingual (100+ languages)
- ✅ Оптимизирован для retrieval задач

---

## Альтернативы

### Рассмотренные варианты

| Вариант | Плюсы | Минусы | Решение |
|---------|-------|--------|---------|
| **Оптимизация существующей** | Минимальные изменения | Временное решение | ❌ Отклонено |
| **Только ONNX** | Максимальная скорость | Нет sparse support | ❌ Отклонено |
| **Только BGE-M3** | Простота | Нет DirectML на Windows | ❌ Отклонено |
| **Unified + Multi-backend** | Best of all worlds | Сложность | ✅ **Принято** |

---

## Последствия

### Положительные

- ✅ **Производительность**: 2.5x ускорение embedding generation
- ✅ **Качество поиска**: +15-25% релевантности благодаря sparse
- ✅ **Простота**: Один сервис вместо двух
- ✅ **Отказоустойчивость**: Graceful fallback между backends

### Риски и ограничения

- ⚠️ **ONNX backend**: Не поддерживает sparse vectors
- ⚠️ **DirectML**: Только Windows, нестабильность на старых драйверах
- ⚠️ **Memory**: Увеличение потребления RAM при загрузке моделей

### Mitigation

- Graceful fallback между backends
- Lazy loading моделей
- Configurable batch sizes для контроля памяти

---

## Статус реализации

- ✅ Core service реализован
- ✅ Интеграция в orchestrator/retrieval
- ✅ Comprehensive testing
- ✅ Production deployment
- ✅ Monitoring в Grafana

**Результат**: Решение успешно внедрено и работает в production.

---

## Связанные документы

- [Technical Specification](technical_specification.md#4-embeddings) - Технические детали
- [Architecture](architecture.md) - Общая архитектура
- ADR-002: Adaptive Chunking Strategy

---

**Последнее обновление**: 9 октября 2024
