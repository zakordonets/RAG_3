@echo off
REM Скрипт установки DirectML для Windows (Radeon RX 6700 XT)

echo 🚀 Установка DirectML для AMD GPU на Windows...
echo.

REM Проверяем версию Python
python --version
if %errorlevel% neq 0 (
    echo ❌ Python не найден. Установите Python 3.8+ с https://python.org
    pause
    exit /b 1
)

echo.
echo 📦 Устанавливаем DirectML...
pip install torch-directml

echo.
echo 📦 Устанавливаем дополнительные пакеты...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers accelerate

echo.
echo 🧪 Тестируем установку...
python -c "import torch_directml; print('DirectML доступен:', torch_directml.is_available()); print('Количество устройств:', torch_directml.device_count())"

echo.
echo ✅ Установка завершена!
echo.
echo Для использования DirectML в коде:
echo   device = torch_directml.device()
echo   model = model.to(device)
echo.
pause
