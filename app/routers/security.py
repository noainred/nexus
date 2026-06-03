"""Security posture endpoints (anonymous access, admin accounts)."""
from __future__ import annotations

import asyncio
from typing import List

from fastapi import APIRouter, Depends

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import InstanceSecurity
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["security"])

_ADMIN_ROLE = "nx-admin"


async def _security_for(instance) -> InstanceSecurity:
    """Probe one instance's security posture; never raises."""
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    result = InstanceSecurity(id=instance.id, name=instance.name)

    try:
        anon = await client.get_anonymous()
        result.anonymous_enabled = bool(anon.get("enabled"))
    except NexusError as exc:
        if exc.status_code is None:  # connection-level failure -> unreachable
            result.reachable = False
            result.error = exc.message
            return result
        result.error = exc.message  # e.g. 403: account lacks permission

    try:
        users = await client.list_users()
        result.user_count = len(users)
        result.admin_users = sorted(
            u.get("userId", "?")
            for u in users
            if _ADMIN_ROLE in (u.get("roles") or [])
        )
        admin = next((u for u in users if u.get("userId") == "admin"), None)
        result.admin_active = bool(admin and admin.get("status") == "active")
    except NexusError as exc:
        if result.error is None:
            result.error = exc.message

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
