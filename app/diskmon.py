"""Blob-store disk usage sampling + saturation forecast.

Running out of blob-store disk is the most common Nexus operational failure
(once full, even cleanup can fail), so we sample every monitored server's
blob stores periodically into a small CSV and fit a linear growth rate to
predict when each store will reach 90% — surfacing "DMZ2: ~18일 후 90%"
*before* it happens.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Settings, get_settings
from .nexus_client import NexusClient, NexusError

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_SAMPLE_INTERVAL = 6 * 3600       # seconds between samples
_WINDOW_DAYS = 14                 # growth fitted over this window
_RETENTION_DAYS = 200


def _path(settings: Settings) -> Path:
    p = Path(getattr(settings, "disk_file", "disk-history.csv"))
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


async def sample_once(registry, settings: Settings) -> int:
    """Record one usage sample for every monitored server's blob stores."""
    ts = datetime.now(timezone.utc).strftime(_TS_FMT)
    lines: List[str] = []

    async def one(inst):
        client = NexusClient(inst, timeout=settings.request_timeout)
        try:
            blobs = await client.list_blobstores()
        except NexusError:
            return
        for b in blobs:
            used, avail = b.total_size_bytes, b.available_space_bytes
            if used is None or avail is None:
                continue
            lines.append(f"{ts},{inst.id},{b.name},{used},{used + avail}\n")

    await asyncio.gather(*(one(i) for i in registry.monitoring()))
    if lines:
        p = _path(settings)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.writelines(lines)
    return len(lines)


_read_cache: dict = {}  # {"key": (path, mtime_ns, size), "data": parsed}


def _read(settings: Settings) -> Dict[Tuple[str, str], List[Tuple[datetime, int, int]]]:
    p = _path(settings)
    out: Dict[Tuple[str, str], List[Tuple[datetime, int, int]]] = {}
    if not p.is_file():
        return out
    # Cache the parsed history keyed by (path, mtime, size): /disk-forecast and
    # /disk-history both re-parse the whole CSV otherwise, and a new sample only
    # lands every 6h — so between samples the parse is reused. Consumers only
    # read the returned structure, so sharing it is safe.
    try:
        st = p.stat()
        key = (str(p), st.st_mtime_ns, st.st_size)
    except OSError:
        key = None
    if key is not None and _read_cache.get("key") == key:
        return _read_cache["data"]
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(",")
        if len(parts) != 5:
            continue
        try:
            dt = datetime.strptime(parts[0], _TS_FMT).replace(tzinfo=timezone.utc)
            used, total = int(parts[3]), int(parts[4])
        except ValueError:
            continue
        out.setdefault((parts[1], parts[2]), []).append((dt, used, total))
    for v in out.values():
        v.sort(key=lambda x: x[0])
    if key is not None:
        _read_cache["key"], _read_cache["data"] = key, out
    return out


def forecast(registry, settings: Settings) -> List[dict]:
    """Per blob store: current usage + linear growth + days until 90%."""
    names = {i.id: i.name for i in registry.all()}
    data = _read(settings)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=_WINDOW_DAYS)
    rows: List[dict] = []
    for (iid, store), samples in data.items():
        if iid not in names or not samples:
            continue
        dt_l, used_l, total_l = samples[-1]
        pct = (used_l / total_l * 100) if total_l > 0 else 0.0
        window = [s for s in samples if s[0] >= cutoff] or samples
        growth = None
        if len(window) >= 2:
            dt_f, used_f, _ = window[0]
            span_days = (dt_l - dt_f).total_seconds() / 86400
            if span_days >= 0.2:
                growth = (used_l - used_f) / span_days
        days_to_90 = None
        if growth is not None and growth > 0 and total_l > 0:
            remain = 0.9 * total_l - used_l
            days_to_90 = max(0.0, remain / growth)
        if pct >= 90 or (days_to_90 is not None and days_to_90 <= 7):
            state = "crit"
        elif pct >= 80 or (days_to_90 is not None and days_to_90 <= 21):
            state = "warn"
        else:
            state = "ok"
        rows.append({
            "instance_id": iid,
            "instance_name": names[iid],
            "store": store,
            "used_bytes": used_l,
            "total_bytes": total_l,
            "pct": round(pct, 1),
            "growth_per_day": round(growth) if growth is not None else None,
            "days_to_90": round(days_to_90, 1) if days_to_90 is not None else None,
            "state": state,
            "sampled_at": dt_l.strftime(_TS_FMT),
            "samples": len(samples),
        })
    order = {"crit": 0, "warn": 1, "ok": 2}
    rows.sort(key=lambda r: (order.get(r["state"], 9),
                             r["days_to_90"] if r["days_to_90"] is not None else 1e9,
                             -r["pct"]))
    return rows


def history(registry, settings: Settings, days: int = 60) -> List[dict]:
    """Per blob store: usage% time series for the trend chart."""
    names = {i.id: i.name for i in registry.all()}
    data = _read(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: List[dict] = []
    for (iid, store), samples in data.items():
        if iid not in names:
            continue
        pts = [
            {
                "t": int(dt.timestamp()),
                "used": used,
                "total": total,
                "pct": round(used / total * 100, 1) if total > 0 else 0.0,
            }
            for (dt, used, total) in samples if dt >= cutoff
        ]
        if not pts:
            continue
        out.append({
            "instance_id": iid,
            "instance_name": names[iid],
            "store": store,
            "points": pts,
        })
    out.sort(key=lambda s: (s["instance_name"], s["store"]))
    return out


def purge(instance_id: str, settings: Optional[Settings] = None) -> int:
    """Drop all disk-history rows for one instance (call when it's deleted).
    Returns the number of removed samples. Without this, a deleted node's rows
    accumulate in the CSV forever (they are filtered from views but never freed).
    """
    settings = settings or get_settings()
    p = _path(settings)
    if not p.is_file():
        return 0
    lines = p.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if ln.split(",", 2)[1:2] != [instance_id]]
    removed = len(lines) - len(kept)
    if removed:
        from .storage import atomic_write_text
        atomic_write_text(p, "\n".join(kept) + ("\n" if kept else ""))
    return removed


def _prune(settings: Settings) -> None:
    p = _path(settings)
    if not p.is_file():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    kept = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            dt = datetime.strptime(line.split(",", 1)[0], _TS_FMT).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt >= cutoff:
            kept.append(line + "\n")
    from .storage import atomic_write_text
    atomic_write_text(p, "".join(kept))


async def run_loop() -> None:
    """Sample on startup, then every ``_SAMPLE_INTERVAL`` seconds."""
    from .deps import registry

    await asyncio.sleep(15)  # let the app settle before the first sample
    while True:
        try:
            await sample_once(registry, get_settings())
            _prune(get_settings())
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(_SAMPLE_INTERVAL)
