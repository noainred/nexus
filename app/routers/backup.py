"""Scheduled configuration-backup endpoints."""
from __future__ import annotations

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
    registry.set_backup_config(cfg.enabled, cfg.time, cfg.keep)
    return BackupConfig(**registry.backup_config())


@router.post("/backup-run")
async def run_backup_now(
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Back up every managed server's configuration right now."""
    return await backup_mod.run_backup(registry, get_settings())


@router.get("/backups")
async def list_backups() -> list:
    return backup_mod.list_backups(get_settings())


@router.get("/backups/{ts}/{name}")
async def download_backup(ts: str, name: str) -> Response:
    path = backup_mod.backup_file_path(get_settings(), ts, name)
    if path is None:
        raise HTTPException(status_code=404, detail="백업 파일을 찾을 수 없습니다.")
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{ts}_{name}"'},
    )
