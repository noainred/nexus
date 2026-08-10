"""Infrastructure ping monitoring.

Measures TCP-connect latency from the manager to each monitored Nexus server,
appends every sample to a CSV text log (kept ~1 year), and serves time-windowed,
down-sampled series for charting. Each charted point is coloured by how far it
deviates from the window baseline (>=+20% warn, >=+50% crit).
"""

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
        from .storage import atomic_write_text
        atomic_write_text(path, "\n".join(kept) + ("\n" if kept else ""))


def purge(instance_id: str, settings: Optional[Settings] = None) -> int:
    """Drop all CSV rows for one instance (call when it's deleted). Returns the
    number of removed samples."""
    settings = settings or get_settings()
    path = _ping_path(settings)
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if ln.split(",", 2)[1:2] != [instance_id]]
    removed = len(lines) - len(kept)
    if removed:
        from .storage import atomic_write_text
        atomic_write_text(path, "\n".join(kept) + ("\n" if kept else ""))
    return removed


def _epoch(ts: str) -> float:
    """Fast parse of the fixed ``YYYY-MM-DDTHH:MM:SSZ`` timestamp to a UTC epoch.

    Equivalent to ``strptime(ts, _TS_FMT)`` but avoids the format-string parsing
    overhead, which dominates when a 7일/30일 window has thousands of samples.
    """
    return datetime(
        int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
        int(ts[11:13]), int(ts[14:16]), int(ts[17:19]),
        tzinfo=timezone.utc,
    ).timestamp()


def _color(value: float, baseline: Optional[float], warn_ratio: float, crit_ratio: float) -> str:
    if not baseline or baseline <= 0:
        return "ok"
    ratio = value / baseline
    if ratio >= crit_ratio:
        return "crit"
    if ratio >= warn_ratio:
        return "warn"
    return "ok"


def _lines_since(path: Path, cutoff: str, chunk: int = 1 << 20) -> List[str]:
    """Return CSV lines whose timestamp >= ``cutoff``, reading only the tail.

    The ping log is appended chronologically, so scanning the file backwards and
    stopping once a line is older than the cutoff avoids reading the whole
    (year-long, possibly huge) file for a 1일/7일 view. The timestamp is the
    first field (fixed-width ISO), so a plain string compare on ``line[:20]``
    works. Returns lines in chronological order.
    """
    out: List[str] = []
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            pos = fh.tell()
            carry = b""
            while pos > 0:
                read = min(chunk, pos)
                pos -= read
                fh.seek(pos)
                data = fh.read(read) + carry
                nl = data.find(b"\n")
                if pos > 0 and nl != -1:
                    carry = data[:nl]          # partial first line → earlier chunk
                    block = data[nl + 1:]
                else:
                    carry = b""
                    block = data
                stop = False
                for raw in reversed(block.split(b"\n")):
                    if not raw:
                        continue
                    line = raw.decode("utf-8", "ignore")
                    if line[:20] < cutoff:
                        stop = True
                        break
                    out.append(line)
                if stop:
                    break
    except OSError:
        return []
    out.reverse()
    return out


def query(
    days: int,
    names: Dict[str, str],
    warn_pct: float = 20.0,
    crit_pct: float = 50.0,
    settings: Optional[Settings] = None,
    known_ids: Optional[set] = None,
) -> dict:
    """Return down-sampled, colour-coded ping series for the last ``days``.

    When ``known_ids`` is given, series for instance ids *not* in it (e.g. nodes
    that were deleted but still have rows in the CSV) are dropped, so stale
    "garbage" nodes don't keep showing up on the chart.
    """
    settings = settings or get_settings()
    warn_ratio = 1.0 + max(0.0, warn_pct) / 100.0
    crit_ratio = 1.0 + max(0.0, crit_pct) / 100.0
    path = _ping_path(settings)
    now = datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(days=days)
    cutoff = cutoff_dt.strftime(_TS_FMT)
    by_inst: Dict[str, List[Tuple[float, Optional[float]]]] = {}

    if path.exists():
        for ln in _lines_since(path, cutoff):
            parts = ln.split(",")
            if len(parts) != 3:
                continue
            ts, iid, val = parts
            if ts < cutoff:
                continue
            try:
                t = _epoch(ts)
            except ValueError:
                continue
            v = float(val) if val else None
            by_inst.setdefault(iid, []).append((t, v))

    t0 = cutoff_dt.timestamp()
    t1 = now.timestamp()
    span = max(t1 - t0, 1.0)
    series = []
    for iid in sorted(by_inst, key=lambda k: names.get(k, k).lower()):
        if known_ids is not None and iid not in known_ids:
            continue  # deleted/unknown node still lingering in the CSV — skip
        pts = by_inst[iid]
        values = [v for _, v in pts if v is not None]
        baseline = round(statistics.median(values), 1) if values else None
        # 평균·최대는 다운샘플 이전의 원시값 기준으로 정확히 계산한다.
        mean = round(sum(values) / len(values), 1) if values else None
        peak = round(max(values), 1) if values else None

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
            "mean": mean,
            "peak": peak,
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
                    # 연 단위 CSV 전체 재작성은 이벤트 루프를 막으므로 스레드로 offload.
                    from .storage import run_in_thread
                    await run_in_thread(_prune, settings)
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(max(10.0, registry.ping_interval()))
