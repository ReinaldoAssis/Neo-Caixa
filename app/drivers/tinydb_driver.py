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

    def _resolve_doc_ids(self, table: str, doc_id: str) -> list[int]:
        try:
            return [int(doc_id)]
        except ValueError:
            Q = Query()
            results = self._table(table).search(Q.id == doc_id)
            return [r.doc_id for r in results]

    def get(self, table: str, doc_id: str) -> Optional[Dict[str, Any]]:
        doc_ids = self._resolve_doc_ids(table, doc_id)
        assert len(doc_ids) <= 1
        if not doc_ids:
            return None
        return self._table(table).get(doc_id=doc_ids[0])

    def update(self, table: str, doc_id: str, data: Dict[str, Any]) -> bool:
        tbl = self._table(table)
        doc_ids = self._resolve_doc_ids(table, doc_id)
        if not doc_ids:
            return False
        ids = tbl.update(data, doc_ids=doc_ids)
        return len(ids) > 0

    def delete(self, table: str, doc_id: str) -> bool:
        tbl = self._table(table)
        doc_ids = self._resolve_doc_ids(table, doc_id)
        if not doc_ids:
            return False
        ids = tbl.remove(doc_ids=doc_ids)
        return len(ids) > 0

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
