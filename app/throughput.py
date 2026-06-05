"""Network throughput monitoring.

Only port 8081 is open, so throughput is measured by downloading a common
Nexus asset over HTTP and timing it. A Range request fetches just the first
N MB so every sample is the same size regardless of the file. Servers are
measured sequentially so concurrent downloads don't skew each other.

Stored/charted like ping history, but lower throughput is worse: a point is
coloured warn/crit when it drops >=warn%/>=crit% BELOW the window median.
"""
from __future__ import annotations

import asyncio
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from .config import Settings, get_settings

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_BUCKETS = 200
_RETENTION_DAYS = 366
_DL_TIMEOUT = 120.0


def _path(settings: Settings) -> Path:
    p = Path(settings.throughput_file)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


async def measure(instance, url_path: str, size_bytes: int) -> Optional[Tuple[int, float]]:
    """Download up to ``size_bytes`` of an asset; return (bytes, elapsed_ms)."""
    url = instance.base_url.rstrip("/") + "/" + url_path.lstrip("/")
    verify = True if instance.verify_tls is None else instance.verify_tls
    headers = {"Range": f"bytes=0-{size_bytes - 1}"}
    total = 0
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=_DL_TIMEOUT,
            verify=verify,
            auth=(instance.username, instance.password),
        ) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                if resp.status_code >= 400:
                    return None
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total >= size_bytes:
                        break
    except httpx.HTTPError:
        return None
    elapsed = (time.perf_counter() - start) * 1000
    if total <= 0 or elapsed <= 0:
        return None
    return total, round(elapsed, 1)


async def record_once(registry, settings: Settings, path: str, size_bytes: int) -> None:
    instances = registry.monitoring()
    if not instances or not path:
        return
    out = _path(settings)
    out.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime(_TS_FMT)
    # Sequential so downloads don't share/contend bandwidth.
    for inst in instances:
        res = await measure(inst, path, size_bytes)
        if res is None:
            line = f"{ts},{inst.id},,\n"
        else:
            line = f"{ts},{inst.id},{res[0]},{res[1]}\n"
        with out.open("a", encoding="utf-8") as fh:
            fh.write(line)


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
    """Daily scheduled throughput test at the configured HH:MM (local time)."""
    from .deps import registry

    last_date: Optional[str] = None
    while True:
        try:
            cfg = registry.throughput_config()
            if cfg["path"] and cfg["time"]:
                now = datetime.now()
                try:
                    hh, mm = (int(x) for x in cfg["time"].split(":"))
                except ValueError:
                    hh, mm = -1, -1
                today = now.date().isoformat()
                if now.hour == hh and now.minute == mm and last_date != today:
                    last_date = today
                    size = max(1, int(cfg["size_mb"])) * 1024 * 1024
                    await record_once(registry, get_settings(), cfg["path"], size)
                    _prune(get_settings())
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(30)
