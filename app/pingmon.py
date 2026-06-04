"""Infrastructure ping monitoring.

Measures TCP-connect latency from the manager to each monitored Nexus server,
appends every sample to a CSV text log (kept ~1 year), and serves time-windowed,
down-sampled series for charting. Each charted point is coloured by how far it
deviates from the window baseline (>=+20% warn, >=+50% crit).
"""
from __future__ import annotations

import asyncio
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .config import Settings, get_settings

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_BUCKETS = 200            # max charted points per series
_RETENTION_DAYS = 366


def _ping_path(settings: Settings) -> Path:
    path = Path(settings.ping_file)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _host_port(base_url: str) -> Tuple[str, int]:
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname or "", port


async def _measure(host: str, port: int, timeout: float) -> Optional[float]:
    """TCP-connect latency in ms, or None when unreachable."""
    start = time.perf_counter()
    try:
        fut = asyncio.open_connection(host, port)
        _, writer = await asyncio.wait_for(fut, timeout=timeout)
        elapsed = (time.perf_counter() - start) * 1000
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return round(elapsed, 1)
    except Exception:
        return None


async def record_once(registry, settings: Settings) -> None:
    instances = registry.monitoring()
    if not instances:
        return
    results = await asyncio.gather(
        *(_measure(*_host_port(i.base_url), min(settings.request_timeout, 5.0))
          for i in instances)
    )
    ts = datetime.now(timezone.utc).strftime(_TS_FMT)
    lines = [
        f"{ts},{inst.id},{'' if ms is None else ms}\n"
        for inst, ms in zip(instances, results)
    ]
    path = _ping_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.writelines(lines)


def _prune(settings: Settings) -> None:
    path = _ping_path(settings)
    if not path.exists():
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)).strftime(_TS_FMT)
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if ln[:20] >= cutoff]
    if len(kept) != len(lines):
        path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


def _color(value: float, baseline: Optional[float], warn_ratio: float, crit_ratio: float) -> str:
    if not baseline or baseline <= 0:
        return "ok"
    ratio = value / baseline
    if ratio >= crit_ratio:
        return "crit"
    if ratio >= warn_ratio:
        return "warn"
    return "ok"


def query(
    days: int,
    names: Dict[str, str],
    warn_pct: float = 20.0,
    crit_pct: float = 50.0,
    settings: Optional[Settings] = None,
) -> dict:
    """Return down-sampled, colour-coded ping series for the last ``days``."""
    settings = settings or get_settings()
    warn_ratio = 1.0 + max(0.0, warn_pct) / 100.0
    crit_ratio = 1.0 + max(0.0, crit_pct) / 100.0
    path = _ping_path(settings)
    now = datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(days=days)
    cutoff = cutoff_dt.strftime(_TS_FMT)
    by_inst: Dict[str, List[Tuple[float, Optional[float]]]] = {}

    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            parts = ln.split(",")
            if len(parts) != 3:
                continue
            ts, iid, val = parts
            if ts < cutoff:
                continue
            try:
                t = datetime.strptime(ts, _TS_FMT).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue
            v = float(val) if val else None
            by_inst.setdefault(iid, []).append((t, v))

    t0 = cutoff_dt.timestamp()
    t1 = now.timestamp()
    span = max(t1 - t0, 1.0)
    series = []
    for iid in sorted(by_inst, key=lambda k: names.get(k, k).lower()):
        pts = by_inst[iid]
        values = [v for _, v in pts if v is not None]
        baseline = round(statistics.median(values), 1) if values else None

        # Bucket by time and average non-null values per bucket.
        buckets: Dict[int, List[float]] = {}
        for t, v in pts:
            if v is None:
                continue
            b = min(_BUCKETS - 1, int((t - t0) / span * _BUCKETS))
            buckets.setdefault(b, []).append(v)
        points = []
        for b in sorted(buckets):
            avg = round(sum(buckets[b]) / len(buckets[b]), 1)
            bt = int(t0 + (b + 0.5) / _BUCKETS * span)
            points.append({
                "t": bt, "v": avg,
                "color": _color(avg, baseline, warn_ratio, crit_ratio),
            })

        series.append({
            "id": iid,
            "name": names.get(iid, iid),
            "baseline": baseline,
            "points": points,
        })

    return {"days": days, "warn_pct": warn_pct, "crit_pct": crit_pct, "series": series}


async def run_loop() -> None:
    """Background ping loop, launched at app startup."""
    from .deps import registry

    count = 0
    while True:
        settings = get_settings()
        try:
            if registry.all():
                await record_once(registry, settings)
                count += 1
                if count % 60 == 0:
                    _prune(settings)
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(max(10.0, registry.ping_interval()))
