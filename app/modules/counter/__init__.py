from fastapi import APIRouter

from app.modules.counter.manifest import manifest

router = APIRouter(prefix="/api/counter", tags=["Counter"])

_state = {"count": 0}


@router.get("/state")
async def get_state():
    return {"count": _state["count"]}


@router.post("/increment")
async def increment():
    _state["count"] += 1
    return {"count": _state["count"]}


@router.post("/reset")
async def reset():
    _state["count"] = 0
    return {"count": _state["count"]}
