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
    --distpath "dist-v0.2.10" `
    --icon "assets\yulow-bunny-hole.ico" `
    --add-data "assets;assets" `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all pystray `
    --collect-all PIL `
    main.py
if ($LASTEXITCODE -ne 0) {
    throw "Yulow 打包失敗，未建立新的發行檔。"
}

Copy-Item README.md "dist-v0.2.10\Yulow\使用說明.md" -Force
New-Item -ItemType Directory -Force outputs | Out-Null
Compress-Archive -Path "dist-v0.2.10\Yulow\*" -DestinationPath "outputs\Yulow-Windows-v0.2.10.zip" -Force
Write-Host "完成：outputs\Yulow-Windows-v0.2.10.zip"
