@echo off
pushd "%~dp0\..\.."
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python %*
popd
