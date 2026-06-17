"""Portal-facing auto-update: editable source config, version check, and
trigger of the (root) systemd update unit.

The settings entered in the dashboard are persisted to ``update-config.json``
so both this app and the ``deploy/auto-update.sh`` watcher use the same source.
The actual upgrade is performed by the ``nexus-manager-update.service`` systemd
unit (it rebuilds the venv and restarts the service).
"""
from __future__ import annotations

import asyncio
import glob
import json
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import __version__
from ..config import get_settings

router = APIRouter(prefix="/api/update", tags=["update"])

_VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_DEFAULTS = {"source": "server", "url": "", "token": "", "interval": 300,
             "auto_install": True, "edges": []}


def _vkey(v: str):
    m = _VER_RE.search(v or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _abs(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else Path(os.getcwd()) / p


def _cfg_path() -> Path:
    return _abs(get_settings().update_config_file)


def _load_cfg() -> dict:
    cfg = dict(_DEFAULTS)
    p = _cfg_path()
    if p.is_file():
        try:
            cfg.update({k: v for k, v in json.loads(p.read_text("utf-8")).items() if k in _DEFAULTS})
        except Exception:  # noqa: BLE001
            pass
    if not cfg.get("url"):
        cfg["url"] = get_settings().update_url or ""
    return cfg


def _masked(cfg: dict) -> dict:
    out = dict(cfg)
    out["token"] = bool(cfg.get("token"))   # never echo the token back
    return out


def _zip_version(path: str) -> Optional[str]:
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                m = re.search(r"ver_(\d+\.\d+\.\d+)\.md", name)
                if m:
                    return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    m = _VER_RE.search(os.path.basename(path))
    return ".".join(m.groups()) if m else None


def _folder_latest(dirpath: Path) -> Optional[str]:
    best: Optional[str] = None
    for p in glob.glob(str(dirpath / "*.zip")) + glob.glob(str(dirpath / "*.tar.gz")):
        v = _zip_version(p) or (_VER_RE.search(os.path.basename(p)) and ".".join(_VER_RE.search(os.path.basename(p)).groups()))
        if v and (best is None or _vkey(v) > _vkey(best)):
            best = v
    return best


async def _remote_latest(cfg: dict) -> Optional[str]:
    """Highest version advertised by the configured remote source."""
    url = (cfg.get("url") or "").strip()
    if not url:
        return None
    token = cfg.get("token") or ""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, verify=False) as c:
        if cfg.get("source") == "github" or url.startswith("github:"):
            repo = url[len("github:"):] if url.startswith("github:") else url
            m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git|/|$)", repo)
            if m:
                repo = m.group(1)
            r = await c.get(f"https://api.github.com/repos/{repo}/releases/tags/latest", headers=headers)
            r.raise_for_status()
            for asset in (r.json() or {}).get("assets", []):
                mm = re.fullmatch(r"ver_(\d+\.\d+\.\d+)\.md", asset.get("name", ""))
                if mm:
                    return mm.group(1)
            return _VER_RE.search((r.json() or {}).get("name", "")) and ".".join(_VER_RE.search(r.json()["name"]).groups())
        # "server" — an internal mirror directory: prefer versions.json. A plain
        # HTTP index is also supported, but Nexus *raw* repos reject browsing
        # ("404 You can't browse this way"), so versions.json is required there.
        base = url if url.endswith("/") else url + "/"
        try:
            vr = await c.get(base + "versions.json", headers=headers)
            if vr.status_code == 200:
                data = vr.json()
                v = data.get("version") or data.get("latest")
                if v:
                    return ".".join(_VER_RE.search(v).groups())
        except Exception:  # noqa: BLE001 - fall back to listing
            pass
        try:
            r = await c.get(url, headers=headers)
            r.raise_for_status()
            vers = re.findall(r"nexus-manager-offline-v(\d+\.\d+\.\d+)\.(?:zip|tar\.gz)", r.text)
            if vers:
                return max(vers, key=_vkey)
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(
            f"versions.json을 찾을 수 없습니다 — {base}versions.json 에 "
            '{"version":"x.y.z","file":"…zip"} 를 올리세요. '
            "(Nexus raw 저장소는 폴더 목록 조회를 막으므로 versions.json이 필수입니다)"
        )


def _tail(path: Path, lines: int) -> List[str]:
    if not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
    except Exception:  # noqa: BLE001
        return []


async def _edge_version(client: httpx.AsyncClient, url: str) -> dict:
    """Read one edge manager's running version from its /healthz (public)."""
    base = url.rstrip("/")
    try:
        r = await client.get(base + "/healthz")
        r.raise_for_status()
        return {"url": url, "version": (r.json() or {}).get("version"), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "version": None, "error": str(exc)[:120]}


async def _check_edges(urls: List[str], deploy_code: str) -> List[dict]:
    urls = [u.strip() for u in (urls or []) if u and u.strip()]
    if not urls:
        return []
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, verify=False) as c:
        edges = list(await asyncio.gather(*(_edge_version(c, u) for u in urls)))
    for e in edges:
        e["outdated"] = bool(e["version"] and _vkey(e["version"]) < _vkey(deploy_code))
    return edges


@router.get("/status")
async def update_status() -> dict:
    s = get_settings()
    cfg = _load_cfg()
    current = __version__
    folder = _folder_latest(_abs(s.update_dir))
    remote = None
    remote_error = None
    if cfg.get("url"):
        try:
            remote = await _remote_latest(cfg)
        except Exception as exc:  # noqa: BLE001 - remote is best-effort
            remote_error = str(exc)[:200]
    cands = [v for v in (folder, remote) if v]
    available = max(cands, key=_vkey) if cands else None
    newer = bool(available and _vkey(available) > _vkey(current))
    edges = await _check_edges(cfg.get("edges") or [], current)
    return {
        "current": current,
        "folder": folder,
        "remote": remote,
        "remote_error": remote_error,
        "available": available,
        "update_available": newer,
        "deploy_code": current,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "edges": edges,
        "edges_total": len(edges),
        "edges_outdated": sum(1 for e in edges if e.get("outdated")),
        "edges_unreachable": sum(1 for e in edges if e.get("error")),
        "config": _masked(cfg),
        "log": _tail(_abs(s.update_log), 25),
    }


class UpdateConfig(BaseModel):
    source: str = "server"
    url: str = ""
    token: Optional[str] = None       # None = keep existing; "" = clear
    interval: int = 300
    auto_install: bool = True
    clear_token: bool = False
    edges: Optional[List[str]] = None  # None = keep existing


@router.post("/config")
async def update_config(body: UpdateConfig) -> dict:
    src = body.source if body.source in ("server", "github") else "server"
    url = (body.url or "").strip()
    if url and src == "github":
        if not (url.startswith("github:") or "github.com" in url):
            raise HTTPException(status_code=400, detail="GitHub 소스는 'github:owner/repo' 또는 github.com 주소여야 합니다.")
    if url and src == "server" and not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Update Server 소스는 http(s):// 주소여야 합니다.")
    cur = _load_cfg()
    token = cur.get("token", "")
    if body.clear_token:
        token = ""
    elif body.token is not None and body.token != "":
        token = body.token
    edges = cur.get("edges") or []
    if body.edges is not None:
        edges = [u.strip() for u in body.edges if u and u.strip()]
    cfg = {
        "source": src, "url": url, "token": token,
        "interval": max(30, int(body.interval or 300)),
        "auto_install": bool(body.auto_install),
        "edges": edges,
    }
    p = _cfg_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)   # may hold a token
    except OSError:
        pass
    return {"ok": True, "config": _masked(cfg)}


@router.post("/run")
async def update_run() -> dict:
    """Trigger the systemd update unit (non-blocking — it restarts the app)."""
    cmd = ["sudo", "-n", "systemctl", "start", "--no-block", "nexus-manager-update.service"]
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
                "감시 폴더에 zip을 넣으면 타이머가 적용합니다. "
                f"{(err or b'').decode(errors='ignore')[:200]}"),
    )
