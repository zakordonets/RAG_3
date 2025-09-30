# Устанавливаем кодовую страницу UTF-8
chcp 65001 | Out-Null

# Устанавливаем кодировку вывода PowerShell на UTF-8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Устанавливаем переменные окружения для Python
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "."

# Запускаем Python с правильными настройками
python -c "
import sys
print('Default encoding:', sys.stdout.encoding)
print('Test русский текст')
"
