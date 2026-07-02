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

    for router in app_context.module_registry.routers:
        app.include_router(router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": app_context.config.VERSION}

    @app.get("/api/modules")
    async def list_modules():
        modules = {}
        for slug, manifest in app_context.module_registry.all().items():
            modules[slug] = {
                "name": manifest.get("name", slug),
                "version": manifest.get("version", ""),
                "description": manifest.get("description", ""),
                "menus": manifest.get("menus", []),
                "is_default": manifest.get("is_default", False),
            }
        return {
            "modules": modules,
            "default_module": app_context.module_registry.default_module,
        }

    frontend_dist = Path(__file__).parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app
