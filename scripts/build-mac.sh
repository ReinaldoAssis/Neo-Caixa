#!/usr/bin/env bash
set -euo pipefail

# Build Neo Caixa onefile for macOS.
# Run from project root:  ./scripts/build-mac.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Neo Caixa - macOS build ==="

# Resolve venv python (create if missing). Never rely on `activate`.
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "[venv] .venv not found, creating"
  python3 -m venv .venv
fi

echo "[1/4] Installing Python deps"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt

echo "[2/4] Building frontend (npm install + build)"
cd app/frontend
npm install
npm run build
cd "$ROOT"

echo "[3/4] Cleaning old build artifacts"
rm -rf build dist

echo "[4/4] Running PyInstaller (onefile)"
"$PY" -m PyInstaller helena.spec --clean --noconfirm

echo ""
echo "Done."
echo "  App bundle : dist/NeoCaixa.app"
echo "  Binary     : dist/NeoCaixa"
echo ""
echo "Run: open dist/NeoCaixa.app"
