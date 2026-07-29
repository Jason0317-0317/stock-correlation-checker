$ErrorActionPreference = "Stop"
$projectPath = $PSScriptRoot
$buildEnvironment = Join-Path $env:TEMP "stock-correlation-build"

Set-Location $projectPath

if (-not (Test-Path $buildEnvironment)) {
    python -m venv $buildEnvironment
}

& "$buildEnvironment\Scripts\python.exe" -m pip install --upgrade pip
& "$buildEnvironment\Scripts\python.exe" -m pip install -r requirements.txt
& "$buildEnvironment\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "StockCorrelationChecker" `
    --collect-all matplotlib `
    --collect-all yfinance `
    app.py

Write-Host ""
Write-Host "Built: dist\StockCorrelationChecker\StockCorrelationChecker.exe"
