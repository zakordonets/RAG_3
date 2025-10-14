@echo off
echo Fixing Telegram Bot 409 Conflict...
echo.

set PYTHONPATH=%CD%
python scripts/fix_telegram_409.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Success! You can now start the bot.
    echo.
    echo To start the bot, run:
    echo   start_telegram_bot.bat
    echo.
) else (
    echo.
    echo Failed to fix the issue. Check the output above.
    echo.
    echo Common solutions:
    echo   1. Stop all Python processes
    echo   2. Stop Docker containers: docker-compose down
    echo   3. Wait 1-2 minutes and try again
    echo.
)

exit /b %ERRORLEVEL%
