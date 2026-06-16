"""Node account management: create an admin user or change a user's password
on one or more managed Nexus instances.

When the target user is the very account the manager uses to connect, the
stored credential is updated in lockstep so a password change never locks the
manager out of that node.
"""
from __future__ import annotations

import asyncio
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..config import InstanceConfig, get_settings
from ..deps import InstanceRegistry, get_registry
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

_ADMIN_ROLE = "nx-admin"


class CreateAdminBody(BaseModel):
    instance_ids: List[str] = Field(default_factory=list)
    user_id: str
    password: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    roles: List[str] = Field(default_factory=lambda: [_ADMIN_ROLE])


class ChangePasswordBody(BaseModel):
    instance_ids: List[str] = Field(default_factory=list)
    user_id: str
    password: str


def _targets(registry: InstanceRegistry, ids: List[str]) -> List[InstanceConfig]:
    want = set(ids or [])
    return [i for i in registry.all() if i.id in want]


@router.get("/instances/{instance_id}/users")
async def list_node_users(
    instance_id: str, registry: InstanceRegistry = Depends(get_registry)
) -> dict:
    """List a node's user IDs (for the change-password picker)."""
    inst = registry.get(instance_id)
    client = NexusClient(inst, timeout=get_settings().request_timeout)
    try:
        users = await client.list_users()
    except NexusError as exc:
        return {"error": exc.message, "users": []}
    out = [
        {"userId": u.get("userId"),
         "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
         "admin": _ADMIN_ROLE in (u.get("roles") or [])}
        for u in users if isinstance(u, dict) and u.get("userId")
    ]
    return {"users": out}


@router.post("/create-admin")
async def create_admin(
    body: CreateAdminBody, registry: InstanceRegistry = Depends(get_registry)
) -> dict:
    """Create a user (admin role by default) on the selected instances."""
    if not body.user_id.strip() or not body.password:
        return {"error": "userId/비밀번호가 필요합니다.", "items": []}
    payload = {
        "userId": body.user_id.strip(),
        "firstName": body.first_name.strip() or body.user_id.strip(),
        "lastName": body.last_name.strip() or "admin",
        "emailAddress": body.email.strip() or f"{body.user_id.strip()}@local",
        "password": body.password,
        "status": "active",
        "roles": body.roles or [_ADMIN_ROLE],
    }

    async def one(inst: InstanceConfig) -> dict:
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            await client.create_user(payload)
            return {"instance_id": inst.id, "instance_name": inst.name, "ok": True}
        except NexusError as exc:
            return {"instance_id": inst.id, "instance_name": inst.name,
                    "ok": False, "error": exc.message}

    targets = _targets(registry, body.instance_ids)
    if not targets:
        return {"error": "대상 서버를 선택하세요.", "items": []}
    items = list(await asyncio.gather(*(one(i) for i in targets)))
    return {"user_id": payload["userId"], "roles": payload["roles"],
            "ok": sum(1 for i in items if i["ok"]), "total": len(items), "items": items}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordBody, registry: InstanceRegistry = Depends(get_registry)
) -> dict:
    """Change a user's password on the selected instances. If the target is the
    manager's own connect account, update the stored credential too."""
    if not body.user_id.strip() or not body.password:
        return {"error": "userId/비밀번호가 필요합니다.", "items": []}
    uid = body.user_id.strip()

    async def one(inst: InstanceConfig) -> dict:
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            await client.change_password(uid, body.password)
        except NexusError as exc:
            return {"instance_id": inst.id, "instance_name": inst.name,
                    "ok": False, "error": exc.message}
        synced = False
        # Avoid locking the manager out: if we just changed the account it uses
        # to connect, store the new password.
        if (inst.username or "") == uid:
            try:
                registry.update(inst.id, inst.model_copy(update={"password": body.password}))
                synced = True
            except Exception:  # noqa: BLE001 - password changed regardless
                synced = False
        return {"instance_id": inst.id, "instance_name": inst.name,
                "ok": True, "credential_synced": synced}

    targets = _targets(registry, body.instance_ids)
    if not targets:
        return {"error": "대상 서버를 선택하세요.", "items": []}
    items = list(await asyncio.gather(*(one(i) for i in targets)))
    return {"user_id": uid, "ok": sum(1 for i in items if i["ok"]),
            "total": len(items), "items": items}
