# PowerShell script to start Telegram Bot
Set-Location -Path (Join-Path $PSScriptRoot '..\\..')
Write-Host "🤖 Starting Telegram Bot..." -ForegroundColor Green
$env:PYTHONPATH = "$PWD"
python adapters/telegram/polling.py
