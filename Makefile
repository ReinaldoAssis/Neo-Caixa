.PHONY: dev dev-api dev-frontend build build-frontend build-bin clean install

APP_NAME := helena

dev: dev-api dev-frontend

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

install:
	pip install -r requirements.txt
	cd app/frontend && npm install
