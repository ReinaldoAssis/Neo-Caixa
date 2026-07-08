# Build Neo Caixa onefile for Windows.
# Run from project root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\scripts\build-win.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== Neo Caixa - Windows build ===" -ForegroundColor Cyan

# Resolve venv python (create if missing). Never rely on Activate.
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[venv] .venv not found, creating"
    python -m venv .venv
}

Write-Host "[1/4] Installing Python deps"
& $Py -m pip install -q --upgrade pip
& $Py -m pip install -q -r requirements.txt

Write-Host "[2/4] Building frontend (npm install + build)"
Push-Location (Join-Path $Root "app\frontend")
# Clean stale/partial modules that cause 'Cannot find package vite' on Windows
if (Test-Path "node_modules") { Remove-Item -Recurse -Force "node_modules" }
npm install
npm run build
Pop-Location

Write-Host "[3/4] Cleaning old build artifacts"
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "[4/4] Running PyInstaller (onefile)"
& $Py -m PyInstaller helena.spec --clean --noconfirm

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Executable: dist\NeoCaixa.exe"
