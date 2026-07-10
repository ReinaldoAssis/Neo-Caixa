from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sys

from app.core import app_context
from app.core import updater


def _frontend_dist() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return Path(__file__).parent / "frontend" / "dist"



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

    @app.get("/api/update/check")
    async def update_check():
        return updater.check_for_update(app_context.config.GITHUB_REPO)

    @app.post("/api/update/download")
    async def update_download(payload: dict):
        url = payload.get("download_url")
        name = payload.get("asset_name")
        if not url or not name:
            return {"downloaded": False, "error": "download_url e asset_name sao obrigatorios."}
        try:
            path = updater.download_update(url, name)
            return {"downloaded": True, "path": str(path), "error": None}
        except Exception as exc:
            return {"downloaded": False, "error": str(exc)}

    @app.post("/api/update/apply")
    async def update_apply(payload: dict):
        path = payload.get("path")
        if not path:
            return {"applied": False, "error": "path e obrigatorio."}
        return updater.apply_update(path)

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

    frontend_dist = _frontend_dist()
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app
