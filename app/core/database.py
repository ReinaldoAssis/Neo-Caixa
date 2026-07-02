from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

class AbstractDatabaseDriver(ABC):
    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> str:
        ...

    @abstractmethod
    def update(self, table: str, doc_id: str, data: Dict[str, Any]) -> bool:
        ...

    @abstractmethod
    def delete(self, table: str, doc_id: str) -> bool:
        ...

    @abstractmethod
    def get(self, table: str, doc_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def search(self, table: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def all(self, table: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def count(self, table: str, query: Optional[Dict[str, Any]] = None) -> int:
        ...
