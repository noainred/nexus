"""Fleet-wide component search across all managed Nexus instances."""
from __future__ import annotations

import asyncio
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["search"])

_CONCURRENCY = 6


@router.get("/search")
async def search_all(
    q: str = Query("", description="Keyword (component/artifact)."),
    format: str = Query("", description="Optional format filter (maven2, npm, …)."),
    repository: str = Query("", description="Optional repository name filter."),
    scope: str = Query("monitoring", pattern="^(monitoring|all)$"),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Search every managed instance for components matching the query."""
    params: Dict[str, str] = {}
    if q.strip():
        params["q"] = q.strip()
    if format.strip():
        params["format"] = format.strip()
    if repository.strip():
        params["repository"] = repository.strip()
    if not params:
        raise HTTPException(status_code=400, detail="검색어(또는 포맷/저장소)를 입력하세요.")

    instances = registry.monitoring() if scope == "monitoring" else registry.all()
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def one(inst):
        async with sem:
            client = NexusClient(inst, timeout=get_settings().request_timeout)
            try:
                items = await client.search_components(params)
            except NexusError as exc:
                return inst, None, exc.message
            return inst, items, None

    results = await asyncio.gather(*(one(i) for i in instances))

    hits: List[dict] = []
    errors: Dict[str, str] = {}
    for inst, items, err in results:
        if err is not None:
            errors[inst.id] = err
            continue
        for it in items:
            hits.append({"instance_id": inst.id, "instance_name": inst.name, **it})

    hits.sort(key=lambda h: (
        (h.get("group") or ""), (h.get("name") or ""),
        (h.get("version") or ""), h["instance_name"],
    ))
    return {"q": q, "count": len(hits), "scanned": len(instances), "hits": hits, "errors": errors}
