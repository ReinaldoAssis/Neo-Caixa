#!/usr/bin/env bash
set -e

echo "=== Helena Dev Mode ==="

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $API_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "[1/2] Starting FastAPI (port 8754)..."
uvicorn app.api:create_app --factory --host 127.0.0.1 --port 8754 --reload &
API_PID=$!

echo "[2/2] Starting Vite dev server (port 5173)..."
cd app/frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "FastAPI  : http://127.0.0.1:8754"
echo "Frontend : http://localhost:5173"
echo "Press Ctrl+C to stop"
echo ""

wait
