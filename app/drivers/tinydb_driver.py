from tinydb import TinyDB, Query
from typing import Dict, Any, List, Optional
from app.core.database import AbstractDatabaseDriver

class TinyDBDriver(AbstractDatabaseDriver):
    def __init__(self, db_path: str):
        self._db = TinyDB(db_path)

    def _table(self, table: str):
        return self._db.table(table)

    def insert(self, table: str, data: Dict[str, Any]) -> str:
        doc_id = self._table(table).insert(data)
        return str(doc_id)

    def update(self, table: str, doc_id: str, data: Dict[str, Any]) -> bool:
        tbl = self._table(table)
        Q = Query()
        ids = tbl.update(data, doc_ids=[int(doc_id)])
        return len(ids) > 0

    def delete(self, table: str, doc_id: str) -> bool:
        tbl = self._table(table)
        ids = tbl.remove(doc_ids=[int(doc_id)])
        return len(ids) > 0

    def get(self, table: str, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._table(table).get(doc_id=int(doc_id))

    def search(self, table: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        Q = Query()
        tbl = self._table(table)
        q = None
        for key, value in query.items():
            cond = (Q[key] == value)
            q = cond if q is None else (q & cond)
        return tbl.search(q) if q is not None else tbl.all()

    def all(self, table: str) -> List[Dict[str, Any]]:
        return self._table(table).all()

    def count(self, table: str, query: Optional[Dict[str, Any]] = None) -> int:
        if query:
            return len(self.search(table, query))
        return len(self._table(table))
