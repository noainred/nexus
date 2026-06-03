"""Instance listing and management (CRUD) endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Response

from ..config import InstanceConfig, get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import (
    InstanceCreate,
    InstanceSummary,
    InstanceTestRequest,
    InstanceTestResult,
    InstanceUpdate,
)
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api/instances", tags=["instances"])


def _summary(cfg: InstanceConfig) -> InstanceSummary:
    return InstanceSummary(
        id=cfg.id,
        name=cfg.name,
        base_url=cfg.base_url,
        username=cfg.username,
        verify_tls=cfg.verify_tls,
        use_in_monitoring=cfg.use_in_monitoring,
        use_in_comparison=cfg.use_in_comparison,
    )


@router.get("", response_model=List[InstanceSummary])
async def list_instances(
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceSummary]:
    """Return the managed instances (without passwords)."""
    return [_summary(i) for i in registry.all()]


@router.post("/test", response_model=InstanceTestResult)
async def test_instance(body: InstanceTestRequest) -> InstanceTestResult:
    """Probe a Nexus server with the given credentials without saving it."""
    cfg = InstanceConfig(
        id="__test__",
        name="__test__",
        base_url=body.base_url,
        username=body.username,
        password=body.password,
        verify_tls=body.verify_tls,
    )
    client = NexusClient(cfg, timeout=get_settings().request_timeout)
    result = InstanceTestResult()
    try:
        ping = await client.ping()
    except NexusError as exc:
        result.error = exc.message
        return result
    result.reachable = True
    result.response_ms = ping["response_ms"]
    result.healthy = all(ping["checks"].values()) if ping["checks"] else True
    try:
        repos = await client.list_repositories()
        result.repository_count = len(repos)
    except NexusError:
        pass  # reachable, but the account may lack browse permission
    return result


@router.post("", response_model=InstanceSummary, status_code=201)
async def create_instance(
    body: InstanceCreate, registry: InstanceRegistry = Depends(get_registry)
) -> InstanceSummary:
    cfg = InstanceConfig(
        id=body.id,
        name=body.name,
        base_url=body.base_url,
        username=body.username,
        password=body.password,
        verify_tls=body.verify_tls,
        use_in_monitoring=body.use_in_monitoring,
        use_in_comparison=body.use_in_comparison,
    )
    registry.add(cfg)  # 409 if id exists
    return _summary(cfg)


@router.put("/{instance_id}", response_model=InstanceSummary)
async def update_instance(
    instance_id: str,
    body: InstanceUpdate,
    registry: InstanceRegistry = Depends(get_registry),
) -> InstanceSummary:
    existing = registry.get(instance_id)  # 404 if unknown
    # Keep the stored password when the form leaves it blank.
    password = body.password if body.password else existing.password
    cfg = InstanceConfig(
        id=instance_id,
        name=body.name,
        base_url=body.base_url,
        username=body.username,
        password=password,
        verify_tls=body.verify_tls,
        use_in_monitoring=body.use_in_monitoring,
        use_in_comparison=body.use_in_comparison,
    )
    registry.update(instance_id, cfg)
    return _summary(cfg)


@router.delete("/{instance_id}", status_code=204, response_class=Response)
async def delete_instance(
    instance_id: str, registry: InstanceRegistry = Depends(get_registry)
) -> Response:
    registry.remove(instance_id)  # 404 if unknown
    return Response(status_code=204)
