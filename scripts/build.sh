#!/usr/bin/env bash
set -e

echo "=== Helena Build ==="

echo "[1/3] Building frontend..."
cd app/frontend && npm run build

echo "[2/3] Building executable with PyInstaller..."
cd ../..
pyinstaller helena.spec --clean --noconfirm

echo "[3/3] Done!"
echo "Executable: dist/helena"
