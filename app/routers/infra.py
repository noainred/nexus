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
    return PingHistory(**pingmon.query(days, names))
