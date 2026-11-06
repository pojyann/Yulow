@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Yulow

if not exist ".venv\Scripts\pythonw.exe" (
  echo 正在进行首次安装，请稍候...
  python -m venv .venv
  if errorlevel 1 goto :error
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

start "" .venv\Scripts\pythonw.exe main.py
exit /b 0

:error
echo.
echo 安装失败。请确认电脑可以连接网络，并已安装 Python 3.10 或更新版本。
pause
exit /b 1
