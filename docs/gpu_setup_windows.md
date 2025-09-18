# GPU-ускорение для Windows (ONNX Runtime + DirectML, Radeon RX 6700 XT)

## 🎯 Обзор

Система использует ONNX Runtime (ORT) с провайдером **DmlExecutionProvider** для ускорения эмбеддингов и reranking на AMD Radeon RX 6700 XT. Компоненты на PyTorch не используют device "dml" — ускорение реализовано на уровне ORT.

## 🚀 Ожидаемое ускорение

- **Эмбеддинги**: 1.5-3x ускорение
- **Reranking**: 1.5-2.5x ускорение
- **Семантический chunking**: 1.5-2x ускорение
- **Общая производительность**: 1.5-3x ускорение

## 📋 Требования

### Системные требования
- **OS**: Windows 10/11 (64-bit)
- **GPU**: AMD Radeon RX 6700 XT (или совместимая)
- **RAM**: 16GB+ рекомендуется
- **VRAM**: 8GB+ (для больших моделей)
- **DirectX**: 12+ (обычно уже установлен)

### Программное обеспечение
- **Python 3.11+**
- **onnx, onnxruntime-directml, optimum**

## 🔧 Установка

### Установка пакетов

```powershell
pip install onnx onnxruntime-directml optimum
```

### Проверка установки

```cmd
# Проверяем DirectML
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

## ⚙️ Конфигурация

### 1. Настройка .env файла

```bash
# GPU Configuration
GPU_ENABLED=true
GPU_DEVICE=0
GPU_MEMORY_FRACTION=0.8

# Reranker на GPU (будет использовать DirectML)
RERANKER_DEVICE=cuda

# Остальные настройки...
```

### 2. Проверка конфигурации

```cmd
# Запускаем тест GPU
python scripts\test_gpu_windows.py

# Проверяем доступность DirectML
python -c "import torch_directml; print(f'DirectML доступен: {torch_directml.is_available()}'); print(f'Количество GPU: {torch_directml.device_count()}')"
```

## 🧪 Тестирование

### 1. Автоматическое тестирование

```cmd
# Запускаем полный тест производительности
python scripts\test_gpu_windows.py
```

### 2. Ручное тестирование

```python
# Проверяем DirectML
import torch_directml
print(f"DirectML доступен: {torch_directml.is_available()}")
print(f"Устройство: {torch_directml.device_name(0)}")

# Тестируем производительность
from app.gpu_utils import get_gpu_memory_info
print(get_gpu_memory_info())
```

### 3. Тестирование компонентов

```cmd
# Тест эмбеддингов
python -c "from app.services.embeddings import embed_dense; print(embed_dense('test'))"

# Тест reranker
python -c "from app.services.rerank import rerank; print(rerank('test', [{'payload': {'text': 'test'}}]))"

# Тест chunker
python -c "from ingestion.semantic_chunker import chunk_text_semantic; print(chunk_text_semantic('test text'))"
```

## 📊 Мониторинг производительности

### 1. GPU мониторинг

```cmd
# Мониторинг GPU через диспетчер задач
# Или используйте GPU-Z для детальной информации
```

### 2. Мониторинг через API

```cmd
# Проверяем состояние GPU через API
curl http://localhost:9000/v1/admin/health

# Получаем метрики
curl http://localhost:9000/v1/admin/metrics
```

### 3. Логирование

Система автоматически логирует:
- Использование DirectML
- Время выполнения операций
- Ошибки GPU
- Оптимизации производительности

## 🔧 Оптимизация

### 1. Настройка памяти GPU

```bash
# В .env файле
GPU_MEMORY_FRACTION=0.8  # Используем 80% памяти GPU
```

### 2. Оптимизация батчей

```python
# Автоматическое определение оптимального размера батча
from app.gpu_utils import get_optimal_batch_size
optimal_batch = get_optimal_batch_size(model, input_shape, device)
```

### 3. Настройка потоков

```cmd
# Для CPU операций
set OMP_NUM_THREADS=4
set MKL_NUM_THREADS=4
```

## 🐛 Устранение неполадок

### 1. DirectML не установлен

```cmd
# Проверяем установку
python -c "import torch_directml"

# Если ошибка, переустанавливаем
pip uninstall torch-directml
pip install torch-directml
```

### 2. PyTorch не видит DirectML

```cmd
# Проверяем версию PyTorch
python -c "import torch; print(torch.__version__)"

# Переустанавливаем с правильным индексом
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install torch-directml
```

### 3. GPU не обнаружен

```cmd
# Проверяем драйверы AMD
# Обновите драйверы с https://www.amd.com/support

# Проверяем DirectX
dxdiag
```

### 4. Медленная производительность

```cmd
# Проверяем загрузку GPU через диспетчер задач
# Оптимизируем размер батча
python scripts\test_gpu_windows.py
```

## 📈 Бенчмарки

### Ожидаемая производительность (Radeon RX 6700 XT + DirectML)

| Операция | CPU (s) | DirectML (s) | Ускорение |
|----------|---------|--------------|-----------|
| Dense Embedding (1 текст) | 0.05 | 0.03 | 1.7x |
| Dense Embedding (10 текстов) | 0.50 | 0.25 | 2.0x |
| Reranking (5 кандидатов) | 0.20 | 0.12 | 1.7x |
| Semantic Chunking | 0.30 | 0.18 | 1.7x |
| Полный запрос | 2.00 | 1.20 | 1.7x |

### Факторы влияющие на производительность

1. **Размер модели** - большие модели требуют больше VRAM
2. **Размер батча** - оптимальный размер зависит от модели
3. **Тип операций** - некоторые операции лучше на CPU
4. **Память GPU** - нехватка памяти снижает производительность
5. **Драйверы AMD** - актуальные драйверы важны для производительности

## 🚀 Запуск с GPU

### 1. Запуск сервера

```cmd
# Убедитесь что GPU включен в .env
set GPU_ENABLED=true
python wsgi.py
```

### 2. Запуск Telegram бота

```cmd
# Запускаем с GPU ускорением
python adapters\telegram_enhanced.py
```

### 3. Запуск индексации

```cmd
# Индексация с GPU ускорением
python -c "from ingestion.pipeline import crawl_and_index; crawl_and_index()"
```

## 📝 Рекомендации

### 1. Для разработки
- Используйте `GPU_MEMORY_FRACTION=0.6` для экономии памяти
- Включайте GPU только для тестирования производительности
- Используйте CPU для отладки

### 2. Для production
- Используйте `GPU_MEMORY_FRACTION=0.8` для максимальной производительности
- Мониторьте использование памяти GPU
- Настройте автоматическое масштабирование

### 3. Для больших нагрузок
- Используйте несколько GPU если доступно
- Оптимизируйте размер батчей
- Кэшируйте результаты эмбеддингов

## 🔄 Сравнение с Linux

| Аспект | Windows (DirectML) | Linux (ROCm) |
|--------|-------------------|--------------|
| **Установка** | Простая | Сложная |
| **Производительность** | 1.5-3x | 2-4x |
| **Стабильность** | Хорошая | Отличная |
| **Поддержка** | Ограниченная | Полная |
| **Рекомендация** | Для разработки | Для production |

## 🎯 Заключение

GPU-ускорение на Windows через DirectML обеспечивает:

- ✅ **1.5-3x ускорение** основных операций
- ✅ **Простая установка** - один pip install
- ✅ **Хорошая совместимость** с Windows
- ✅ **Автоматическое управление** памятью

**Рекомендация**: Используйте Windows + DirectML для разработки и тестирования, Linux + ROCm для production развертывания.

Radeon RX 6700 XT отлично работает с DirectML на Windows! 🚀
