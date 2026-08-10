"""Proxy cache-warming: pull a source repo's asset paths through a target
proxy so the target caches the same content (best-effort, resumable), plus
scheduled cache-warming jobs (daily at HH:MM)."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import Settings, get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import SyncJobs
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["sync"])

_CONCURRENCY = 6
_WARM_TIMEOUT = 180.0


async def _warm_one(client: httpx.AsyncClient, url: str) -> tuple:
    """Range-GET an asset so the proxy fetches+caches the full file upstream."""
    try:
        resp = await client.get(url, headers={"Range": "bytes=0-0"})
    except httpx.HTTPError as exc:
        return False, (str(exc).strip() or type(exc).__name__)
    if resp.status_code in (200, 206, 304):
        return True, ""
    return False, f"HTTP {resp.status_code}"


@router.post("/instances/{target_id}/cache-warm")
async def cache_warm(
    target_id: str,
    source_id: str = Query(..., description="Instance whose cached assets are the source list."),
    repository: str = Query(..., description="Repository name (same on both servers)."),
    token: str = Query("", description="Resume cursor (continuationToken)."),
    pages: int = Query(5, ge=1, le=50, description="Asset pages to process this call."),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Warm ``target``'s proxy cache for ``repository`` using ``source``'s asset
    list. Processes up to ``pages`` asset pages, returning a resume token."""
    if source_id == target_id:
        raise HTTPException(status_code=400, detail="원본과 대상이 같습니다.")
    source = registry.get(source_id)   # 404 if unknown
    target = registry.get(target_id)   # 404 if unknown

    sc = NexusClient(source, timeout=get_settings().request_timeout)
    base = target.base_url.rstrip("/")
    verify = True if target.verify_tls is None else target.verify_tls

    warmed = failed = processed = 0
    errors: List[str] = []
    tok = token or None
    done = False

    async with httpx.AsyncClient(
        auth=(target.username, target.password),
        timeout=_WARM_TIMEOUT,
        verify=verify,
        follow_redirects=True,
    ) as tcli:
        sem = asyncio.Semaphore(_CONCURRENCY)

        async def warm(path: str) -> None:
            nonlocal warmed, failed, processed
            url = f"{base}/repository/{repository}/{path.lstrip('/')}"
            async with sem:
                ok, reason = await _warm_one(tcli, url)
            processed += 1
            if ok:
                warmed += 1
            else:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"{path}: {reason}")

        for _ in range(pages):
            try:
                page = await sc.list_assets(repository, tok)
            except NexusError as exc:
                raise HTTPException(status_code=502, detail=f"원본 자산 조회 실패: {exc.message}")
            paths = [a.path for a in page.items if a.path]
            await asyncio.gather(*(warm(p) for p in paths))
            tok = page.continuation_token
            if not tok:
                done = True
                break

    return {
        "warmed": warmed,
        "failed": failed,
        "processed": processed,
        "next_token": tok or "",
        "done": done,
        "errors": errors,
    }


# -- Full (non-paged) warm + scheduled jobs --------------------------------

async def warm_full(source, target, repository: str, settings: Settings,
                    max_pages: int = 5000) -> dict:
    """Warm the target proxy's cache for the whole repository (all pages)."""
    sc = NexusClient(source, timeout=settings.request_timeout)
    base = target.base_url.rstrip("/")
    verify = True if target.verify_tls is None else target.verify_tls
    warmed = failed = processed = 0
    async with httpx.AsyncClient(
        auth=(target.username, target.password),
        timeout=_WARM_TIMEOUT, verify=verify, follow_redirects=True,
    ) as tcli:
        sem = asyncio.Semaphore(_CONCURRENCY)

        async def warm(path: str) -> None:
            nonlocal warmed, failed, processed
            url = f"{base}/repository/{repository}/{path.lstrip('/')}"
            async with sem:
                ok, _ = await _warm_one(tcli, url)
            processed += 1
            if ok:
                warmed += 1
            else:
                failed += 1

        tok = None
        pages = 0
        while pages < max_pages:
            page = await sc.list_assets(repository, tok)
            await asyncio.gather(*(warm(a.path) for a in page.items if a.path))
            tok = page.continuation_token
            pages += 1
            if not tok:
                break
    return {"warmed": warmed, "failed": failed, "processed": processed}


@router.get("/sync-jobs", response_model=SyncJobs)
async def get_sync_jobs(registry: InstanceRegistry = Depends(get_registry)) -> SyncJobs:
    return SyncJobs(jobs=registry.sync_jobs())


@router.put("/sync-jobs", response_model=SyncJobs)
async def set_sync_jobs(
    body: SyncJobs, registry: InstanceRegistry = Depends(get_registry)
) -> SyncJobs:
    jobs = []
    for j in body.jobs:
        d = j.dict()
        if not d.get("id"):
            d["id"] = uuid.uuid4().hex[:12]
        jobs.append(d)
    registry.set_sync_jobs(jobs)
    return SyncJobs(jobs=registry.sync_jobs())


@router.post("/sync-jobs/run")
async def run_sync_job_now(
    id: str = Query(..., description="Job id to run now."),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    job = next((j for j in registry.sync_jobs() if j.get("id") == id), None)
    if job is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    by_id = {i.id: i for i in registry.all()}
    src = by_id.get(job.get("source_id"))
    tgt = by_id.get(job.get("target_id"))
    if not src or not tgt or not job.get("repository"):
        raise HTTPException(status_code=400, detail="원본/대상/저장소가 올바르지 않습니다.")
    try:
        res = await warm_full(src, tgt, job["repository"], get_settings())
    except NexusError as exc:
        raise HTTPException(status_code=exc.status_code or 502,
                            detail=f"캐시 워밍 실패: {exc.message}")
    return {"id": id, **res}


async def run_loop() -> None:
    """Run scheduled cache-warming jobs at their configured HH:MM."""
    from ..deps import registry

    last: Dict[str, str] = {}
    while True:
        try:
            jobs = registry.sync_jobs()
            now = datetime.now()
            today = now.date().isoformat()
            by_id = {i.id: i for i in registry.all()}
            for job in jobs:
                if not job.get("enabled"):
                    continue
                try:
                    hh, mm = (int(x) for x in str(job.get("time", "")).split(":"))
                except ValueError:
                    continue
                jid = job.get("id") or ""
                if now.hour == hh and now.minute == mm and last.get(jid) != today:
                    last[jid] = today
                    src = by_id.get(job.get("source_id"))
                    tgt = by_id.get(job.get("target_id"))
                    if src and tgt and job.get("repository"):
                        # 백그라운드로 실행 — 한 작업의 긴 캐시 워밍이 스케줄러
                        # 루프를 막아, 같은 분에 예약된 다른 작업이 그 분을
                        # 놓쳐 하루 종일 건너뛰어지는 문제를 방지한다.
                        asyncio.create_task(
                            _run_job_safe(src, tgt, job["repository"], get_settings())
                        )
        except Exception:  # pragma: no cover - defensive
            pass
        await asyncio.sleep(30)


async def _run_job_safe(src, tgt, repository: str, settings: Settings) -> None:
    """Scheduled warm wrapper — swallow NexusError so a failing job doesn't
    surface as an unretrieved-task-exception warning, but keep the loop alive."""
    try:
        await warm_full(src, tgt, repository, settings)
    except NexusError:
        pass
    except Exception:  # pragma: no cover - defensive
        pass
