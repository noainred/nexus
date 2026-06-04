"""Infrastructure ping history endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import pingmon
from ..deps import InstanceRegistry, get_registry
from ..models import PingHistory

router = APIRouter(prefix="/api", tags=["infra"])


@router.get("/ping-history", response_model=PingHistory)
async def ping_history(
    days: int = Query(1, ge=1, le=366),
    registry: InstanceRegistry = Depends(get_registry),
) -> PingHistory:
    names = {i.id: i.name for i in registry.all()}
    groups = {i.id: i.group for i in registry.all()}
    cfg = registry.ping_config()
    res = pingmon.query(days, names, cfg["warn_pct"], cfg["crit_pct"])
    for s in res["series"]:
        s["group"] = groups.get(s["id"], "")
    return PingHistory(**res)
