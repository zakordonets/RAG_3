# Auto-Merge: Опциональные зависимости

## 📦 Обзор

Auto-Merge работает **из коробки** без дополнительных зависимостей! Функциональность `tiktoken` и `cachetools` является **опциональной** и используется только для оптимизации.

---

## 🔄 Режимы работы

### Режим 1: Базовый (без опциональных зависимостей)

**Что используется:**
- ✅ Эвристическая оценка токенов: `len(text) // 4`
- ✅ Простой dict-кеш без TTL
- ✅ Все основные функции auto-merge

**Конфигурация:**
```bash
RETRIEVAL_AUTO_MERGE_ENABLED=true
RETRIEVAL_AUTO_MERGE_MAX_TOKENS=1200
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=false  # Важно!
```

**Плюсы:**
- ✅ Работает без дополнительных зависимостей
- ✅ Быстрая установка
- ✅ Нет конфликтов зависимостей

**Минусы:**
- ⚠️ Оценка токенов менее точная (~10-15% погрешность)
- ⚠️ Кеш без TTL (память может расти со временем)

---

### Режим 2: Оптимизированный (с опциональными зависимостями)

**Что используется:**
- ✅ Точная оценка токенов через `tiktoken`
- ✅ TTL-кеш с автоматической очисткой
- ✅ Максимальная точность и производительность

**Установка:**
```bash
# Если нет конфликтов зависимостей
pip install tiktoken==0.8.0 cachetools==5.5.0

# Или по отдельности
pip install tiktoken==0.8.0  # Только точная оценка токенов
pip install cachetools==5.5.0  # Только TTL-кеш
```

**Конфигурация:**
```bash
RETRIEVAL_AUTO_MERGE_ENABLED=true
RETRIEVAL_AUTO_MERGE_MAX_TOKENS=1200
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=true  # Требует tiktoken
RETRIEVAL_CACHE_MAXSIZE=1000            # Требует cachetools
RETRIEVAL_CACHE_TTL=300                 # Требует cachetools
```

**Плюсы:**
- ✅ Точная оценка токенов (±2-3%)
- ✅ Автоматическая очистка кеша
- ✅ Оптимальное использование памяти

**Минусы:**
- ⚠️ Дополнительные зависимости
- ⚠️ Возможны конфликты с другими пакетами

---

## 🔍 Автоматическое определение режима

Система автоматически определяет доступность зависимостей при запуске:

```python
# При запуске в логах вы увидите:

# Без tiktoken:
DEBUG tiktoken not available, using heuristic token estimation (len//4)

# Без cachetools:
DEBUG cachetools not available, using simple dict cache (no TTL)
WARNING Using simple dict cache without TTL (memory may grow over time)

# С обеими зависимостями:
INFO Using TTL cache (maxsize=1000, ttl=300s)
```

---

## 🛠️ Решение конфликтов зависимостей

### Проблема: Конфликт при установке tiktoken

**Причина:** `tiktoken` требует специфичные версии `regex` или других пакетов

**Решение 1:** Использовать базовый режим
```bash
# В .env установите
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=false
```

**Решение 2:** Обновить конфликтующие пакеты
```bash
pip install --upgrade regex
pip install tiktoken==0.8.0
```

**Решение 3:** Использовать более старую версию tiktoken
```bash
pip install tiktoken==0.5.2  # Старая версия, меньше конфликтов
```

---

### Проблема: Конфликт при установке cachetools

**Причина:** `cachetools` конфликтует с версиями других пакетов

**Решение 1:** Система работает без cachetools (простой dict)
```bash
# Ничего не нужно делать - система использует fallback
```

**Решение 2:** Вручную очищать кеш при необходимости
```python
from app.services.search.retrieval import clear_chunk_cache

# Вызвать периодически или при высокой нагрузке
clear_chunk_cache()
```

**Решение 3:** Использовать другую версию cachetools
```bash
pip install cachetools==4.2.4  # Старая стабильная версия
```

---

## 📊 Сравнение режимов

| Характеристика | Базовый режим | Оптимизированный |
|----------------|---------------|------------------|
| **Зависимости** | Нет | `tiktoken` + `cachetools` |
| **Точность токенов** | ±10-15% | ±2-3% |
| **Скорость оценки** | Очень быстро | Быстро |
| **Управление памятью** | Ручное | Автоматическое |
| **Риск конфликтов** | Нет | Возможен |
| **Рекомендуется для** | Development, Testing | Production |

---

## 🎯 Рекомендации

### Для разработки и тестирования
```bash
# Используйте базовый режим
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=false
```
- Быстрая установка
- Нет проблем с зависимостями
- Достаточная точность для тестов

### Для production (если нет конфликтов)
```bash
# Установите опциональные зависимости
pip install tiktoken cachetools

# Включите оптимизации
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=true
```
- Максимальная точность
- Лучшее управление памятью

### Для production (при конфликтах)
```bash
# Используйте базовый режим + ручная очистка кеша
RETRIEVAL_AUTO_MERGE_USE_TIKTOKEN=false

# Настройте периодическую очистку кеша (например, через cron или healthcheck)
```

---

## 🔧 API для управления кешем

### Очистка кеша программно

```python
from app.services.search.retrieval import clear_chunk_cache

# Очистить весь кеш
clear_chunk_cache()
```

### Интеграция с healthcheck

```python
# В вашем admin endpoint
from app.services.search.retrieval import clear_chunk_cache

@app.route('/v1/admin/cache/clear', methods=['POST'])
def clear_retrieval_cache():
    clear_chunk_cache()
    return {"status": "ok", "message": "Cache cleared"}
```

### Периодическая очистка

```python
import threading
import time
from app.services.search.retrieval import clear_chunk_cache

def periodic_cache_cleanup(interval_seconds=3600):
    """Очищать кеш каждый час."""
    while True:
        time.sleep(interval_seconds)
        clear_chunk_cache()

# Запустить в фоновом потоке
cleanup_thread = threading.Thread(target=periodic_cache_cleanup, daemon=True)
cleanup_thread.start()
```

---

## 📈 Мониторинг

### Проверка использования памяти (без cachetools)

```python
import sys
from app.services.search.retrieval import _doc_chunk_cache

# Размер кеша в памяти
cache_size = sys.getsizeof(_doc_chunk_cache)
num_docs = len(_doc_chunk_cache)

print(f"Cache: {num_docs} documents, ~{cache_size / 1024 / 1024:.2f} MB")
```

### Логирование при достижении лимита

```python
from loguru import logger
from app.services.search.retrieval import _doc_chunk_cache

if len(_doc_chunk_cache) > 1000:
    logger.warning(f"Cache size exceeded: {len(_doc_chunk_cache)} documents")
```

---

## ✅ FAQ

**Q: Нужно ли устанавливать tiktoken и cachetools?**
A: Нет, система работает без них. Это опциональные оптимизации.

**Q: Как понять, какой режим активен?**
A: Смотрите в логи при запуске - там будут сообщения о доступности библиотек.

**Q: Что делать при росте памяти без cachetools?**
A: Периодически вызывайте `clear_chunk_cache()` или перезапускайте сервис.

**Q: Насколько менее точна эвристическая оценка?**
A: Для русского/английского текста погрешность ~10-15%, что приемлемо для большинства задач.

**Q: Можно ли установить только tiktoken без cachetools?**
A: Да, каждая зависимость независима. Tiktoken улучшит точность, а кеш останется простым dict.

**Q: Влияет ли отсутствие этих библиотек на основную функциональность?**
A: Нет, auto-merge полностью функционален в базовом режиме.

---

**Версия:** 1.0
**Дата обновления:** 2025-10-08
**Статус:** ✅ Готово к использованию в любом режиме
