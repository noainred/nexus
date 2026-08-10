"""Infrastructure ping history + disk-saturation forecast endpoints."""

from fastapi import APIRouter, Depends, Query

from .. import diskmon, pingmon
from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import PingHistory
from ..storage import run_in_thread

router = APIRouter(prefix="/api", tags=["infra"])


@router.get("/disk-forecast")
async def disk_forecast(
    sample: bool = Query(False, description="Take a fresh sample first."),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Blob-store usage forecast: growth per day and days until 90% full."""
    if sample:
        await diskmon.sample_once(registry, get_settings())
    rows = diskmon.forecast(registry, get_settings())
    counts = {"crit": 0, "warn": 0, "ok": 0}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return {"counts": counts, "stores": rows}


@router.get("/disk-history")
async def disk_history(
    days: int = Query(60, ge=1, le=200),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Blob-store usage% time series (for the trend chart)."""
    return {"stores": diskmon.history(registry, get_settings(), days)}


@router.get("/ping-history", response_model=PingHistory)
async def ping_history(
    days: int = Query(1, ge=1, le=366),
    registry: InstanceRegistry = Depends(get_registry),
) -> PingHistory:
    names = {i.id: i.name for i in registry.all()}
    groups = {i.id: i.group for i in registry.all()}
    cfg = registry.ping_config()
    # query()는 큰 CSV를 통째로 읽어 파싱하므로 스레드로 offload — 이벤트 루프가
    # 한 사용자의 넓은 기간 조회에 막혀 대시보드 전체가 멈추지 않도록 한다.
    res = await run_in_thread(
        pingmon.query, days, names, cfg["warn_pct"], cfg["crit_pct"], None, set(names)
    )
    for s in res["series"]:
        s["group"] = groups.get(s["id"], "")
    return PingHistory(**res)
