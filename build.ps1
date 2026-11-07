$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& .venv\Scripts\python.exe -m pip install -r requirements-build.txt
& .venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "Yulow" `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all pystray `
    --collect-all PIL `
    main.py

Copy-Item README.md "dist\Yulow\使用說明.md" -Force
New-Item -ItemType Directory -Force outputs | Out-Null
Compress-Archive -Path "dist\Yulow\*" -DestinationPath "outputs\Yulow-Windows-v0.2.0.zip" -Force
Write-Host "完成：outputs\Yulow-Windows-v0.2.0.zip"
