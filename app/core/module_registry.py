import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.events import EventBus
from app.core.logger import logger


class ModuleRegistry:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._modules: Dict[str, dict] = {}
        self._routers: list = []
        self._default_module: Optional[str] = None

    def discover(self):
        try:
            import app.modules as modules_pkg
        except Exception as e:
            logger.error(f"Cannot import modules package: {e}")
            return
        for finder, name, ispkg in pkgutil.iter_modules(modules_pkg.__path__):
            if ispkg and not name.startswith("_"):
                self._load_module(name)

    def _load_module(self, name: str):
        try:
            mod = importlib.import_module(f"app.modules.{name}")
            manifest = getattr(mod, "manifest", None)
            if manifest is None:
                logger.warning(f"Module '{name}' has no manifest, skipping")
                return

            router = getattr(mod, "router", None)
            self._modules[name] = manifest

            if router is not None:
                self._routers.append(router)

            if manifest.get("is_default", False):
                if self._default_module is not None:
                    logger.warning(
                        f"Module '{name}' marked as default but '{self._default_module}' already set"
                    )
                self._default_module = name

            logger.info(f"Module loaded: {name} v{manifest.get('version', '?')}")
            self.event_bus.emit("module:loaded", {"name": name, "manifest": manifest})
        except Exception as e:
            logger.error(f"Failed to load module '{name}': {e}")

    def get(self, name: str) -> Optional[dict]:
        return self._modules.get(name)

    def all(self) -> Dict[str, dict]:
        return dict(self._modules)

    def list(self) -> list[str]:
        return list(self._modules.keys())

    @property
    def routers(self) -> list:
        return list(self._routers)

    @property
    def default_module(self) -> Optional[str]:
        return self._default_module
