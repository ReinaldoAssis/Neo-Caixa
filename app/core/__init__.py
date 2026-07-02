from app.core.config import settings
from app.core.module_registry import ModuleRegistry
from app.core.events import EventBus
from app.core.logger import logger
from app.core.db_service import DatabaseService

class AppContext:
    def __init__(self):
        self.config = settings
        self.event_bus = EventBus()
        self.module_registry = ModuleRegistry(self.event_bus)
        self.database = DatabaseService(settings)
        self.logger = logger

app_context = AppContext()
