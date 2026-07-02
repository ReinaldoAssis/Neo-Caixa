from app.core.database import AbstractDatabaseDriver
from app.core.config import Settings
from app.drivers.tinydb_driver import TinyDBDriver

class DatabaseService:
    def __init__(self, settings: Settings):
        self._driver = self._load_driver(settings)

    def _load_driver(self, settings: Settings) -> AbstractDatabaseDriver:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if settings.DB_DRIVER == "tinydb":
            return TinyDBDriver(str(settings.DB_PATH))
        raise ValueError(f"Unsupported database driver: {settings.DB_DRIVER}")

    @property
    def driver(self) -> AbstractDatabaseDriver:
        return self._driver

    def insert(self, table: str, data: dict) -> str:
        return self._driver.insert(table, data)

    def update(self, table: str, doc_id: str, data: dict) -> bool:
        return self._driver.update(table, doc_id, data)

    def delete(self, table: str, doc_id: str) -> bool:
        return self._driver.delete(table, doc_id)

    def get(self, table: str, doc_id: str):
        return self._driver.get(table, doc_id)

    def search(self, table: str, query: dict):
        return self._driver.search(table, query)

    def all(self, table: str):
        return self._driver.all(table)

    def count(self, table: str, query: dict = None) -> int:
        return self._driver.count(table, query)
