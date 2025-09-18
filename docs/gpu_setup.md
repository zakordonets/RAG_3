# GPU-ускорение для Radeon RX 6700 XT

## 🎯 Обзор

RAG-система поддерживает GPU-ускорение для AMD Radeon RX 6700 XT через ROCm (Radeon Open Compute). Это значительно ускоряет вычисления эмбеддингов, reranking и семантического chunking.

## 🚀 Ожидаемое ускорение

- **Эмбеддинги**: 3-5x ускорение
- **Reranking**: 2-4x ускорение
- **Семантический chunking**: 2-3x ускорение
- **Общая производительность**: 2-4x ускорение

## 📋 Требования

### Системные требования
- **OS**: Ubuntu 20.04+ или Windows 11
- **GPU**: AMD Radeon RX 6700 XT (или совместимая)
- **RAM**: 16GB+ рекомендуется
- **VRAM**: 8GB+ (для больших моделей)

### Программное обеспечение
- **ROCm 5.7+** - для AMD GPU
- **PyTorch с ROCm** - для GPU вычислений
- **Python 3.8+** - для RAG системы

## 🔧 Установка

### 1. Установка ROCm (Ubuntu)

```bash
# Скачиваем и устанавливаем ROCm
wget https://repo.radeon.com/amdgpu-install/5.7/ubuntu/jammy/amdgpu-install_5.7.50700-1_all.deb
sudo dpkg -i amdgpu-install_5.7.50700-1_all.deb
sudo apt-get update

# Устанавливаем ROCm
sudo amdgpu-install --usecase=rocm

# Проверяем установку
rocm-smi
```

### 2. Установка PyTorch с ROCm

```bash
# Устанавливаем PyTorch с поддержкой ROCm
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7

# Устанавливаем дополнительные пакеты
pip install transformers[torch] accelerate
```

### 3. Установка RAG системы

```bash
# Клонируем репозиторий
git clone <repository-url>
cd RAG_2

# Устанавливаем зависимости
pip install -r requirements.txt

# Настраиваем конфигурацию
cp env.example .env
# Отредактируйте .env файл для включения GPU
```

## ⚙️ Конфигурация

### 1. Настройка .env файла

```bash
# GPU Configuration
GPU_ENABLED=true
GPU_DEVICE=0
GPU_MEMORY_FRACTION=0.8

# Reranker на GPU
RERANKER_DEVICE=cuda

# Остальные настройки...
```

### 2. Проверка конфигурации

```bash
# Запускаем тест GPU
python scripts/test_gpu_performance.py

# Проверяем доступность GPU
python -c "import torch; print(f'CUDA доступен: {torch.cuda.is_available()}'); print(f'Количество GPU: {torch.cuda.device_count()}')"
```

## 🧪 Тестирование

### 1. Автоматическое тестирование

```bash
# Запускаем полный тест производительности
python scripts/test_gpu_performance.py
```

### 2. Ручное тестирование

```python
# Проверяем GPU
import torch
print(f"CUDA доступен: {torch.cuda.is_available()}")
print(f"Устройство: {torch.cuda.get_device_name(0)}")

# Тестируем производительность
from app.gpu_utils import get_gpu_memory_info
print(get_gpu_memory_info())
```

### 3. Тестирование компонентов

```bash
# Тест эмбеддингов
python -c "from app.services.embeddings import embed_dense; print(embed_dense('test'))"

# Тест reranker
python -c "from app.services.rerank import rerank; print(rerank('test', [{'payload': {'text': 'test'}}]))"

# Тест chunker
python -c "from ingestion.semantic_chunker import chunk_text_semantic; print(chunk_text_semantic('test text'))"
```

## 📊 Мониторинг производительности

### 1. GPU мониторинг

```bash
# Мониторинг GPU в реальном времени
watch -n 1 rocm-smi

# Или через nvidia-smi (если установлен)
nvidia-smi
```

### 2. Мониторинг через API

```bash
# Проверяем состояние GPU через API
curl http://localhost:9000/v1/admin/health

# Получаем метрики
curl http://localhost:9000/v1/admin/metrics
```

### 3. Логирование

Система автоматически логирует:
- Использование GPU
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

```bash
# Для CPU операций
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
```

## 🐛 Устранение неполадок

### 1. ROCm не установлен

```bash
# Проверяем установку
rocm-smi
# Если не работает, переустанавливаем ROCm
```

### 2. PyTorch не видит GPU

```bash
# Проверяем версию PyTorch
python -c "import torch; print(torch.__version__)"

# Переустанавливаем с правильным индексом
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

### 3. Нехватка памяти GPU

```bash
# Уменьшаем использование памяти
GPU_MEMORY_FRACTION=0.6

# Или используем CPU для больших операций
RERANKER_DEVICE=cpu
```

### 4. Медленная производительность

```bash
# Проверяем загрузку GPU
rocm-smi

# Оптимизируем размер батча
python scripts/test_gpu_performance.py
```

## 📈 Бенчмарки

### Ожидаемая производительность (Radeon RX 6700 XT)

| Операция | CPU (s) | GPU (s) | Ускорение |
|----------|---------|---------|-----------|
| Dense Embedding (1 текст) | 0.05 | 0.02 | 2.5x |
| Dense Embedding (10 текстов) | 0.50 | 0.15 | 3.3x |
| Reranking (5 кандидатов) | 0.20 | 0.08 | 2.5x |
| Semantic Chunking | 0.30 | 0.12 | 2.5x |
| Полный запрос | 2.00 | 0.80 | 2.5x |

### Факторы влияющие на производительность

1. **Размер модели** - большие модели требуют больше VRAM
2. **Размер батча** - оптимальный размер зависит от модели
3. **Тип операций** - некоторые операции лучше на CPU
4. **Память GPU** - нехватка памяти снижает производительность

## 🚀 Запуск с GPU

### 1. Запуск сервера

```bash
# Убедитесь что GPU включен в .env
export GPU_ENABLED=true
python wsgi.py
```

### 2. Запуск Telegram бота

```bash
# Запускаем с GPU ускорением
python adapters/telegram_enhanced.py
```

### 3. Запуск индексации

```bash
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

## 🎯 Заключение

GPU-ускорение значительно повышает производительность RAG-системы:

- ✅ **2-4x ускорение** основных операций
- ✅ **Лучший пользовательский опыт** - быстрые ответы
- ✅ **Масштабируемость** - обработка большего количества запросов
- ✅ **Эффективность** - лучшее использование ресурсов

Radeon RX 6700 XT отлично подходит для RAG-системы и обеспечивает отличную производительность! 🚀
