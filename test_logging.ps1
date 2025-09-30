# Устанавливаем кодовую страницу UTF-8
chcp 65001 | Out-Null

# Устанавливаем переменные окружения для Python
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "."

# Запускаем Python с правильными настройками
python -c "
from app.logging_config import configure_logging
from loguru import logger
logger.info('Тест русского языка в PowerShell')
logger.warning('Предупреждение на русском')
logger.error('Ошибка для проверки')
"
