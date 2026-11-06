@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  call "安装与启动.bat"
  exit /b
)
start "" .venv\Scripts\pythonw.exe main.py
