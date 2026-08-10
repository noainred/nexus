"""Status and monitoring endpoints."""

import asyncio
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_client, get_registry
from ..models import BlobStore, InstanceBlobStores, InstanceStatus, NodeMetrics
from ..nexus_client import NexusClient, NexusError
from .. import statusmon
from .. import __version__

router = APIRouter(prefix="/api", tags=["monitoring"])


def _fmt_ts(ts: Optional[float]) -> Optional[str]:
    return time.strftime("%H:%M:%S", time.localtime(ts)) if ts else None


# Backwards-compatible alias — the live probe now lives in statusmon so the
# background poller and on-demand endpoints share one implementation.
_status_for = statusmon.probe_status


@router.get("/status", response_model=List[InstanceStatus])
async def status_all(
    fresh: bool = Query(False, description="Probe live instead of using the cache."),
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceStatus]:
    """Overview status. Served from the background poller cache (instant); only
    not-yet-cached nodes are probed live (or all of them when ``fresh=true``)."""
    insts = list(registry.monitoring())
    out: List[InstanceStatus] = []
    missing = []
    for inst in insts:
        cached = None if fresh else statusmon.get_status(inst.id)
        if cached is not None:
            cached.checked_at = _fmt_ts(statusmon.checked_at(inst.id))
            cached.cached = True
            out.append(cached)
        else:
            missing.append(inst)
    if missing:
        # Cold cache: ping-only (fast) so each card shows the moment its ping
        # answers; the background poller backfills repository_count shortly.
        live = await asyncio.gather(*(statusmon.probe_status(i, with_repos=False) for i in missing))
        for s in live:
            s.checked_at = _fmt_ts(time.time())
        out.extend(live)
    order = {inst.id: n for n, inst in enumerate(insts)}
    out.sort(key=lambda s: order.get(s.id, 1 << 30))
    return out


@router.get("/summary")
async def summary(registry: InstanceRegistry = Depends(get_registry)) -> dict:
    """Aggregated fleet snapshot for *other servers/systems* to consume (public,
    read-only). Built from the background status cache, so it's instant and adds
    no load. Poll this to mirror the dashboard's health elsewhere."""
    insts = list(registry.monitoring())
    up = warn = down = unknown = 0
    repo_total = 0
    resp: List[float] = []
    groups: dict = {}
    items = []
    for inst in insts:
        s = statusmon.get_status(inst.id)
        g = (inst.group or "").strip() or "(미지정)"
        gd = groups.setdefault(g, {"name": g, "total": 0, "up": 0, "warn": 0, "down": 0, "unknown": 0})
        gd["total"] += 1
        if s is None:
            st = "unknown"; unknown += 1
            items.append({"id": inst.id, "name": inst.name, "group": inst.group,
                          "state": st, "reachable": None, "healthy": None,
                          "response_ms": None, "repository_count": None, "checked_at": None})
        else:
            if not s.reachable:
                st = "down"; down += 1
            elif not s.healthy:
                st = "warn"; warn += 1
            else:
                st = "up"; up += 1
            if s.repository_count:
                repo_total += s.repository_count
            if s.response_ms is not None:
                resp.append(s.response_ms)
            items.append({"id": inst.id, "name": inst.name, "group": inst.group,
                          "state": st, "reachable": s.reachable, "healthy": s.healthy,
                          "response_ms": s.response_ms, "repository_count": s.repository_count,
                          "checked_at": _fmt_ts(statusmon.checked_at(inst.id))})
        gd[st] += 1
    return {
        "manager_version": __version__,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "servers": {"total": len(insts), "up": up, "warn": warn, "down": down, "unknown": unknown},
        "repository_total": repo_total,
        "avg_response_ms": round(sum(resp) / len(resp), 1) if resp else None,
        "groups": list(groups.values()),
        "instances": items,
    }


@router.get("/instances/{instance_id}/status", response_model=InstanceStatus)
async def status_one(
    instance_id: str,
    fresh: bool = Query(False, description="Probe live instead of using the cache."),
    registry: InstanceRegistry = Depends(get_registry),
) -> InstanceStatus:
    instance = registry.get(instance_id)
    if not fresh:
        cached = statusmon.get_status(instance_id)
        if cached is not None:
            cached.checked_at = _fmt_ts(statusmon.checked_at(instance_id))
            cached.cached = True
            return cached
    # Not cached yet → ping-only (fast); poller backfills repository_count.
    st = await statusmon.probe_status(instance, with_repos=(False if not fresh else True))
    st.checked_at = _fmt_ts(time.time())
    return st


def _gauge(gauges: dict, *names: str):
    for name in names:
        val = gauges.get(name)
        if isinstance(val, dict) and "value" in val:
            return val["value"]
    return None


async def _metrics_for(instance) -> NodeMetrics:
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    result = NodeMetrics(id=instance.id, name=instance.name)
    try:
        data = await client.get_metrics()
    except NexusError as exc:
        result.reachable = False
        result.error = exc.message
        return result

    gauges = data.get("gauges", {}) if isinstance(data, dict) else {}
    used = _gauge(gauges, "jvm.memory.heap.used")
    mx = _gauge(gauges, "jvm.memory.heap.max")
    usage = _gauge(gauges, "jvm.memory.heap.usage")
    result.heap_used_bytes = int(used) if isinstance(used, (int, float)) else None
    result.heap_max_bytes = int(mx) if isinstance(mx, (int, float)) and mx > 0 else None
    if isinstance(usage, (int, float)):
        result.heap_usage_pct = round(usage * 100, 1)
    elif result.heap_used_bytes and result.heap_max_bytes:
        result.heap_usage_pct = round(
            result.heap_used_bytes / result.heap_max_bytes * 100, 1
        )
    threads = _gauge(gauges, "jvm.threads.count", "jvm.thread-states.count")
    result.thread_count = int(threads) if isinstance(threads, (int, float)) else None
    uptime = _gauge(gauges, "jvm.attribute.uptime", "jvm.uptime")
    result.uptime_ms = int(uptime) if isinstance(uptime, (int, float)) else None
    return result


@router.get("/metrics", response_model=List[NodeMetrics])
async def metrics_all(
    registry: InstanceRegistry = Depends(get_registry),
) -> List[NodeMetrics]:
    """JVM/resource metrics for every monitoring-enabled node."""
    results = await asyncio.gather(
        *(_metrics_for(instance) for instance in registry.monitoring())
    )
    return list(results)


@router.get("/instances/{instance_id}/blobstores", response_model=List[BlobStore])
async def list_blobstores(instance_id: str) -> List[BlobStore]:
    client: NexusClient = get_client(instance_id)
    try:
        return await client.list_blobstores()
    except NexusError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)


async def _blobstores_for(instance) -> InstanceBlobStores:
    """Fetch one instance's blob stores, never raising (errors -> fields)."""
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    result = InstanceBlobStores(id=instance.id, name=instance.name)
    try:
        stores = await client.list_blobstores()
    except NexusError as exc:
        result.reachable = False
        result.error = exc.message
        return result

    result.blobstores = stores
    sizes = [s.total_size_bytes for s in stores if s.total_size_bytes is not None]
    counts = [s.blob_count for s in stores if s.blob_count is not None]
    result.total_size_bytes = sum(sizes) if sizes else None
    result.blob_count = sum(counts) if counts else None
    return result


@router.get("/blobstores", response_model=List[InstanceBlobStores])
async def blobstores_all(
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceBlobStores]:
    """Blob store usage for every instance, for the site-by-site overview."""
    results = await asyncio.gather(
        *(_blobstores_for(instance) for instance in registry.monitoring())
    )
    return list(results)
