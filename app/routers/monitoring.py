"""Status and monitoring endpoints."""
from __future__ import annotations

import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_settings
from ..deps import InstanceRegistry, get_client, get_registry
from ..models import BlobStore, InstanceBlobStores, InstanceStatus, NodeMetrics
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["monitoring"])


async def _status_for(instance) -> InstanceStatus:
    """Probe a single instance, never raising — failures become status fields."""
    # Wait out a *slow but alive* node (high latency is still 정상): the read
    # timeout stays at request_timeout. Truly unreachable nodes still fail fast
    # because _client caps the *connect* phase (~6s), and the overview loads
    # each card independently so one slow node never freezes the board.
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    base = InstanceStatus(
        id=instance.id,
        name=instance.name,
        base_url=instance.base_url,
        group=instance.group,
        reachable=False,
        healthy=False,
    )
    try:
        ping = await client.ping()
    except NexusError as exc:
        base.error = exc.message
        return base

    base.reachable = True
    base.response_ms = ping["response_ms"]
    base.checks = ping["checks"]
    # Healthy when reachable and no subsystem reports unhealthy.
    base.healthy = all(base.checks.values()) if base.checks else True

    try:
        repos = await client.list_repositories()
        base.repository_count = len(repos)
    except NexusError:
        base.repository_count = None

    return base


@router.get("/status", response_model=List[InstanceStatus])
async def status_all(
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceStatus]:
    """Probe every monitoring-enabled instance concurrently for the overview."""
    results = await asyncio.gather(
        *(_status_for(instance) for instance in registry.monitoring())
    )
    return list(results)


@router.get("/instances/{instance_id}/status", response_model=InstanceStatus)
async def status_one(
    instance_id: str, registry: InstanceRegistry = Depends(get_registry)
) -> InstanceStatus:
    instance = registry.get(instance_id)
    return await _status_for(instance)


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
