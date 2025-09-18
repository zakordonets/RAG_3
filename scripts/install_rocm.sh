#!/bin/bash
# Скрипт установки ROCm для AMD GPU (Radeon RX 6700 XT)

echo "🚀 Установка ROCm для AMD GPU..."

# Проверяем архитектуру GPU
echo "📊 Проверка GPU..."
lspci | grep -i amd

# Устанавливаем ROCm (Ubuntu/Debian)
echo "📦 Установка ROCm..."
wget https://repo.radeon.com/amdgpu-install/5.7/ubuntu/jammy/amdgpu-install_5.7.50700-1_all.deb
sudo dpkg -i amdgpu-install_5.7.50700-1_all.deb
sudo apt-get update
sudo amdgpu-install --usecase=rocm

# Устанавливаем Python пакеты для ROCm
echo "🐍 Установка Python пакетов для ROCm..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
pip install transformers[torch] accelerate

# Проверяем установку
echo "✅ Проверка установки ROCm..."
python -c "import torch; print(f'PyTorch версия: {torch.__version__}'); print(f'CUDA доступен: {torch.cuda.is_available()}'); print(f'Количество GPU: {torch.cuda.device_count()}')"

echo "🎉 ROCm установлен! Теперь можно использовать GPU-ускорение."
