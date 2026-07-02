from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.core import app_context

def create_app() -> FastAPI:
    app = FastAPI(
        title=app_context.config.APP_NAME,
        version=app_context.config.VERSION,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app_context.module_registry.discover()

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": app_context.config.VERSION}

    @app.get("/api/modules")
    async def list_modules():
        return {"modules": app_context.module_registry.list()}

    frontend_dist = Path(__file__).parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app
