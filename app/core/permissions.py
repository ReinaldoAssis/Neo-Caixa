from typing import Dict, List, Optional, Any
from app.core.logger import logger

class PermissionManager:
    def __init__(self):
        self._permissions: Dict[str, List[str]] = {}

    def register(self, module: str, permissions: List[str]):
        self._permissions[module] = permissions
        logger.info(f"Permissions registered for module '{module}'")

    def has(self, module: str, permission: str) -> bool:
        return permission in self._permissions.get(module, [])

    def get_module_permissions(self, module: str) -> List[str]:
        return self._permissions.get(module, [])

    def all(self) -> Dict[str, List[str]]:
        return dict(self._permissions)
