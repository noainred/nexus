"""Background status poller.

Continuously probes every monitoring-enabled instance and caches the latest
``InstanceStatus`` in memory, so the dashboard can show the *current* value
instantly instead of probing on demand (which stalls on slow/unreachable
nodes). The UI reads the cache; a background loop keeps it fresh.
"""

import asyncio
import time
from typing import Dict, Optional

from .config import get_settings
from .models import InstanceStatus
from .nexus_client import NexusClient, NexusError

_cache: Dict[str, InstanceStatus] = {}
_checked_at: Dict[str, float] = {}


async def probe_status(instance, with_repos: bool = True) -> InstanceStatus:
    """Probe a single instance, never raising — failures become status fields.

    ``with_repos=False`` returns as soon as the ping completes (skips the
    heavier repository listing) so an on-demand card can show up the moment its
    ping answers; the background poller fills repository_count with the default.
    """
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
    if with_repos:
        try:
            repos = await client.list_repositories()
            base.repository_count = len(repos)
        except NexusError:
            base.repository_count = None
    return base


async def refresh_once(registry) -> None:
    """Probe every monitoring instance and update the cache *per node* as each
    finishes — so fast nodes are cached within their own response time and a
    single slow node can't hold the whole cache cold."""
    insts = list(registry.monitoring())
    if not insts:
        return

    async def _one(inst) -> None:
        try:
            res = await probe_status(inst)
        except Exception:  # pragma: no cover - defensive, probe_status rarely raises
            return
        _cache[inst.id] = res
        _checked_at[inst.id] = time.time()

    await asyncio.gather(*(_one(i) for i in insts), return_exceptions=True)


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
