# PowerShell script to fix Telegram Bot 409 Conflict error
Write-Host "🔧 Fixing Telegram Bot 409 Conflict..." -ForegroundColor Cyan
Write-Host ""

$env:PYTHONPATH = "$PWD"
python scripts/fix_telegram_409.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Success! You can now start the bot." -ForegroundColor Green
    Write-Host ""
    Write-Host "To start the bot, run:" -ForegroundColor Yellow
    Write-Host "  .\start_telegram_bot.ps1" -ForegroundColor White
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "❌ Failed to fix the issue. Check the output above." -ForegroundColor Red
    Write-Host ""
    Write-Host "Common solutions:" -ForegroundColor Yellow
    Write-Host "  1. Stop all Python processes: Get-Process python | Stop-Process" -ForegroundColor White
    Write-Host "  2. Stop Docker containers: docker-compose down" -ForegroundColor White
    Write-Host "  3. Wait 1-2 minutes and try again" -ForegroundColor White
    Write-Host ""
}

exit $LASTEXITCODE
