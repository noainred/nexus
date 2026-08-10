"""Security posture endpoints (anonymous access, admin accounts)."""

import asyncio
from typing import List

from fastapi import APIRouter, Depends

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import InstanceSecurity
from ..nexus_client import NexusClient, NexusError
from ..vulndb import scan_version

router = APIRouter(prefix="/api", tags=["security"])

_ADMIN_ROLE = "nx-admin"


async def _try(coro):
    """Await a NexusClient coroutine, returning (value, error) instead of raising."""
    try:
        return await coro, None
    except NexusError as exc:
        return None, exc


async def _security_for(instance) -> InstanceSecurity:
    """Probe one instance's security posture; never raises.

    The two read calls run concurrently — on slow/high-latency links this
    roughly halves per-instance scan time.
    """
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    result = InstanceSecurity(id=instance.id, name=instance.name)

    (anon, anon_exc), (users, users_exc), (version, _ver_exc) = await asyncio.gather(
        _try(client.get_anonymous()),
        _try(client.list_users()),
        _try(client.server_version()),
    )

    # A connection-level failure on the anonymous probe == unreachable node.
    if anon_exc is not None and anon_exc.status_code is None:
        result.reachable = False
        result.error = anon_exc.message
        result.risk = "unknown"
        return result

    if anon is not None:
        result.anonymous_enabled = bool(anon.get("enabled"))
    elif anon_exc is not None:
        result.error = anon_exc.message  # e.g. 403: account lacks permission

    if users is not None:
        result.user_count = len(users)
        result.admin_users = sorted(
            u.get("userId", "?") for u in users if _ADMIN_ROLE in (u.get("roles") or [])
        )
        admin = next((u for u in users if u.get("userId") == "admin"), None)
        result.admin_active = bool(admin and admin.get("status") == "active")
    elif users_exc is not None and result.error is None:
        result.error = users_exc.message

    # Version + known-CVE scan (Server header). Unknown version => not scanned.
    if version:
        result.version = version
        result.vulns = scan_version(version)

    # Derive a risk flag + human-readable issue list for at-a-glance scanning.
    issues: List[str] = []
    if result.anonymous_enabled:
        issues.append("익명 접근 허용")
    if result.admin_active:
        issues.append("기본 admin 계정 활성")
    for v in result.vulns:
        issues.append(f"취약 버전: {v['id']}")
    result.issues = issues
    result.risk = "unknown" if (anon is None and users is None) else ("warn" if issues else "ok")
    return result


@router.get("/security", response_model=List[InstanceSecurity])
async def security_all(
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceSecurity]:
    """Security posture for every managed instance (concurrent)."""
    results = await asyncio.gather(
        *(_security_for(instance) for instance in registry.monitoring())
    )
    return list(results)
