.PHONY: dev-api dev-frontend dev build build-frontend build-bin clean install

APP_NAME := helena

dev:
	@echo "=== Helena Dev Mode ==="
	@trap 'kill 0' EXIT; \
		echo "[1/2] Starting FastAPI (port 8754)..."; \
		uvicorn app.api:create_app --factory --host 127.0.0.1 --port 8754 --reload & \
		echo "[2/2] Starting Vite dev server (port 5173)..."; \
		cd app/frontend && npm run dev & \
		echo ""; \
		echo "FastAPI  : http://127.0.0.1:8754"; \
		echo "Frontend : http://localhost:5173"; \
		echo "Press Ctrl+C to stop"; \
		echo ""; \
		wait

dev-api:
	@echo "[helena] Starting FastAPI..."
	uvicorn app.api:create_app --factory --host 127.0.0.1 --port 8754 --reload

dev-frontend:
	@echo "[helena] Starting Vite dev server..."
	cd app/frontend && npm run dev

build: build-frontend build-bin

build-frontend:
	@echo "[helena] Building frontend..."
	cd app/frontend && npm run build

build-bin:
	@echo "[helena] Building executable with PyInstaller..."
	pyinstaller helena.spec --clean --noconfirm

clean:
	rm -rf build/ dist/ __pycache__/ app/frontend/dist/ app/**/__pycache__/
	rm -rf app/**/*/__pycache__/
	rm -rf app/**/*/*/__pycache__/

install:
	pip install -r requirements.txt
	cd app/frontend && npm install
