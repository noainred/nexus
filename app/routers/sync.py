"""Proxy cache-warming: pull a source repo's asset paths through a target
proxy so the target caches the same content (best-effort, resumable)."""
from __future__ import annotations

import asyncio
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
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
