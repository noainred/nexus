"""Portal-facing auto-update: report current vs available version and trigger
the (root) systemd update unit.

The actual upgrade is performed by ``deploy/auto-update.sh`` via the
``nexus-manager-update.service`` systemd unit (it rebuilds the venv and
restarts the service, which the non-root app process cannot do itself). This
router only *reports* status and *triggers* that unit without blocking.
"""
from __future__ import annotations

import asyncio
import glob
import os
import re
import zipfile
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException

from .. import __version__
from ..config import get_settings

router = APIRouter(prefix="/api/update", tags=["update"])

_VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _vkey(v: str):
    m = _VER_RE.search(v or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _abs(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else Path(os.getcwd()) / p


def _zip_version(path: str) -> Optional[str]:
    """Version from the ver_X.Y.Z.md marker inside the bundle, else filename."""
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                m = re.search(r"ver_(\d+\.\d+\.\d+)\.md", name)
                if m:
                    return m.group(1)
    except Exception:  # noqa: BLE001 - a bad zip just isn't a candidate
        pass
    m = _VER_RE.search(os.path.basename(path))
    return ".".join(m.groups()) if m else None


def _folder_latest(dirpath: Path) -> Optional[str]:
    best: Optional[str] = None
    for p in glob.glob(str(dirpath / "*.zip")):
        v = _zip_version(p)
        if v and (best is None or _vkey(v) > _vkey(best)):
            best = v
    return best


async def _remote_latest(url: str) -> Optional[str]:
    """Highest version advertised by the configured remote source."""
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as c:
        if url.startswith("github:"):
            repo = url[len("github:"):]
            r = await c.get(f"https://api.github.com/repos/{repo}/releases/tags/latest")
            r.raise_for_status()
            for asset in (r.json() or {}).get("assets", []):
                m = re.fullmatch(r"ver_(\d+\.\d+\.\d+)\.md", asset.get("name", ""))
                if m:
                    return m.group(1)
        elif url.startswith("http://") or url.startswith("https://"):
            r = await c.get(url)
            r.raise_for_status()
            vers = re.findall(r"nexus-manager-offline-v(\d+\.\d+\.\d+)\.zip", r.text)
            if vers:
                return max(vers, key=_vkey)
    return None


def _tail(path: Path, lines: int) -> List[str]:
    if not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
    except Exception:  # noqa: BLE001
        return []


@router.get("/status")
async def update_status() -> dict:
    """Current version + best available (watch folder and/or remote) + log tail."""
    s = get_settings()
    current = __version__
    folder = _folder_latest(_abs(s.update_dir))
    remote = None
    remote_error = None
    if s.update_url:
        try:
            remote = await _remote_latest(s.update_url)
        except Exception as exc:  # noqa: BLE001 - remote is best-effort
            remote_error = str(exc)[:200]
    cands = [v for v in (folder, remote) if v]
    available = max(cands, key=_vkey) if cands else None
    newer = bool(available and _vkey(available) > _vkey(current))
    return {
        "current": current,
        "folder": folder,
        "remote": remote,
        "remote_error": remote_error,
        "available": available,
        "update_available": newer,
        "source": s.update_url or "",
        "log": _tail(_abs(s.update_log), 25),
    }


@router.post("/run")
async def update_run() -> dict:
    """Trigger the systemd update unit (non-blocking — it restarts the app)."""
    cmd = ["sudo", "-n", "systemctl", "start", "--no-block",
           "nexus-manager-update.service"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, err = await asyncio.wait_for(proc.communicate(), timeout=15)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="sudo/systemctl 을 찾을 수 없습니다(미설치 환경).")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"업데이트 실행 불가: {exc}")
    if proc.returncode == 0:
        return {"ok": True, "detail": "업데이트를 시작했습니다. 새 버전이 있으면 곧 자동 재시작됩니다."}
    raise HTTPException(
        status_code=503,
        detail=("업데이트 트리거 실패 — 권한(sudo) 또는 systemd 서비스가 없습니다. "
                "감시 폴더에 zip을 넣으면 타이머가 5분 내 적용합니다. "
                f"{(err or b'').decode(errors='ignore')[:200]}"),
    )
