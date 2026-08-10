"""Scheduled configuration-backup endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response

from .. import backup as backup_mod
from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import BackupConfig

router = APIRouter(prefix="/api", tags=["backup"])


@router.get("/backup-config", response_model=BackupConfig)
async def get_backup_config(
    registry: InstanceRegistry = Depends(get_registry),
) -> BackupConfig:
    return BackupConfig(**registry.backup_config())


@router.put("/backup-config", response_model=BackupConfig)
async def set_backup_config(
    cfg: BackupConfig,
    registry: InstanceRegistry = Depends(get_registry),
) -> BackupConfig:
    registry.set_backup_config(cfg.enabled, cfg.time, cfg.keep, cfg.path)
    return BackupConfig(**registry.backup_config())


def _root(registry: InstanceRegistry):
    return backup_mod.resolve_root(registry.backup_config().get("path", ""), get_settings())


@router.post("/backup-run")
async def run_backup_now(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Back up every managed server's configuration right now."""
    return await backup_mod.run_backup(registry, get_settings())


@router.get("/backups")
async def list_backups(
    registry: InstanceRegistry = Depends(get_registry),
) -> list:
    return backup_mod.list_backups(_root(registry))


@router.get("/backups/{ts}/{name}")
async def download_backup(
    ts: str,
    name: str,
    registry: InstanceRegistry = Depends(get_registry),
) -> Response:
    path = backup_mod.backup_file_path(_root(registry), ts, name)
    if path is None:
        raise HTTPException(status_code=404, detail="백업 파일을 찾을 수 없습니다.")
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{ts}_{name}"'},
    )


# -- DR readiness audit ------------------------------------------------------

import asyncio
import re
from datetime import datetime, timedelta, timezone

from ..nexus_client import NexusClient, NexusError


def _parse_dt(s):
    if not s:
        return None
    # datetime.fromisoformat is 3.7+, but the appliance runs on Python 3.6.8;
    # parse the common Nexus timestamp shapes with strptime instead.
    text = str(s).strip().replace("Z", "+0000")
    # normalize a "+00:00" style offset to strptime's "+0000".
    m = re.match(r"^(.*[+-]\d{2}):(\d{2})$", text)
    if m:
        text = m.group(1) + m.group(2)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


@router.get("/dr-audit")
async def dr_audit(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Disaster-recovery readiness.

    Configuration is covered by this manager's scheduled config backup; the
    *data* side needs each Nexus server's own 'Export databases for backup'
    (db.backup) task. Report per server whether one exists, when it last ran
    and whether it succeeded.
    """
    instances = registry.monitoring()

    async def one(inst):
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            tasks = await client.list_tasks()
        except NexusError as exc:
            return {"id": inst.id, "name": inst.name, "error": exc.message, "state": "unknown"}
        backups = [t for t in tasks if "backup" in (t.type or "").lower()]
        if not backups:
            return {"id": inst.id, "name": inst.name, "tasks": 0, "state": "crit",
                    "detail": "DB 백업 태스크 없음 — Nexus UI에서 'Admin - Export databases for backup' 작업을 만드세요."}
        latest = sorted(backups, key=lambda t: t.last_run or "", reverse=True)[0]
        last_dt = _parse_dt(latest.last_run)
        stale = last_dt is None or (datetime.now(timezone.utc) - last_dt) > timedelta(days=8)
        result = (latest.last_run_result or "").upper()
        if stale:
            state, detail = "warn", "최근 8일 내 실행 기록 없음 — 스케줄을 확인하세요."
        elif result and result != "OK":
            state, detail = "warn", f"마지막 실행 결과: {latest.last_run_result}"
        else:
            state, detail = "ok", "정상"
        return {"id": inst.id, "name": inst.name, "tasks": len(backups),
                "last_run": latest.last_run, "last_result": latest.last_run_result,
                "next_run": latest.next_run, "state": state, "detail": detail}

    servers = list(await asyncio.gather(*(one(i) for i in instances)))
    counts = {"ok": 0, "warn": 0, "crit": 0, "unknown": 0}
    for s in servers:
        counts[s.get("state", "unknown")] = counts.get(s.get("state", "unknown"), 0) + 1

    cfg = registry.backup_config()
    runs = backup_mod.list_backups(_root(registry))
    return {
        "config_backup": {
            "enabled": cfg.get("enabled"),
            "time": cfg.get("time"),
            "last_run": runs[0]["timestamp"] if runs else "",
            "runs": len(runs),
        },
        "counts": counts,
        "servers": servers,
    }


@router.post("/dr-run-backup")
async def run_db_backups_everywhere(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Run every DB-backup task on every monitored server right now."""
    instances = registry.monitoring()

    async def one(inst):
        client = NexusClient(inst, timeout=get_settings().request_timeout)
        try:
            tasks = await client.list_tasks()
        except NexusError as exc:
            return {"id": inst.id, "name": inst.name, "error": exc.message}
        backups = [t for t in tasks if "backup" in (t.type or "").lower()]
        started = 0
        errors = []
        for t in backups:
            try:
                await client.run_task(t.id)
                started += 1
            except NexusError as exc:
                errors.append(exc.message)
        return {"id": inst.id, "name": inst.name, "tasks": len(backups),
                "started": started, "errors": errors}

    return {"servers": list(await asyncio.gather(*(one(i) for i in instances)))}
