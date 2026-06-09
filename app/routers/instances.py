"""Instance listing and management (CRUD) endpoints."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from ..config import (
    InstanceConfig,
    get_settings,
    instances_to_yaml,
    parse_document,
)
from .. import restore as restore_mod
from ..deps import InstanceRegistry, get_registry
from ..models import (
    CompareFields,
    GroupOrder,
    PingConfig,
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
        group=cfg.group,
        verify_tls=cfg.verify_tls,
        use_in_monitoring=cfg.use_in_monitoring,
        use_in_comparison=cfg.use_in_comparison,
        is_reference=cfg.is_reference,
    )


@router.get("", response_model=List[InstanceSummary])
async def list_instances(
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceSummary]:
    """Return the managed instances (without passwords)."""
    return [_summary(i) for i in registry.all()]


@router.get("/group-order", response_model=GroupOrder)
async def get_group_order(
    registry: InstanceRegistry = Depends(get_registry),
) -> GroupOrder:
    return GroupOrder(groups=registry.group_order())


@router.put("/group-order", response_model=GroupOrder)
async def set_group_order(
    body: GroupOrder, registry: InstanceRegistry = Depends(get_registry)
) -> GroupOrder:
    registry.set_group_order(body.groups)
    return GroupOrder(groups=registry.group_order())


@router.get("/compare-fields", response_model=CompareFields)
async def get_compare_fields(
    registry: InstanceRegistry = Depends(get_registry),
) -> CompareFields:
    return CompareFields(fields=registry.compare_fields())


@router.put("/compare-fields", response_model=CompareFields)
async def set_compare_fields(
    body: CompareFields, registry: InstanceRegistry = Depends(get_registry)
) -> CompareFields:
    registry.set_compare_fields(body.fields)
    return CompareFields(fields=registry.compare_fields())


@router.get("/ping-config", response_model=PingConfig)
async def get_ping_config(
    registry: InstanceRegistry = Depends(get_registry),
) -> PingConfig:
    return PingConfig(**registry.ping_config())


@router.put("/ping-config", response_model=PingConfig)
async def set_ping_config(
    body: PingConfig, registry: InstanceRegistry = Depends(get_registry)
) -> PingConfig:
    registry.set_ping_config(body.interval, body.warn_pct, body.crit_pct)
    return PingConfig(**registry.ping_config())


@router.get("/export")
async def export_instances(
    registry: InstanceRegistry = Depends(get_registry),
) -> Response:
    """Download the full server list as a YAML backup (includes passwords)."""
    text = instances_to_yaml(
        registry.all(),
        registry.group_order(),
        registry.compare_fields(),
        registry.ping_config(),
    )
    return Response(
        content=text,
        media_type="application/x-yaml",
        headers={"Content-Disposition": 'attachment; filename="instances-backup.yaml"'},
    )


@router.post("/import", response_model=List[InstanceSummary])
async def import_instances(
    request: Request,
    mode: str = Query("replace", pattern="^(replace|merge)$"),
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceSummary]:
    """Import a previously exported server list (YAML or JSON).

    ``mode=replace`` (default) overwrites the whole list; ``mode=merge``
    upserts the imported entries by id, keeping the rest.
    """
    raw = (await request.body()).decode("utf-8")
    try:
        document = parse_document(raw)
    except Exception as exc:  # noqa: BLE001 - surface a clean 400
        raise HTTPException(status_code=400, detail=f"유효하지 않은 구성 파일: {exc}")
    if not document.instances:
        raise HTTPException(status_code=400, detail="가져올 서버가 없습니다.")
    if mode == "merge":
        registry.merge(document.instances)
    else:
        registry.replace_all(document.instances)
    if document.group_order:
        registry.set_group_order(document.group_order)
    if document.compare_fields:
        registry.set_compare_fields(document.compare_fields)
    registry.set_ping_config(
        document.ping_interval, document.ping_warn_pct, document.ping_crit_pct
    )
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
        group=body.group,
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
        group=body.group,
        verify_tls=body.verify_tls,
        use_in_monitoring=body.use_in_monitoring,
        use_in_comparison=body.use_in_comparison,
        is_reference=existing.is_reference,  # preserved; set via /reference
    )
    registry.update(instance_id, cfg)
    return _summary(cfg)


@router.post("/{instance_id}/reference", response_model=List[InstanceSummary])
async def toggle_reference(
    instance_id: str, registry: InstanceRegistry = Depends(get_registry)
) -> List[InstanceSummary]:
    """Designate (or clear) the baseline/reference instance for comparisons."""
    inst = registry.get(instance_id)  # 404 if unknown
    if inst.is_reference:
        registry.clear_reference()
    else:
        registry.set_reference(instance_id)
    return [_summary(i) for i in registry.all()]


@router.get("/{instance_id}/config-export")
async def export_instance_config(
    instance_id: str,
    registry: InstanceRegistry = Depends(get_registry),
) -> Response:
    """Download the live Nexus configuration of one server as a JSON snapshot.

    Aggregates the readable config (repositories with full settings, blob
    stores, cleanup/routing policies, security, tasks) via the REST API. Each
    section is best-effort, so a section the account cannot read is noted under
    ``errors`` instead of failing the whole download.
    """
    inst = registry.get(instance_id)  # 404 if unknown
    client = NexusClient(inst, timeout=get_settings().request_timeout)
    try:
        config = await client.export_configuration()
    except NexusError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)
    payload = {
        "instance": {"id": inst.id, "name": inst.name, "base_url": inst.base_url},
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **config,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", inst.name).strip("_") or inst.id
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"nexus-config-{safe}-{stamp}.json"
    return Response(
        content=text,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{instance_id}/config-restore")
async def restore_instance_config(
    instance_id: str,
    request: Request,
    sections: str = Query("", description="Comma-separated sections to restore; empty = repositories + dependencies."),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Recreate configuration on a target server from an uploaded snapshot.

    The request body is the JSON produced by ``/config-export``. Idempotent and
    best-effort: existing items are skipped, failures are reported per item.
    """
    inst = registry.get(instance_id)  # 404 if unknown
    raw = (await request.body()).decode("utf-8")
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 스냅샷 JSON: {exc}")
    sel = {s.strip() for s in sections.split(",") if s.strip()} or None
    client = NexusClient(inst, timeout=get_settings().request_timeout)
    return await restore_mod.apply(client, snapshot, sel)


@router.delete("/{instance_id}", status_code=204, response_class=Response)
async def delete_instance(
    instance_id: str, registry: InstanceRegistry = Depends(get_registry)
) -> Response:
    registry.remove(instance_id)  # 404 if unknown
    return Response(status_code=204)
