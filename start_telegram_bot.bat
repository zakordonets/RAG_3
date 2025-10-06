@echo off
echo Starting Telegram Bot...
set PYTHONPATH=%CD%
python adapters/telegram/polling.py
