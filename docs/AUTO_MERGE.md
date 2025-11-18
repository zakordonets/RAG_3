# Auto-Merge: Автоматическое объединение соседних чанков

## 📖 Обзор

**Auto-Merge** — это интеллектуальная функция retrieval-пайплайна, которая автоматически объединяет соседние чанки из одного документа после этапа rerank, предоставляя LLM более широкий и связный контекст при сохранении token budget.

> **⚠️ Важно:** Auto-Merge работает **из коробки** без дополнительных зависимостей!
> Библиотеки `tiktoken` и `cachetools` являются **опциональными** оптимизациями.
> См. [AUTO_MERGE_OPTIONAL_DEPS.md](./AUTO_MERGE_OPTIONAL_DEPS.md) для подробностей.

### Ключевые преимущества

- ✅ **Улучшенный контекст**: LLM получает связанные фрагменты документа вместо изолированных чанков
- ✅ **Экономия токенов**: Объединение уменьшает количество окон для обработки
- ✅ **Сохранение релевантности**: Работает после rerank, поэтому расширяет только релевантные чанки
- ✅ **Гибкая настройка**: Полностью конфигурируется через env-переменные
- ✅ **Прозрачные метаданные**: Детальная информация о слиянии для анализа

---

## 🔄 Как это работает

### Место в пайплайне

```
Запрос → Embedding → Hybrid Search → RRF Fusion → Rerank
                                                      ↓
                                              🎯 AUTO-MERGE 🎯
                                                      ↓
                                          Context Optimization → LLM
```

### Алгоритм

1. **Группировка по документам**
   Чанки с одинаковым `doc_id` группируются вместе.

2. **Получение всех чанков документа**
   Для каждого документа fetch все его чанки из Qdrant (с кешированием).

3. **Расширение окна**
   Для каждого релевантного чанка расширяем окно влево и вправо:
   ```
   Исходный чанк: [2]
   Расширение влево: [1] [2]
   Расширение вправо: [1] [2] [3]
   Остановка: достигнут token budget
   ```

4. **Token Budget контроль**
   Оценка токенов выполняется через:
   - **tiktoken** (точно, если доступен)
   - Эвристика `len(text) // 4` (fallback)

5. **Deduplification**
   Объединённые окна дедуплицируются — один чанк не появится дважды.

6. **Сохранение порядка**
   Результаты возвращаются в исходном порядке после rerank.

---

## ⚙️ Конфигурация

### Переменные окружения

```bash
# Основные параметры
RETRIEVAL_AUTO_MERGE_ENABLED=true              # Включить/выключить
RETRIEVAL_AUTO_MERGE_MAX_TOKENS=1200           # Макс. размер окна в токенах
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=true         # Использовать tiktoken для оценки

# Кеширование
RETRIEVAL_CACHE_MAXSIZE=1000                   # Макс. документов в кеше
RETRIEVAL_CACHE_TTL=300                        # Время жизни кеша (секунды)

# Qdrant
QDRANT_SCROLL_BATCH_SIZE=64                    # Размер батча при scroll
```

### Параметры в app/config/app_config.py

```python
@dataclass(frozen=True)
class AppConfig:
    # Auto-Merge
    retrieval_auto_merge_enabled: bool            # default: True
    retrieval_auto_merge_max_tokens: int          # default: 1200
    retrieval_auto_merge_use_tiktoken: bool       # default: True
    retrieval_cache_maxsize: int                  # default: 1000
    retrieval_cache_ttl: int                      # default: 300 (5 мин)
    qdrant_scroll_batch_size: int                 # default: 64
```

---

## 📊 Рекомендации по настройке

### RETRIEVAL_AUTO_MERGE_MAX_TOKENS

| Значение | Сценарий | Описание |
|----------|----------|----------|
| `800-1000` | Экономия контекста | Максимальный резерв для длинных ответов LLM |
| `1200` | **Рекомендуется** | Баланс контекста и производительности |
| `1500-2000` | Богатый контекст | Максимальный контекст для коротких ответов |

**Динамическая адаптация:**
Orchestrator автоматически адаптирует лимит на основе `context_optimizer.max_context_tokens`:
```python
available = max_context_tokens * (1 - reserve_for_response)
merge_limit = min(CONFIG.retrieval_auto_merge_max_tokens, available)
```

### RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN

- ✅ **true** (рекомендуется): Точная оценка через tiktoken (~10-15% точнее)
- ⚡ **false**: Быстрая эвристика `len//4` (на ~30% быстрее, но менее точно)

### RETRIEVAL_CACHE_TTL

- `60-180`: Частые изменения индекса
- `300`: **Рекомендуется** (5 минут)
- `600-900`: Стабильный индекс

---

## 🔍 Метаданные слияния

После слияния payload содержит:

```python
{
    "auto_merged": True,
    "merged_chunk_indices": [2, 3, 4],      # Какие чанки объединены
    "merged_chunk_count": 3,                # Количество
    "chunk_span": {
        "start": 2,
        "end": 4
    },
    "merged_chunk_ids": [                   # ID объединённых чанков
        "doc-123#2",
        "doc-123#3",
        "doc-123#4"
    ],
    "text": "Объединённый текст...",        # Слитый контент
    "content_length": 3456                  # Длина в символах
}
```

---

## 📈 Метрики и логирование

### Пример лога

```log
DEBUG Auto-merge: 15 -> 8 окон (лимит=1200 токенов, экономия=7 чанков, эффективность=46.7%)
```

### Метрики

- **До/После**: Количество окон до и после слияния
- **Лимит**: Используемый token budget
- **Экономия**: Сколько чанков объединено
- **Эффективность**: Процент редукции окон

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Базовые тесты
pytest tests/test_retrieval_auto_merge.py -v

# Расширенные тесты (edge cases, performance)
pytest tests/test_retrieval_auto_merge_extended.py -v

# Все тесты
pytest tests/test_retrieval_auto_merge*.py -v
```

### Покрытие тестов

✅ **Базовая функциональность**
- Слияние соседних чанков
- Сохранение порядка
- Обработка orphan chunks

✅ **Edge Cases**
- Пустые входные данные
- Отключённый auto-merge
- Чанки без метаданных
- Один чанк превышает лимит
- Non-sequential chunks

✅ **Performance**
- Обработка больших документов (100 docs × 10 chunks)
- Проверка времени выполнения

✅ **Token Estimation**
- Пустые строки
- Короткие/длинные тексты
- Многоязычный контент

✅ **Merge Logic**
- Соблюдение token budget
- Корректность метаданных
- Множественные документы

---

## 💡 Примеры использования

### Пример 1: Базовое использование

```python
from app.retrieval.retrieval import auto_merge_neighbors

# После rerank получили топ-10 чанков
top_docs = reranker.rerank(query, candidates)

# Автоматическое слияние
merged_docs = auto_merge_neighbors(
    top_docs,
    max_window_tokens=1200
)

# merged_docs теперь содержит расширенные контекстные окна
for doc in merged_docs:
    if doc["payload"].get("auto_merged"):
        print(f"Merged {doc['payload']['merged_chunk_count']} chunks")
```

### Пример 2: С собственной fetch-функцией (тестирование)

```python
def custom_fetch(doc_id: str) -> list[dict]:
    # Ваша логика получения чанков
    return get_chunks_from_cache(doc_id)

merged = auto_merge_neighbors(
    top_docs,
    max_window_tokens=1500,
    fetch_fn=custom_fetch
)
```

### Пример 3: Отключение для конкретного запроса

```python
# Временно отключить
object.__setattr__(CONFIG, "retrieval_auto_merge_enabled", False)
result = orchestrator.search(query)

# Или использовать max_window_tokens=0
merged = auto_merge_neighbors(top_docs, max_window_tokens=0)  # Не сольёт
```

---

## 🔧 Интеграция с Orchestrator

Orchestrator автоматически вызывает auto-merge после rerank:

```python
# app/orchestration/orchestrator.py

# 5a. Rerank
top_docs = reranker.rerank(query, candidates)

# 5b. Auto-merge
if CONFIG.retrieval_auto_merge_enabled:
    max_ctx_tokens = context_optimizer.max_context_tokens
    reserve = context_optimizer.reserve_for_response
    available = max(1, int(max_ctx_tokens * (1 - reserve)))
    merge_limit = min(CONFIG.retrieval_auto_merge_max_tokens, available)

    merged_docs = auto_merge_neighbors(top_docs, max_window_tokens=merge_limit)
    top_docs = merged_docs

# 6. Context Optimization
optimized = context_optimizer.optimize_context(top_docs, normalized)
```

---

## 🐛 Troubleshooting

### Проблема: Слияние не работает

**Проверьте:**
1. `RETRIEVAL_AUTO_MERGE_ENABLED=true` в `.env`
2. `RETRIEVAL_AUTO_MERGE_MAX_TOKENS` > 0
3. В логах должны быть записи `Auto-merge: X -> Y окон`

**Решение:**
```bash
# Проверить конфигурацию
python -c "from app.config import CONFIG; print(f'Enabled: {CONFIG.retrieval_auto_merge_enabled}, MaxTokens: {CONFIG.retrieval_auto_merge_max_tokens}')"
```

### Проблема: Слишком агрессивное слияние

**Симптомы:**
Слишком много чанков объединяется, context window overflow

**Решение:**
```bash
# Уменьшить лимит
RETRIEVAL_AUTO_MERGE_MAX_TOKENS=800

# Или отключить tiktoken (будет консервативнее)
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=false
```

### Проблема: Низкая производительность

**Симптомы:**
Медленные запросы после включения auto-merge

**Решение:**
```bash
# Увеличить размер кеша
RETRIEVAL_CACHE_MAXSIZE=2000

# Увеличить batch size для scroll
QDRANT_SCROLL_BATCH_SIZE=128

# Отключить tiktoken для скорости
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=false
```

### Проблема: Утечка памяти

**Симптомы:**
Рост памяти со временем

**Решение:**
```bash
# Уменьшить размер кеша
RETRIEVAL_CACHE_MAXSIZE=500

# Уменьшить TTL
RETRIEVAL_CACHE_TTL=120  # 2 минуты
```

---

## 📚 Дополнительные ресурсы

- [ADR-001: BGE-M3 Unified Embeddings](./adr-001-bge-m3-unified-embeddings.md)
- [ADR-002: Adaptive Chunking](./adr-002-adaptive-chunking.md)
- [Architecture Overview](./architecture.md)
- [API Documentation](./api_documentation.md)

---

## 🎯 Best Practices

1. **Начните с дефолтных значений** (`RETRIEVAL_AUTO_MERGE_MAX_TOKENS=1200`)
2. **Мониторьте метрики** эффективности слияния в логах
3. **Настройте под LLM**: для моделей с большим context window увеличьте лимит
4. **Используйте tiktoken в production** для точности
5. **Настройте кеш** под нагрузку вашего приложения
6. **Тестируйте на реальных запросах** и корректируйте параметры

---

**Версия:** 1.0
**Дата обновления:** 2025-10-08
**Авторы:** RAG System Team
