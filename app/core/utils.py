import uuid
from datetime import datetime, timezone

def generate_id() -> str:
    return str(uuid.uuid4())

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def safe_get(d: dict, key: str, default=None):
    return d.get(key, default)
