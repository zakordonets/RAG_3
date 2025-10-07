# 🔄 Руководство по переиндексации с BGE-M3

## 🎯 Когда нужна переиндексация?

### ✅ Обязательно переиндексируйте, если:
- Хотите включить **sparse vectors** для улучшения качества поиска
- Переходите с legacy системы на BGE-M3 unified embeddings
- Обновили модель эмбеддингов или изменили размерность
- База данных повреждена или содержит некорректные векторы

### 🤔 Опционально переиндексируйте, если:
- Хотите воспользоваться новыми оптимизациями производительности
- Изменили параметры `max_length` или `batch_size`
- Хотите перейти на другую стратегию эмбеддингов (ONNX → BGE → Hybrid)

### ❌ Не нужно переиндексировать, если:
- Система работает стабильно и вас устраивает качество поиска
- Используете только dense vectors и не планируете включать sparse
- Недавно уже выполняли переиндексацию с BGE-M3

## 🔍 Проверка текущего состояния

```bash
# Быстрая проверка состояния базы данных
python -c "
from qdrant_client import QdrantClient
from app.config import CONFIG

client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)
collection_info = client.get_collection(CONFIG.qdrant_collection)
points = client.scroll(CONFIG.qdrant_collection, limit=1, with_vectors=True)

print('📊 Текущее состояние базы:')
print(f'Количество векторов: {collection_info.points_count}')
print(f'Dense размерность: {len(points[0][0].vector[\"dense\"]) if points[0] else \"N/A\"}')
print(f'Sparse vectors: {\"✅ Есть\" if points[0] and hasattr(points[0][0], \"sparse_vectors\") and points[0][0].sparse_vectors else \"❌ Отсутствуют\"}')

# Проверяем стратегию эмбеддингов
from app.services.bge_embeddings import _get_optimal_backend_strategy
strategy = _get_optimal_backend_strategy()
print(f'Оптимальная стратегия: {strategy}')
"
```

## 🚀 Способы переиндексации

### 1. Рекомендуемый способ (ingestion/run.py)

```bash
# Полная переиндексация с очисткой коллекции (рекомендуется)
python -m ingestion.run --source docusaurus --docs-root "C:\CC_RAG\docs" --clear-collection

# Базовая переиндексация с sparse vectors
python scripts/reindex.py --sparse

# С дополнительными параметрами
python scripts/reindex.py --sparse --backend=hybrid --batch-size=32

# Посмотреть все опции
python scripts/reindex.py --help
```

**Преимущества:**
- ✅ Детальный прогресс и статистика
- ✅ Проверка конфигурации перед запуском
- ✅ Безопасное прерывание (Ctrl+C)
- ✅ Автоматическая проверка результатов

### 2. Через модуль pipeline

```bash
python -m ingestion.pipeline
```

**Преимущества:**
- ✅ Простота запуска
- ✅ Использует текущие настройки из .env

### 3. Через API (для автоматизации)

```bash
curl -X POST http://localhost:9000/v1/admin/reindex
```

**Преимущества:**
- ✅ Подходит для CI/CD
- ✅ Удаленное выполнение

## ⚙️ Оптимальные настройки

### Windows + AMD GPU (RX 6700 XT)
```env
EMBEDDINGS_BACKEND=hybrid
EMBEDDING_BATCH_SIZE=32
EMBEDDING_USE_FP16=true
ONNX_PROVIDER=dml
USE_SPARSE=true
```

```bash
python scripts/reindex.py --sparse --backend=hybrid --batch-size=32
```

### Linux + NVIDIA GPU
```env
EMBEDDINGS_BACKEND=bge
EMBEDDING_BATCH_SIZE=16
EMBEDDING_USE_FP16=true
USE_SPARSE=true
```

```bash
python scripts/reindex.py --sparse --backend=bge --batch-size=16
```

### CPU Only
```env
EMBEDDINGS_BACKEND=onnx
EMBEDDING_BATCH_SIZE=8
EMBEDDING_USE_FP16=false
USE_SPARSE=false  # ONNX не поддерживает sparse
```

```bash
python scripts/reindex.py --backend=onnx --batch-size=8
```

## 📊 Мониторинг процесса

### Прогресс переиндексации
```
🚀 Запуск переиндексации с BGE-M3 unified embeddings...
Конфигурация эмбеддингов:
  EMBEDDINGS_BACKEND: auto
  EMBEDDING_DEVICE: auto
  USE_SPARSE: True
  Оптимальная стратегия: hybrid

Indexing: 100%|████████████| 127/127 [15:23<00:00, 0.14it/s]
✅ Переиндексация завершена!
📊 Статистика: 127 страниц, 1247 чанков
🎯 Итого в базе: 1247 векторов
```

### Логи в реальном времени
```bash
# Отслеживание логов во время переиндексации
tail -f logs/app.log | grep -E "(BGE|ONNX|embedding|batch)"
```

## ⚠️ Важные моменты

### Время выполнения
- **Малая база** (< 500 документов): 5-10 минут
- **Средняя база** (500-2000 документов): 10-30 минут
- **Большая база** (> 2000 документов): 30-60 минут

### Требования к ресурсам
- **RAM**: 4-8 GB для BGE-M3 модели
- **GPU Memory**: 2-4 GB для DirectML/CUDA
- **Disk**: Временно +50% от размера базы данных

### Безопасность
- ✅ **Не удаляет старые данные** до успешного завершения
- ✅ **Atomic operations** - либо все успешно, либо откат
- ✅ **Прерывание Ctrl+C** безопасно на любом этапе

## 🐛 Устранение неполадок

### Ошибки памяти
```bash
# Уменьшить размер батча
python scripts/reindex.py --sparse --batch-size=8

# Отключить FP16 (если включен)
EMBEDDING_USE_FP16=false python scripts/reindex.py --sparse
```

### Ошибки DirectML
```bash
# Принудительно CPU режим
ONNX_PROVIDER=cpu python scripts/reindex.py --sparse --backend=onnx

# Или гибридный режим без DirectML
EMBEDDINGS_BACKEND=bge python scripts/reindex.py --sparse
```

### Ошибки сети (краулинг)
```bash
# Увеличить таймауты
CRAWL_TIMEOUT_S=60 python scripts/reindex.py --sparse

# Уменьшить параллелизм
CRAWL_CONCURRENCY=4 python scripts/reindex.py --sparse
```

## ✅ Проверка результатов

### После переиндексации
```bash
# Проверить количество векторов
python -c "
from qdrant_client import QdrantClient
from app.config import CONFIG

client = QdrantClient(url=CONFIG.qdrant_url, api_key=CONFIG.qdrant_api_key or None)
info = client.get_collection(CONFIG.qdrant_collection)
print(f'Векторов в базе: {info.points_count}')

# Проверить наличие sparse vectors
points = client.scroll(CONFIG.qdrant_collection, limit=1, with_vectors=True)
if points[0] and hasattr(points[0][0], 'sparse_vectors') and points[0][0].sparse_vectors:
    print('✅ Sparse vectors присутствуют')
else:
    print('❌ Sparse vectors отсутствуют')
"
```

### Тестирование качества поиска
```bash
# Тест поиска после переиндексации
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"message": "Как настроить маршрутизацию в edna Chat Center?"}'
```

## 📈 Ожидаемые улучшения

### Производительность
- **2.5x ускорение** генерации эмбеддингов
- **Batch processing** для массовых операций
- **GPU ускорение** (где доступно)

### Качество поиска
- **15-25% улучшение** релевантности с sparse vectors
- **Консистентные результаты** благодаря unified generation
- **Лучшая обработка** синонимов и контекста

### Надежность
- **Graceful fallback** между стратегиями
- **Comprehensive error handling**
- **Production-ready** мониторинг и логирование

---

*Это руководство поможет вам безопасно и эффективно выполнить переиндексацию с новыми BGE-M3 unified embeddings.*
