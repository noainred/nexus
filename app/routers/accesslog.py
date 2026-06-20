"""Server-side Nexus request.log analyzer for the download-tracking (IP) tab.

The manager reads request.log files it has local access to — but only those
listed in ``settings.request_log_paths`` (no arbitrary path reads) — and returns
per-IP download aggregates, so the operator doesn't have to upload the log.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry

router = APIRouter(prefix="/api/access-log", tags=["access-log"])

# Apache/Nexus combined log: host - user [date] "GET /path HTTP/1.1" code bytes ...
_LOG_RE = re.compile(r'^(\S+)\s+\S+\s+(\S+)\s+\[([^\]]+)\]\s+"(\S+)\s+(\S+)[^"]*"\s+(\d{3})\s+(\S+)')


def _cfg_path() -> Path:
    s = get_settings()
    p = Path(getattr(s, "access_log_config_file", "access-log-config.json"))
    return p if p.is_absolute() else Path(os.getcwd()) / p


def _load_cfg() -> dict:
    """{'template': ..., 'paths': ...} — UI-saved file, falling back to env."""
    cfg = {"template": "", "paths": (get_settings().request_log_paths or "")}
    p = _cfg_path()
    if p.is_file():
        try:
            d = json.loads(p.read_text("utf-8"))
            if isinstance(d, dict):
                cfg["template"] = str(d.get("template") or "")
                if d.get("paths") is not None:
                    cfg["paths"] = str(d.get("paths") or "")
        except Exception:  # noqa: BLE001
            pass
    return cfg


def _instance_log_path(instance) -> Optional[str]:
    """Resolve the per-server log path from the template ({id}/{name}/{host})."""
    tmpl = (_load_cfg().get("template") or "").strip()
    if not tmpl:
        return None
    host = urlparse(instance.base_url).hostname or ""
    try:
        return tmpl.format(id=instance.id, name=instance.name, host=host)
    except Exception:  # noqa: BLE001 - bad template placeholder
        return None


def _configured() -> List[Tuple[str, str]]:
    """[(label, path)] from saved/env paths; 'label=path' or bare path, globs."""
    raw = (_load_cfg().get("paths") or "").strip()
    out: List[Tuple[str, str]] = []
    for tok in re.split(r"[,\n]+", raw):
        tok = tok.strip()
        if not tok:
            continue
        if "=" in tok:
            label, path = (x.strip() for x in tok.split("=", 1))
        else:
            label, path = "", tok
        matches = sorted(glob.glob(path)) or [path]
        for p in matches:
            out.append((label or os.path.basename(p), p))
    return out


def _allowed(path: str) -> bool:
    return path in [p for _, p in _configured()]


def _open_text(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="ignore")
    return open(path, "rt", encoding="utf-8", errors="ignore")


def _parse(path: str, want_ip: Optional[str], repo_filter: str, limit: int) -> dict:
    by_ip: Dict[str, dict] = {}
    detail: List[dict] = []
    rf = (repo_filter or "").lower()
    idx = 0
    try:
        with _open_text(path) as fh:
            for line in fh:
                m = _LOG_RE.match(line)
                if not m:
                    continue
                ip, ts, method, url, code = m.group(1), m.group(3), m.group(4), m.group(5), m.group(6)
                if method != "GET" or not url.startswith("/repository/") or code not in ("200", "206"):
                    continue
                idx += 1
                rest = url[len("/repository/"):]
                slash = rest.find("/")
                repo = rest if slash < 0 else rest[:slash]
                rpath = "" if slash < 0 else rest[slash + 1:]
                e = by_ip.get(ip)
                if e is None:
                    e = {"count": 0, "last": ts, "last_idx": idx, "repos": {}}
                    by_ip[ip] = e
                e["count"] += 1
                e["last"] = ts
                e["last_idx"] = idx
                e["repos"][repo] = e["repos"].get(repo, 0) + 1
                if want_ip and ip == want_ip and (not rf or rf in repo.lower() or rf in rpath.lower()):
                    if len(detail) < limit:
                        b = m.group(7)
                        detail.append({"ts": ts, "repo": repo, "path": rpath, "status": int(code),
                                       "bytes": int(b) if b.isdigit() else 0})
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"로그 읽기 실패: {exc}")
    if want_ip:
        return {"ip": want_ip, "detail": detail, "total": (by_ip.get(want_ip) or {}).get("count", 0)}
    recent = sorted(by_ip.items(), key=lambda kv: kv[1]["last_idx"], reverse=True)[:limit]
    return {"ip_count": len(by_ip), "ips": [
        {"ip": ip, "count": e["count"], "last": e["last"],
         "top_repos": sorted(e["repos"].items(), key=lambda x: -x[1])[:5]}
        for ip, e in recent]}


@router.get("/sources")
async def sources() -> dict:
    return {"sources": [{"label": label, "path": p, "exists": os.path.isfile(p)}
                        for label, p in _configured()]}


@router.get("/config")
async def get_config() -> dict:
    return _load_cfg()


@router.put("/config")
async def set_config(body: dict) -> dict:
    cfg = {"template": str((body or {}).get("template") or "").strip(),
           "paths": str((body or {}).get("paths") or "").strip()}
    p = _cfg_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"설정 저장 실패: {exc}")
    return cfg


@router.get("/by-instance")
async def by_instance(
    instance_id: str = Query(...),
    ip: str = Query(""),
    repo: str = Query(""),
    limit: int = Query(500, ge=1, le=5000),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Read+analyze a registered Nexus server's request.log via the per-server
    path template (settings → 다운로드 로그 경로)."""
    inst = registry.get(instance_id)   # 404 if unknown
    path = _instance_log_path(inst)
    if not path:
        raise HTTPException(status_code=400, detail="서버별 로그 경로 템플릿이 설정되지 않았습니다(설정 → 모니터링·백업에서 지정).")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"로그 파일이 없습니다: {path}")
    out = _parse(path, ip.strip() or None, repo, limit)
    out["path"] = path
    return out


@router.get("/analyze")
async def analyze(
    path: str = Query(..., description="A path listed in request_log_paths."),
    ip: str = Query(""),
    repo: str = Query(""),
    limit: int = Query(500, ge=1, le=5000),
) -> dict:
    if not _allowed(path):
        raise HTTPException(status_code=400, detail="허용되지 않은 로그 경로입니다(설정 request_log_paths에 등록 필요).")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="로그 파일이 없습니다.")
    return _parse(path, ip.strip() or None, repo, limit)
