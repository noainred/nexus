"""Infrastructure ping + Spine→Leaf throughput history endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import pingmon, throughput
from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import (
    PingHistory,
    ThroughputAsset,
    ThroughputAssets,
    ThroughputConfig,
    ThroughputDiag,
    ThroughputHistory,
    ThroughputLeaf,
    ThroughputLeaves,
    ThroughputTestResult,
)
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["infra"])

# How hard we scan each Spine repo when hunting for candidate assets.
_MAX_PAGES_PER_REPO = 8
_MAX_CANDIDATES = 40


@router.get("/ping-history", response_model=PingHistory)
async def ping_history(
    days: int = Query(1, ge=1, le=366),
    registry: InstanceRegistry = Depends(get_registry),
) -> PingHistory:
    names = {i.id: i.name for i in registry.all()}
    groups = {i.id: i.group for i in registry.all()}
    cfg = registry.ping_config()
    res = pingmon.query(days, names, cfg["warn_pct"], cfg["crit_pct"])
    for s in res["series"]:
        s["group"] = groups.get(s["id"], "")
    return PingHistory(**res)


def _attach_groups(res: dict, registry: InstanceRegistry) -> dict:
    groups = {i.id: i.group for i in registry.all()}
    for s in res["series"]:
        s["group"] = groups.get(s["id"], "")
    return res


@router.get("/throughput-history", response_model=ThroughputHistory)
async def throughput_history(
    days: int = Query(1, ge=1, le=366),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputHistory:
    names = {i.id: i.name for i in registry.all()}
    cfg = registry.throughput_config()
    res = throughput.query(days, names, cfg["warn_pct"], cfg["crit_pct"])
    return ThroughputHistory(**_attach_groups(res, registry))


@router.get("/throughput-config", response_model=ThroughputConfig)
async def get_throughput_config(
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputConfig:
    return ThroughputConfig(**registry.throughput_config())


@router.put("/throughput-config", response_model=ThroughputConfig)
async def set_throughput_config(
    cfg: ThroughputConfig,
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputConfig:
    registry.set_throughput_config(
        cfg.spine_id,
        cfg.spine_repo,
        cfg.path,
        cfg.time,
        cfg.size_mb,
        cfg.warn_pct,
        cfg.crit_pct,
    )
    return ThroughputConfig(**registry.throughput_config())


@router.post("/throughput-run", response_model=ThroughputHistory)
async def run_throughput(
    days: int = Query(1, ge=1, le=366),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputHistory:
    """Run one Spine→Leaf measurement now, then return refreshed history."""
    cfg = registry.throughput_config()
    diagnostics: list = []
    if cfg.get("spine_id") and cfg.get("path"):
        diagnostics = await throughput.record_once(registry, get_settings(), cfg)
    names = {i.id: i.name for i in registry.all()}
    res = throughput.query(days, names, cfg["warn_pct"], cfg["crit_pct"])
    res = _attach_groups(res, registry)
    res["diagnostics"] = diagnostics
    return ThroughputHistory(**res)


@router.get("/throughput-leaves", response_model=ThroughputLeaves)
async def throughput_leaves(
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputLeaves:
    """List the Leaf servers a '지금 측정' run will measure, in order."""
    cfg = registry.throughput_config()
    spine_id = cfg.get("spine_id") or ""
    by_id = {i.id: i for i in registry.all()}
    spine = by_id.get(spine_id)
    leaves = [
        ThroughputLeaf(id=i.id, name=i.name, group=i.group)
        for i in registry.monitoring()
        if i.id != spine_id
    ]
    return ThroughputLeaves(
        spine_id=spine_id,
        spine_name=(spine.name if spine else ""),
        leaves=leaves,
    )


@router.post("/throughput-run-one", response_model=ThroughputDiag)
async def run_throughput_one(
    leaf_id: str = Query(..., description="Leaf instance id to measure now."),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputDiag:
    """Measure a single Leaf now (used by the live progress popup)."""
    cfg = registry.throughput_config()
    if not cfg.get("spine_id") or not cfg.get("path"):
        raise HTTPException(status_code=400, detail="Spine·자산이 설정되지 않았습니다.")
    diag = await throughput.record_one(registry, get_settings(), cfg, leaf_id)
    if diag is None:
        raise HTTPException(status_code=404, detail="측정 대상 Leaf가 아닙니다.")
    return ThroughputDiag(**diag)


@router.post("/throughput-test", response_model=ThroughputTestResult)
async def test_throughput(
    cfg: ThroughputConfig,
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputTestResult:
    """Pre-check connectivity to the Spine without recording anything.

    Uses the values posted from the form (not the saved config) so the
    operator can verify before saving.
    """
    spine = registry.get(cfg.spine_id)  # 404 if unknown / empty
    results = await throughput.test_connectivity(
        registry,
        {"spine_id": spine.id, "spine_repo": cfg.spine_repo, "path": cfg.path},
    )
    return ThroughputTestResult(spine_id=spine.id, results=results)


@router.get("/throughput-assets", response_model=ThroughputAssets)
async def throughput_assets(
    spine_id: str = Query(..., description="Instance id to scan for candidates."),
    min_mb: float = Query(30.0, ge=0),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputAssets:
    """Find assets on the Spine that are at least ``min_mb`` in size.

    These become a convenient pick-list for the speed test so the operator
    doesn't have to type an asset path by hand.
    """
    spine = registry.get(spine_id)  # 404 if unknown
    client = NexusClient(spine, timeout=get_settings().request_timeout)
    lo = int(min_mb * 1024 * 1024)

    try:
        repos = await client.list_repositories()
    except NexusError:
        repos = []
    # Hosted repos hold the real bytes; skip group repos (no own assets).
    candidates: list[ThroughputAsset] = []
    scanned = 0
    truncated = False
    for repo in repos:
        if (repo.type or "").lower() == "group":
            continue
        scanned += 1
        token = None
        pages = 0
        try:
            while pages < _MAX_PAGES_PER_REPO:
                page = await client.list_assets(repo.name, token)
                for a in page.items:
                    size = a.file_size or 0
                    if size >= lo and a.path:
                        candidates.append(
                            ThroughputAsset(
                                repository=repo.name,
                                path=a.path,
                                size_bytes=size,
                                format=a.format,
                            )
                        )
                        if len(candidates) >= _MAX_CANDIDATES:
                            truncated = True
                            break
                if len(candidates) >= _MAX_CANDIDATES:
                    break
                token = page.continuation_token
                pages += 1
                if not token:
                    break
        except NexusError:
            continue
        if len(candidates) >= _MAX_CANDIDATES:
            break

    # Smallest-first so the candidates closest to the requested size lead.
    candidates.sort(key=lambda c: c.size_bytes)
    return ThroughputAssets(
        spine_id=spine_id,
        min_mb=min_mb,
        assets=candidates,
        scanned_repositories=scanned,
        truncated=truncated,
    )
