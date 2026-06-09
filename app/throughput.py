"""Spine→Leaf network throughput monitoring.

Only port 8081 is open and there is no agent on the servers, so a direct
server-to-server copy cannot be triggered from the manager. Instead we use
the existing Nexus proxy topology: every Leaf has a proxy repository whose
remote is the Spine. Requesting an *uncached* asset on a Leaf makes the Leaf
pull it from the Spine over the real (often cross-continent) link — that pull
is the Spine→Leaf transfer we want to time.

For each Leaf we:
  1. find its proxy repo pointing at the Spine (host + repo match),
  2. DELETE the cached asset on the Leaf to force a cache miss,
  3. time a full GET (t_miss = Spine→Leaf + Leaf→manager),
  4. time a second GET (t_hit ≈ Leaf→manager, now cached),
  5. take t_miss − t_hit as the isolated Spine→Leaf time (clamped).

Stored/charted like ping history, but lower throughput (Mbps) is worse: a
point is coloured warn/crit when it drops >=warn%/>=crit% BELOW the median.
"""
from __future__ import annotations

import asyncio
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .config import Settings, get_settings
from .nexus_client import NexusClient, NexusError

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_BUCKETS = 200
_RETENTION_DAYS = 366
_DL_TIMEOUT = 300.0
_DEL_TIMEOUT = 30.0


def _path(settings: Settings) -> Path:
    p = Path(settings.throughput_file)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _host_key(url: str) -> Tuple[str, Optional[int]]:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return (parsed.hostname or "").lower(), parsed.port


def _repo_segment(url: str) -> str:
    """Extract the repository name from a remote URL like .../repository/<name>/."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    if "repository" in parts:
        i = parts.index("repository")
        if i + 1 < len(parts):
            return parts[i + 1]
    return ""


async def _find_proxy_repo(leaf, spine, spine_repo: str) -> Optional[str]:
    """Return the Leaf proxy repo whose remote points at the Spine (+repo)."""
    client = NexusClient(leaf, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError:
        return None
    skey = _host_key(spine.base_url)
    host_match: Optional[str] = None
    for r in repos:
        attrs = r.attributes if isinstance(r.attributes, dict) else {}
        proxy = attrs.get("proxy") if isinstance(attrs, dict) else None
        remote = proxy.get("remoteUrl") if isinstance(proxy, dict) else None
        if not remote or _host_key(remote) != skey:
            continue
        if spine_repo:
            # When a specific Spine repo is chosen, only an exact host+repo
            # match is valid — otherwise the asset path won't resolve and we'd
            # get a misleading 404 from an unrelated proxy.
            if _repo_segment(remote) == spine_repo:
                return r.name
            continue
        if host_match is None:
            host_match = r.name
    return host_match


async def leaf_spine_repos(leaf, spine) -> set:
    """The set of Spine repo names that ``leaf`` proxies (host match)."""
    client = NexusClient(leaf, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError:
        return set()
    skey = _host_key(spine.base_url)
    segs: set = set()
    for r in repos:
        attrs = r.attributes if isinstance(r.attributes, dict) else {}
        proxy = attrs.get("proxy") if isinstance(attrs, dict) else None
        remote = proxy.get("remoteUrl") if isinstance(proxy, dict) else None
        if remote and _host_key(remote) == skey:
            seg = _repo_segment(remote)
            if seg:
                segs.add(seg)
    return segs


async def _timed_get(inst, url: str, cap_bytes: int) -> Tuple[Optional[Tuple[int, float]], str]:
    """Timed full GET. Returns ((bytes, ms), "") or (None, reason)."""
    verify = True if inst.verify_tls is None else inst.verify_tls
    total = 0
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=_DL_TIMEOUT,
            verify=verify,
            auth=(inst.username, inst.password),
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    return None, f"HTTP {resp.status_code}"
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if cap_bytes and total >= cap_bytes:
                        break
    except httpx.HTTPError as exc:
        return None, f"연결 오류: {type(exc).__name__}"
    elapsed = (time.perf_counter() - start) * 1000
    if total <= 0 or elapsed <= 0:
        return None, "빈 응답"
    return (total, elapsed), ""


async def _delete_cached(inst, url: str) -> None:
    """Best-effort delete of a cached asset on a proxy (forces a re-fetch)."""
    verify = True if inst.verify_tls is None else inst.verify_tls
    try:
        async with httpx.AsyncClient(
            timeout=_DEL_TIMEOUT,
            verify=verify,
            auth=(inst.username, inst.password),
            follow_redirects=True,
        ) as client:
            await client.delete(url)
    except httpx.HTTPError:
        pass


async def measure(
    spine, leaf, spine_repo: str, asset_path: str, cap_bytes: int
) -> Tuple[Optional[Tuple[int, float]], str]:
    """Measure the isolated Spine→Leaf transfer time for ``asset_path``.

    Returns ((bytes, ms), detail) on success, or (None, reason) on failure.
    """
    repo = await _find_proxy_repo(leaf, spine, spine_repo)
    if not repo:
        if spine_repo:
            return None, f"'{spine_repo}'을(를) 프록시하는 저장소가 없음 (다단 구조이거나 미프록시)"
        return None, "Spine을 가리키는 프록시 저장소를 찾지 못함 (다단 프록시 구조일 수 있음)"
    url = leaf.base_url.rstrip("/") + f"/repository/{repo}/" + asset_path.lstrip("/")
    await _delete_cached(leaf, url)            # force cache miss
    miss, derr = await _timed_get(leaf, url, cap_bytes)
    if miss is None:
        return None, f"자산 다운로드 실패: {derr} (프록시 {repo}/{asset_path.lstrip('/')})"
    hit, _ = await _timed_get(leaf, url, cap_bytes)
    miss_bytes, miss_ms = miss
    hit_ms = hit[1] if hit else 0.0
    spine_ms = miss_ms - hit_ms
    floor = max(miss_ms * 0.1, 1.0)            # guard against noise/streaming
    if spine_ms < floor:
        spine_ms = floor
    detail = f"성공 · {repo} · miss {round(miss_ms)}ms / hit {round(hit_ms)}ms"
    return (miss_bytes, round(spine_ms, 1)), detail


def select_leaves(registry, cfg: dict) -> list:
    """Leaves to measure: monitored, non-Spine, restricted to targets if set."""
    spine_id = cfg.get("spine_id") or ""
    targets = set(cfg.get("targets") or [])
    leafs = [i for i in registry.monitoring() if i.id != spine_id]
    if targets:
        leafs = [i for i in leafs if i.id in targets]
    return leafs


async def record_once(registry, settings: Settings, cfg: dict) -> List[dict]:
    """Run one Spine→Leaf measurement round. Returns per-leaf diagnostics."""
    spine_id = cfg.get("spine_id") or ""
    asset_path = cfg.get("path") or ""
    spine_repo = cfg.get("spine_repo") or ""
    if not spine_id or not asset_path:
        return []
    by_id = {i.id: i for i in registry.all()}
    spine = by_id.get(spine_id)
    if spine is None:
        return []
    leafs = select_leaves(registry, cfg)
    if not leafs:
        return []
    cap_bytes = max(1, int(cfg.get("size_mb", 30))) * 1024 * 1024
    out = _path(settings)
    out.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime(_TS_FMT)
    diagnostics: List[dict] = []
    # Sequential so the Spine→Leaf pulls don't contend with each other.
    for leaf in leafs:
        res, detail = await measure(spine, leaf, spine_repo, asset_path, cap_bytes)
        if res is None:
            line = f"{ts},{leaf.id},,\n"
            ok = False
        else:
            line = f"{ts},{leaf.id},{res[0]},{res[1]}\n"
            ok = True
        with out.open("a", encoding="utf-8") as fh:
            fh.write(line)
        diagnostics.append({"id": leaf.id, "name": leaf.name, "ok": ok, "detail": detail})
    return diagnostics


async def _probe_get(inst, url: str) -> Tuple[bool, str]:
    """Tiny ranged GET just to confirm the asset is reachable (no full DL)."""
    verify = True if inst.verify_tls is None else inst.verify_tls
    try:
        async with httpx.AsyncClient(
            timeout=_DEL_TIMEOUT,
            verify=verify,
            auth=(inst.username, inst.password),
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, headers={"Range": "bytes=0-0"})
    except httpx.HTTPError as exc:
        return False, f"연결 오류: {type(exc).__name__}"
    if resp.status_code >= 400:
        return False, f"HTTP {resp.status_code}"
    return True, f"HTTP {resp.status_code}"


async def test_connectivity(registry, cfg: dict) -> List[dict]:
    """Pre-check Spine reachability and each Leaf's proxy path to the Spine.

    Returns a list of per-server diagnostics (Spine first, then Leaves).
    Nothing is measured or written — this only verifies connectivity.
    """
    spine_id = cfg.get("spine_id") or ""
    spine_repo = cfg.get("spine_repo") or ""
    asset_path = cfg.get("path") or ""
    by_id = {i.id: i for i in registry.all()}
    spine = by_id.get(spine_id)
    results: List[dict] = []
    if spine is None:
        return results

    # 1) Manager → Spine itself.
    client = NexusClient(spine, timeout=get_settings().request_timeout)
    try:
        info = await client.ping()
        results.append({
            "id": spine.id,
            "name": f"{spine.name} (Spine)",
            "ok": True,
            "detail": f"Spine 연결 OK · 응답 {info.get('response_ms')}ms",
        })
    except NexusError as exc:
        results.append({
            "id": spine.id,
            "name": f"{spine.name} (Spine)",
            "ok": False,
            "detail": f"Spine 연결 실패: {exc.message}",
        })
        return results  # no point probing leaves if the Spine is down

    # 2) Each Leaf → can it reach the Spine through a proxy repo?
    leafs = [i for i in registry.monitoring() if i.id != spine_id]
    for leaf in leafs:
        repo = await _find_proxy_repo(leaf, spine, spine_repo)
        if not repo:
            detail = (
                f"'{spine_repo}'을(를) 프록시하는 저장소가 없음"
                if spine_repo
                else "Spine을 가리키는 프록시 저장소를 찾지 못함"
            )
            results.append({
                "id": leaf.id,
                "name": leaf.name,
                "ok": False,
                "detail": detail,
            })
            continue
        if not asset_path:
            results.append({
                "id": leaf.id,
                "name": leaf.name,
                "ok": True,
                "detail": f"프록시 OK ({repo}) · 자산 경로 미지정",
            })
            continue
        url = leaf.base_url.rstrip("/") + f"/repository/{repo}/" + asset_path.lstrip("/")
        ok, detail = await _probe_get(leaf, url)
        results.append({
            "id": leaf.id,
            "name": leaf.name,
            "ok": ok,
            "detail": (f"프록시 {repo} · 자산 접근 OK ({detail})" if ok
                       else f"프록시 {repo} · 자산 접근 실패: {detail}"),
        })
    return results


async def record_one(registry, settings: Settings, cfg: dict, leaf_id: str) -> Optional[dict]:
    """Measure a single Leaf now, append to CSV, return its diagnostic."""
    spine_id = cfg.get("spine_id") or ""
    asset_path = cfg.get("path") or ""
    spine_repo = cfg.get("spine_repo") or ""
    if not spine_id or not asset_path:
        return None
    by_id = {i.id: i for i in registry.all()}
    spine = by_id.get(spine_id)
    leaf = by_id.get(leaf_id)
    if spine is None or leaf is None or leaf.id == spine_id:
        return None
    cap_bytes = max(1, int(cfg.get("size_mb", 30))) * 1024 * 1024
    out = _path(settings)
    out.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime(_TS_FMT)
    res, detail = await measure(spine, leaf, spine_repo, asset_path, cap_bytes)
    mbps: Optional[float] = None
    if res is None:
        line = f"{ts},{leaf.id},,\n"
        ok = False
    else:
        line = f"{ts},{leaf.id},{res[0]},{res[1]}\n"
        ok = True
        secs = res[1] / 1000.0
        if secs > 0:
            mbps = round(res[0] * 8 / secs / 1_000_000, 2)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return {"id": leaf.id, "name": leaf.name, "ok": ok, "detail": detail, "mbps": mbps}


def _prune(settings: Settings) -> None:
    out = _path(settings)
    if not out.exists():
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)).strftime(_TS_FMT)
    lines = out.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if ln[:20] >= cutoff]
    if len(kept) != len(lines):
        out.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


def _color(value: float, baseline: Optional[float], warn_ratio: float, crit_ratio: float) -> str:
    """Lower throughput is worse: colour when value drops below the baseline."""
    if not baseline or baseline <= 0:
        return "ok"
    if value <= baseline * crit_ratio:
        return "crit"
    if value <= baseline * warn_ratio:
        return "warn"
    return "ok"


def query(
    days: int,
    names: Dict[str, str],
    warn_pct: float = 20.0,
    crit_pct: float = 50.0,
    settings: Optional[Settings] = None,
) -> dict:
    """Down-sampled throughput series (Mbps) with deviation colouring."""
    settings = settings or get_settings()
    warn_ratio = 1.0 - max(0.0, warn_pct) / 100.0
    crit_ratio = 1.0 - max(0.0, crit_pct) / 100.0
    out = _path(settings)
    now = datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(days=days)
    cutoff = cutoff_dt.strftime(_TS_FMT)
    by_inst: Dict[str, List[Tuple[float, Optional[float]]]] = {}

    if out.exists():
        for ln in out.read_text(encoding="utf-8").splitlines():
            parts = ln.split(",")
            if len(parts) != 4:
                continue
            ts, iid, nbytes, ms = parts
            if ts < cutoff:
                continue
            try:
                t = datetime.strptime(ts, _TS_FMT).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue
            mbps = None
            if nbytes and ms:
                try:
                    secs = float(ms) / 1000.0
                    mbps = round(float(nbytes) * 8 / secs / 1_000_000, 2) if secs > 0 else None
                except ValueError:
                    mbps = None
            by_inst.setdefault(iid, []).append((t, mbps))

    t0 = cutoff_dt.timestamp()
    t1 = now.timestamp()
    span = max(t1 - t0, 1.0)
    series = []
    for iid in sorted(by_inst, key=lambda k: names.get(k, k).lower()):
        pts = by_inst[iid]
        values = [v for _, v in pts if v is not None]
        baseline = round(statistics.median(values), 2) if values else None
        buckets: Dict[int, List[float]] = {}
        for t, v in pts:
            if v is None:
                continue
            b = min(_BUCKETS - 1, int((t - t0) / span * _BUCKETS))
            buckets.setdefault(b, []).append(v)
        points = []
        for b in sorted(buckets):
            avg = round(sum(buckets[b]) / len(buckets[b]), 2)
            bt = int(t0 + (b + 0.5) / _BUCKETS * span)
            points.append({"t": bt, "v": avg, "color": _color(avg, baseline, warn_ratio, crit_ratio)})
        series.append({"id": iid, "name": names.get(iid, iid), "baseline": baseline, "points": points})

    return {"days": days, "warn_pct": warn_pct, "crit_pct": crit_pct, "series": series}


async def run_loop() -> None:
    """Daily scheduled Spine→Leaf test at the configured HH:MM (local time)."""
    from .deps import registry

    last_date: Optional[str] = None
    while True:
        try:
            cfg = registry.throughput_config()
            if cfg.get("spine_id") and cfg.get("path") and cfg.get("time"):
                now = datetime.now()
                try:
                    hh, mm = (int(x) for x in cfg["time"].split(":"))
                except ValueError:
                    hh, mm = -1, -1
                today = now.date().isoformat()
                if now.hour == hh and now.minute == mm and last_date != today:
                    last_date = today
                    await record_once(registry, get_settings(), cfg)
                    _prune(get_settings())
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(30)
