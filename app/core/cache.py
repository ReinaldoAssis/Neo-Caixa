from functools import lru_cache
from typing import Any, Optional
import time

class CacheManager:
    def __init__(self):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        expires_at = time.time() + ttl if ttl else None
        self._store[key] = (value, expires_at)

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def has(self, key: str) -> bool:
        return self.get(key) is not None
