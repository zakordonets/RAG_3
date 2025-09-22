# PowerShell script to start Telegram Bot
Write-Host "🤖 Starting Telegram Bot..." -ForegroundColor Green
$env:PYTHONPATH = "$PWD"
python adapters/telegram_polling.py
