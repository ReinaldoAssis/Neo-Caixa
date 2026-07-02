from typing import Callable, Dict, List, Any
from app.core.logger import logger

class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def on(self, event_name: str, handler: Callable):
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)

    def off(self, event_name: str, handler: Callable):
        if event_name in self._handlers:
            self._handlers[event_name].remove(handler)

    def emit(self, event_name: str, data: Any = None):
        handlers = self._handlers.get(event_name, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in event handler '{event_name}': {e}")

    def clear(self):
        self._handlers.clear()
