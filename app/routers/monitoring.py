"""Status and monitoring endpoints."""
from __future__ import annotations

import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_settings
from ..deps import InstanceRegistry, get_client, get_registry
from ..models import BlobStore, InstanceBlobStores, InstanceStatus
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["monitoring"])


async def _status_for(instance) -> InstanceStatus:
    """Probe a single instance, never raising — failures become status fields."""
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    base = InstanceStatus(
        id=instance.id,
        name=instance.name,
        base_url=instance.base_url,
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
