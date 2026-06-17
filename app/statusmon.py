"""Background status poller.

Continuously probes every monitoring-enabled instance and caches the latest
``InstanceStatus`` in memory, so the dashboard can show the *current* value
instantly instead of probing on demand (which stalls on slow/unreachable
nodes). The UI reads the cache; a background loop keeps it fresh.
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional

from .config import get_settings
from .models import InstanceStatus
from .nexus_client import NexusClient, NexusError

_cache: Dict[str, InstanceStatus] = {}
_checked_at: Dict[str, float] = {}


async def probe_status(instance) -> InstanceStatus:
    """Probe a single instance, never raising — failures become status fields."""
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
    base.healthy = all(base.checks.values()) if base.checks else True
    try:
        repos = await client.list_repositories()
        base.repository_count = len(repos)
    except NexusError:
        base.repository_count = None
    return base


async def refresh_once(registry) -> None:
    """Probe every monitoring instance concurrently and update the cache."""
    insts = list(registry.monitoring())
    if not insts:
        return
    results = await asyncio.gather(
        *(probe_status(i) for i in insts), return_exceptions=True
    )
    now = time.time()
    for inst, res in zip(insts, results):
        if isinstance(res, InstanceStatus):
            _cache[inst.id] = res
            _checked_at[inst.id] = now


def get_status(instance_id: str) -> Optional[InstanceStatus]:
    return _cache.get(instance_id)


def checked_at(instance_id: str) -> Optional[float]:
    return _checked_at.get(instance_id)


def drop(instance_id: str) -> None:
    """Forget a cached node (e.g. when it's deleted/edited)."""
    _cache.pop(instance_id, None)
    _checked_at.pop(instance_id, None)


def _interval() -> float:
    return max(5.0, float(getattr(get_settings(), "status_poll_interval", 20.0)))


async def run_loop() -> None:
    """Background status poll loop, launched at app startup."""
    from .deps import registry

    # Prime the cache promptly on boot, then keep it fresh on the interval.
    while True:
        try:
            if registry.all():
                await refresh_once(registry)
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(_interval())
