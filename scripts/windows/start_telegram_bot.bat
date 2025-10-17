@echo off
pushd "%~dp0\..\.."
echo Starting Telegram Bot...
set PYTHONPATH=%CD%
python adapters/telegram/polling.py
popd
