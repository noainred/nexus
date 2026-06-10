"""Scheduled configuration backups.

Periodically exports every managed Nexus server's configuration (the same
snapshot as the per-server '설정 ↓' download) to local JSON files, so a lost or
wiped server can be recovered quickly via the existing config import/restore.

Backups are grouped per run under ``<backup_dir>/<timestamp>/<server>.json``.
Only configuration is captured (not artifact/blob data) — see the restore docs.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import Settings, get_settings
from .nexus_client import NexusClient, NexusError


def resolve_root(path: str, settings: Settings) -> Path:
    """Backup directory: the user-configured path, else the default."""
    p = Path((path or "").strip() or settings.backup_dir)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "server"


async def run_backup(registry, settings: Settings) -> dict:
    """Back up every managed server's configuration once. Returns a summary."""
    root = resolve_root(registry.backup_config().get("path", ""), settings)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = root / ts
    out.mkdir(parents=True, exist_ok=True)
    items: List[dict] = []
    for inst in registry.all():
        entry = {"id": inst.id, "name": inst.name}
        client = NexusClient(inst, timeout=settings.request_timeout)
        try:
            cfg = await client.export_configuration()
            payload = {
                "instance": {"id": inst.id, "name": inst.name, "base_url": inst.base_url},
                "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                **cfg,
            }
            fname = f"{_safe(inst.name)}.json"
            (out / fname).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            repos = len((payload.get("sections") or {}).get("repositories") or [])
            entry.update(ok=True, file=fname, repositories=repos)
        except NexusError as exc:
            entry.update(ok=False, error=exc.message)
        except Exception as exc:  # noqa: BLE001 - never let one server abort the run
            entry.update(ok=False, error=str(exc))
        items.append(entry)

    # If nothing was written (e.g. no servers), drop the empty folder.
    if not any((out / (i.get("file") or "")).is_file() for i in items):
        shutil.rmtree(out, ignore_errors=True)

    _prune(root, registry.backup_config().get("keep", 14))
    ok = sum(1 for i in items if i.get("ok"))
    return {"timestamp": ts, "ok": ok, "total": len(items),
            "directory": str(out), "items": items}


def _prune(root: Path, keep: int) -> None:
    if not root.exists():
        return
    dirs = sorted((d for d in root.iterdir() if d.is_dir()), reverse=True)
    for d in dirs[max(1, int(keep)):]:
        shutil.rmtree(d, ignore_errors=True)


def list_backups(root: Path) -> List[dict]:
    if not root.exists():
        return []
    out: List[dict] = []
    for d in sorted((d for d in root.iterdir() if d.is_dir()), reverse=True):
        files = [
            {"name": f.name, "size": f.stat().st_size}
            for f in sorted(d.glob("*.json"))
        ]
        if files:
            out.append({"timestamp": d.name, "files": files})
    return out


def backup_file_path(root: Path, ts: str, name: str) -> Optional[Path]:
    """Resolve a backup file, guarding against path traversal."""
    if not re.fullmatch(r"[0-9][0-9-]{0,20}", ts or ""):
        return None
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.json", name or ""):
        return None
    p = root / ts / name
    return p if p.is_file() else None


async def run_loop() -> None:
    """Daily scheduled backup at the configured HH:MM (local time)."""
    from .deps import registry

    last_date: Optional[str] = None
    while True:
        try:
            cfg = registry.backup_config()
            if cfg.get("enabled"):
                now = datetime.now()
                try:
                    hh, mm = (int(x) for x in str(cfg["time"]).split(":"))
                except ValueError:
                    hh, mm = -1, -1
                today = now.date().isoformat()
                if now.hour == hh and now.minute == mm and last_date != today:
                    last_date = today
                    await run_backup(registry, get_settings())
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(30)
