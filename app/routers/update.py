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


_RAW_GH_RE = re.compile(r"^https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/(.+)$")
_DIR_GH_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/(?:raw|tree|blob)/(.+)$")


def _gh_contents_api(url: str) -> Optional[str]:
    """Convert a GitHub raw / branch-folder URL to the contents API base.

    ``raw.githubusercontent.com/{o}/{r}/{ref...}/{dir}`` or
    ``github.com/{o}/{r}/(raw|tree|blob)/{ref...}/{dir}`` →
    ``api.github.com/repos/{o}/{r}/contents/{dir}?ref={ref...}``.

    The last path segment is the directory and the rest is the ref, so branch
    names containing '/' (e.g. ``claude/foo-bar``) work. This lets a *private*
    repo's ``download/`` folder be read with a token — no GitHub Release needed.
    Returns None when the URL is not a GitHub branch-folder URL.
    """
    m = _RAW_GH_RE.match(url or "") or _DIR_GH_RE.match(url or "")
    if not m:
        return None
    owner, repo, rest = m.groups()
    ref, _, dirpath = rest.rpartition("/")
    if not ref or not dirpath:
        return None
    return "https://api.github.com/repos/%s/%s/contents/%s?ref=%s" % (owner, repo, dirpath, ref)


def _gh_join(base: str, name: str) -> str:
    """Append a filename to a contents-API base, keeping any ``?ref=…`` query."""
    if "?" in base:
        head, _, query = base.partition("?")
        return head.rstrip("/") + "/" + name + "?" + query
    return base.rstrip("/") + "/" + name


def _abs(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else Path(os.getcwd()) / p


def _cfg_path() -> Path:
    return _abs(get_settings().update_config_file)


def _load_cfg(include_env: bool = True) -> dict:
    """Effective update config. ``include_env=False`` returns only what is
    stored in the file — use it for read-modify-write so the env-var fallback
    URL never gets materialized into the persisted config."""
    cfg = dict(_DEFAULTS)
    p = _cfg_path()
    if p.is_file():
        try:
            cfg.update({k: v for k, v in json.loads(p.read_text("utf-8")).items() if k in _DEFAULTS})
        except Exception:  # noqa: BLE001
            pass
    if include_env and not cfg.get("url"):
        cfg["url"] = get_settings().update_url or ""
    return cfg


def _url_fits_source(url: str, src: str) -> bool:
    if src == "github":
        return url.startswith("github:") or "github.com" in url or "raw.githubusercontent.com" in url
    return url.startswith("http://") or url.startswith("https://")


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
    verify = get_settings().verify_tls
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, verify=verify) as c:
        if cfg.get("source") == "github" or url.startswith("github:"):
            api = _gh_contents_api(url)
            if api:
                # Private/public branch *download folder* — no Release needed.
                # Prefer versions.json (read raw via contents API), else list the
                # folder for the highest nexus-manager-offline-vX.Y.Z.zip.
                gh = {"Accept": "application/vnd.github.raw"}
                if token:
                    gh["Authorization"] = f"Bearer {token}"
                try:
                    vr = await c.get(_gh_join(api, "versions.json"), headers=gh)
                    if vr.status_code == 200:
                        data = vr.json()
                        v = data.get("version") or data.get("latest")
                        if v and _VER_RE.search(str(v)):
                            return ".".join(_VER_RE.search(str(v)).groups())
                except Exception:  # noqa: BLE001 - fall back to a directory listing
                    pass
                lh = {"Accept": "application/vnd.github+json"}
                if token:
                    lh["Authorization"] = f"Bearer {token}"
                r = await c.get(api, headers=lh)
                r.raise_for_status()
                listing = r.json()
                items = listing if isinstance(listing, list) else []
                vers = [mm.group(1)
                        for it in items if isinstance(it, dict)
                        for mm in [re.fullmatch(r"nexus-manager-offline-v(\d+\.\d+\.\d+)\.zip", it.get("name", ""))]
                        if mm]
                if vers:
                    return max(vers, key=_vkey)
                raise RuntimeError(
                    "GitHub 폴더에서 versions.json 또는 nexus-manager-offline-vX.Y.Z.zip 을 "
                    "찾지 못했습니다 — 브랜치/폴더 경로와 토큰(비공개 레포) 권한을 확인하세요."
                )
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


async def _edge_version(client: httpx.AsyncClient, url: str, retries: int = 0) -> dict:
    """Read one edge manager's running version from its /healthz (public).

    ``retries`` re-probes once after a short pause — used by the explicit
    connection-test endpoint so a transiently dropped edge reconnects on the
    spot (the regular status poll keeps retries=0 to stay fast).
    """
    import time
    base = url.rstrip("/")
    last_err = None
    for attempt in range(retries + 1):
        if attempt:
            await asyncio.sleep(0.5)
        start = time.perf_counter()
        try:
            r = await client.get(base + "/healthz")
            r.raise_for_status()
            ms = round((time.perf_counter() - start) * 1000)
            return {"url": url, "version": (r.json() or {}).get("version"),
                    "error": None, "latency_ms": ms}
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)[:120]
    return {"url": url, "version": None, "error": last_err, "latency_ms": None}


async def _check_edges(urls: List[str], deploy_code: str, retries: int = 0) -> List[dict]:
    urls = [u.strip() for u in (urls or []) if u and u.strip()]
    if not urls:
        return []
    verify = get_settings().verify_tls
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, verify=verify) as c:
        edges = list(await asyncio.gather(*(_edge_version(c, u, retries) for u in urls)))
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


class EdgeTest(BaseModel):
    url: Optional[str] = None   # None = 등록된 엣지 전체 테스트


@router.post("/edge-test")
async def edge_test(body: EdgeTest) -> dict:
    """등록된 엣지 노드의 연결을 즉시 재점검한다(연결 분리 시 재연결 확인용).

    설정에 저장된 엣지 URL만 대상으로 허용한다 — 임의 URL을 받으면 매니저가
    내부망 아무 주소나 찔러보는 SSRF 통로가 되므로, 미등록 URL은 400."""
    cfg = _load_cfg()
    registered = [u.strip() for u in (cfg.get("edges") or []) if u and u.strip()]
    if not registered:
        raise HTTPException(status_code=400, detail="등록된 엣지가 없습니다 — 설정에서 엣지 목록을 먼저 저장하세요.")
    target = (body.url or "").strip()
    if target:
        if target not in registered:
            raise HTTPException(status_code=400, detail="등록된 엣지 URL이 아닙니다 — 설정에 저장된 엣지만 테스트할 수 있습니다.")
        urls = [target]
    else:
        urls = registered
    # 명시적 테스트이므로 1회 재시도 — 일시적 끊김이면 그 자리에서 재연결된다.
    edges = await _check_edges(urls, __version__, retries=1)
    ok = sum(1 for e in edges if e.get("version"))
    return {"deploy_code": __version__, "tested": len(edges), "connected": ok,
            "unreachable": len(edges) - ok, "edges": edges}


class UpdateConfig(BaseModel):
    source: str = "server"
    url: str = ""                     # "" = keep existing (accidental-wipe guard)
    token: Optional[str] = None       # None/"" = keep existing; clear via clear_token
    interval: int = 300
    auto_install: bool = True
    clear_token: bool = False
    clear_url: bool = False           # explicit opt-in to erase the source URL
    edges: Optional[List[str]] = None  # None = keep existing


@router.post("/config")
async def update_config(body: UpdateConfig) -> dict:
    src = body.source if body.source in ("server", "github") else "server"
    # 파일에 저장된 값만 기준으로 병합 — env 폴백 URL이 파일에 고착되는 것 방지.
    cur = _load_cfg(include_env=False)
    url = (body.url or "").strip()
    if body.clear_url:
        if url:
            raise HTTPException(
                status_code=400,
                detail="url과 clear_url을 함께 보낼 수 없습니다 — 새 URL 저장과 삭제 중 하나만 지정하세요.")
    elif not url:
        # 빈 URL 저장으로 동작 중인 소스가 소리 없이 지워지는 사고 방지.
        url = (cur.get("url") or "").strip()
        # URL 없이 소스 종류만 바꾼 저장: 유효 URL(파일에 없으면 env 폴백)과 어긋나는
        # 소스로 400을 내거나 어긋난 쌍을 저장하는 대신, 소스·URL 쌍을 통째로
        # 기존 값으로 유지하고 나머지 설정만 반영한다.
        eff = url or (get_settings().update_url or "").strip()
        if eff and not _url_fits_source(eff, src):
            src = cur.get("source") if cur.get("source") in ("server", "github") else src
    if url and not _url_fits_source(url, src):
        if src == "github":
            raise HTTPException(
                status_code=400,
                detail="GitHub 소스는 'github:owner/repo', github.com 또는 raw.githubusercontent.com 주소여야 합니다.")
        raise HTTPException(status_code=400, detail="Update Server 소스는 http(s):// 주소여야 합니다.")
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
    # May hold a token → atomic + 0600.
    from ..storage import atomic_write_text
    atomic_write_text(p, json.dumps(cfg, ensure_ascii=False, indent=2), mode=0o600)
    return {"ok": True, "config": _masked(cfg)}


@router.post("/run")
async def update_run() -> dict:
    """Trigger the systemd update unit.

    Privilege-free first: drop a ``.update-now`` marker that the root systemd
    ``.path`` unit watches — this works even when sudo is unusable (``/usr/bin/
    sudo`` on a ``nosuid`` mount) and when the manager runs as a non-root user.
    Then best-effort start the unit directly for immediacy (root → no sudo;
    otherwise the sudoers-allowed ``sudo -n``).
    """
    triggered = False
    try:
        marker = _abs(".update-now")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(datetime.now().isoformat(), encoding="utf-8")
        triggered = True
    except OSError:
        pass

    unit = ["systemctl", "start", "--no-block", "nexus-manager-update.service"]
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    cmd = unit if is_root else (["sudo", "-n"] + unit)
    err = b""
    started = False
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, err = await asyncio.wait_for(proc.communicate(), timeout=15)
        started = proc.returncode == 0
    except Exception:  # noqa: BLE001 - sudo/systemctl missing or blocked (nosuid)
        started = False

    if started:
        return {"ok": True, "detail": "업데이트를 시작했습니다. 새 버전이 있으면 곧 자동 재시작됩니다."}
    if triggered:
        return {"ok": True, "detail": ("업데이트를 예약했습니다 — 감시(.path) 유닛 또는 타이머가 곧 "
                                       "적용합니다. sudo가 막힌(nosuid) 환경에서도 동작합니다.")}
    raise HTTPException(
        status_code=503,
        detail=("업데이트 트리거 실패 — 트리거 파일 기록도 sudo 실행도 불가합니다. "
                "root로 'systemctl start nexus-manager-update.service' 를 실행하거나 "
                "감시 폴더에 zip을 넣으세요. "
                f"{(err or b'').decode(errors='ignore')[:200]}"),
    )
