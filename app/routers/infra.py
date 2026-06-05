"""Infrastructure ping + throughput history endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import pingmon, throughput
from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import (
    PingHistory,
    ThroughputConfig,
    ThroughputHistory,
)

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


@router.get("/throughput-history", response_model=ThroughputHistory)
async def throughput_history(
    days: int = Query(1, ge=1, le=366),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputHistory:
    names = {i.id: i.name for i in registry.all()}
    groups = {i.id: i.group for i in registry.all()}
    cfg = registry.throughput_config()
    res = throughput.query(days, names, cfg["warn_pct"], cfg["crit_pct"])
    for s in res["series"]:
        s["group"] = groups.get(s["id"], "")
    return ThroughputHistory(**res)


@router.get("/throughput-config", response_model=ThroughputConfig)
async def get_throughput_config(
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputConfig:
    return ThroughputConfig(**registry.throughput_config())


@router.put("/throughput-config", response_model=ThroughputConfig)
async def set_throughput_config(
    cfg: ThroughputConfig,
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputConfig:
    registry.set_throughput_config(
        cfg.path, cfg.time, cfg.size_mb, cfg.warn_pct, cfg.crit_pct
    )
    return ThroughputConfig(**registry.throughput_config())


@router.post("/throughput-run", response_model=ThroughputHistory)
async def run_throughput(
    days: int = Query(1, ge=1, le=366),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputHistory:
    """Run one throughput measurement now, then return refreshed history."""
    cfg = registry.throughput_config()
    if cfg["path"]:
        size = max(1, int(cfg["size_mb"])) * 1024 * 1024
        await throughput.record_once(registry, get_settings(), cfg["path"], size)
    names = {i.id: i.name for i in registry.all()}
    groups = {i.id: i.group for i in registry.all()}
    res = throughput.query(days, names, cfg["warn_pct"], cfg["crit_pct"])
    for s in res["series"]:
        s["group"] = groups.get(s["id"], "")
    return ThroughputHistory(**res)
