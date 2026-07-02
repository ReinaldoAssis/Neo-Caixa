import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Any, List
from app.core.events import EventBus
from app.core.logger import logger

class ModuleRegistry:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._modules: Dict[str, Any] = {}

    def discover(self):
        modules_path = Path(__file__).parent.parent / "modules"
        if not modules_path.exists():
            return
        for finder, name, ispkg in pkgutil.iter_modules([str(modules_path)]):
            if ispkg:
                self._load_module(name)

    def _load_module(self, name: str):
        try:
            mod = importlib.import_module(f"app.modules.{name}")
            manifest = getattr(mod, "manifest", None)
            if manifest:
                self._modules[name] = manifest
                logger.info(f"Module loaded: {name} v{manifest.get('version', '?')}")
                self.event_bus.emit("module:loaded", {"name": name, "manifest": manifest})
        except Exception as e:
            logger.error(f"Failed to load module '{name}': {e}")

    def get(self, name: str) -> Any:
        return self._modules.get(name)

    def all(self) -> Dict[str, Any]:
        return self._modules

    def list(self) -> List[str]:
        return list(self._modules.keys())
