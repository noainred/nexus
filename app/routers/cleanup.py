"""Cleanup policy endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException

from ..models import CleanupPolicy, CleanupPolicyCreate
from ..nexus_client import NexusClient, NexusError
from ..deps import get_client

router = APIRouter(
    prefix="/api/instances/{instance_id}/cleanup-policies", tags=["cleanup"]
)


def _translate(exc: NexusError) -> HTTPException:
    return HTTPException(status_code=exc.status_code or 502, detail=exc.message)


def _build_criteria(payload: CleanupPolicyCreate) -> dict:
    """Map the simplified create payload to Nexus' criteria object."""
    criteria: dict = {}
    if payload.criteria_last_blob_updated is not None:
        criteria["lastBlobUpdated"] = payload.criteria_last_blob_updated
    if payload.criteria_last_downloaded is not None:
        criteria["lastDownloaded"] = payload.criteria_last_downloaded
    if payload.criteria_release_type:
        criteria["releaseType"] = payload.criteria_release_type
    if payload.criteria_asset_regex:
        criteria["regex"] = payload.criteria_asset_regex
    return criteria


@router.get("", response_model=List[CleanupPolicy])
async def list_cleanup_policies(instance_id: str) -> List[CleanupPolicy]:
    client: NexusClient = get_client(instance_id)
    try:
        return await client.list_cleanup_policies()
    except NexusError as exc:
        raise _translate(exc)


@router.post("", response_model=CleanupPolicy, status_code=201)
async def create_cleanup_policy(
    instance_id: str, body: CleanupPolicyCreate
) -> CleanupPolicy:
    client: NexusClient = get_client(instance_id)
    criteria = _build_criteria(body)
    if not criteria:
        raise HTTPException(
            status_code=400, detail="At least one cleanup criterion is required."
        )
    payload = {
        "name": body.name,
        "format": body.format,
        "notes": body.notes or "",
        "criteria": criteria,
    }
    try:
        await client.create_cleanup_policy(payload)
    except NexusError as exc:
        raise _translate(exc)
    return CleanupPolicy(
        name=body.name,
        format=body.format,
        notes=body.notes,
        criteria=criteria,
    )


# -- Fleet-wide cleanup audit / bulk actions --------------------------------

import asyncio

from fastapi import Depends, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry

fleet_router = APIRouter(prefix="/api", tags=["cleanup"])


def _is_docker_gc(t) -> bool:
    """'Docker - Delete unused manifests and images' task."""
    ttype = (t.type or "").lower()
    name = (t.name or "").lower()
    return "docker.gc" in ttype or ("manifest" in name and "docker" in name) or \
        ("unused" in name and "manifest" in name)


@fleet_router.get("/cleanup-audit")
async def cleanup_audit(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Per-server cleanup hygiene: policies, repos without a cleanup policy,
    blob stores, and whether a 'Compact blob store' task exists/last ran."""
    instances = registry.monitoring()

    async def one(inst):
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        row = {"id": inst.id, "name": inst.name}
        try:
            policies, tasks, blobs = await asyncio.gather(
                client.list_cleanup_policies(),
                client.list_tasks(),
                client.list_blobstores(),
            )
        except NexusError as exc:
            row["error"] = exc.message
            return row
        compact = [t for t in tasks if (t.type or "") == "blobstore.compact"]
        cleanup_tasks = [t for t in tasks if "cleanup" in (t.type or "")]
        docker_gc = [t for t in tasks if _is_docker_gc(t)]
        row.update(
            policies=len(policies),
            policy_names=[p.name for p in policies],
            blobstores=len(blobs),
            compact_tasks=len(compact),
            compact_last=max((t.last_run or "" for t in compact), default=""),
            compact_last_result=next(
                (t.last_run_result for t in sorted(compact, key=lambda x: x.last_run or "", reverse=True)),
                None,
            ),
            cleanup_tasks=len(cleanup_tasks),
            docker_gc_tasks=len(docker_gc),
            docker_gc_last=max((t.last_run or "" for t in docker_gc), default=""),
            has_docker=False,
        )
        # Repos (non-group) without any cleanup policy assigned + docker presence.
        try:
            settings_list = await client.list_repository_settings()
            repos = [r for r in settings_list if (r.get("type") or "").lower() != "group"]
            without = [
                r.get("name") for r in repos
                if not ((r.get("cleanup") or {}).get("policyNames"))
            ]
            row.update(
                repos=len(repos), repos_without_cleanup=len(without),
                repos_without_cleanup_names=without[:50],
                has_docker=any((r.get("format") or "").lower() == "docker" for r in settings_list),
            )
        except NexusError:
            row.update(repos=None, repos_without_cleanup=None)
        return row

    rows = await asyncio.gather(*(one(i) for i in instances))
    return {"servers": list(rows)}


@fleet_router.post("/cleanup-compact-run")
async def run_compact_everywhere(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Run every 'Compact blob store' task on every monitored server."""
    instances = registry.monitoring()

    async def one(inst):
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            tasks = await client.list_tasks()
        except NexusError as exc:
            return {"id": inst.id, "name": inst.name, "error": exc.message}
        compact = [t for t in tasks if (t.type or "") == "blobstore.compact"]
        started = 0
        errors = []
        for t in compact:
            try:
                await client.run_task(t.id)
                started += 1
            except NexusError as exc:
                errors.append(exc.message)
        return {"id": inst.id, "name": inst.name, "tasks": len(compact),
                "started": started, "errors": errors}

    return {"servers": list(await asyncio.gather(*(one(i) for i in instances)))}


@fleet_router.post("/cleanup-docker-run")
async def run_docker_gc_everywhere(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Run every 'Docker - Delete unused manifests and images' task on every
    monitored server (step 1 of the two-step Docker cleanup; run Compact after
    they finish to reclaim disk)."""
    instances = registry.monitoring()

    async def one(inst):
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            tasks = await client.list_tasks()
        except NexusError as exc:
            return {"id": inst.id, "name": inst.name, "error": exc.message}
        gc = [t for t in tasks if _is_docker_gc(t)]
        started = 0
        errors = []
        for t in gc:
            try:
                await client.run_task(t.id)
                started += 1
            except NexusError as exc:
                errors.append(exc.message)
        return {"id": inst.id, "name": inst.name, "tasks": len(gc),
                "started": started, "errors": errors}

    return {"servers": list(await asyncio.gather(*(one(i) for i in instances)))}


@fleet_router.post("/cleanup-push-policy")
async def push_policy_everywhere(
    source_id: str = Query(...),
    name: str = Query(..., description="Cleanup policy name on the source."),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Copy one cleanup policy from a source server to every other server
    (created only where missing)."""
    src = registry.get(source_id)
    sc = NexusClient(src, timeout=get_settings().request_timeout)
    try:
        policies = await sc.list_cleanup_policies()
    except NexusError as exc:
        raise HTTPException(status_code=502, detail=f"원본 정책 조회 실패: {exc.message}")
    policy = next((p for p in policies if p.name == name), None)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"원본에 '{name}' 정책이 없습니다.")
    payload = {"name": policy.name, "format": policy.format,
               "notes": policy.notes or "", "criteria": policy.criteria}

    async def one(inst):
        if inst.id == source_id:
            return None
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            existing = {p.name for p in await client.list_cleanup_policies()}
            if name in existing:
                return {"id": inst.id, "name": inst.name, "status": "skip", "detail": "이미 존재"}
            await client.create_cleanup_policy(payload)
            return {"id": inst.id, "name": inst.name, "status": "ok", "detail": "생성됨"}
        except NexusError as exc:
            return {"id": inst.id, "name": inst.name, "status": "fail", "detail": exc.message}

    results = [r for r in await asyncio.gather(*(one(i) for i in registry.monitoring())) if r]
    return {"policy": name, "servers": results}
