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
    ThroughputAutoConfig,
    ThroughputConfig,
    ThroughputDiag,
    ThroughputHistory,
    ThroughputLeaf,
    ThroughputLeaves,
    ThroughputProvision,
    ThroughputTargets,
    ThroughputTestResult,
)
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["infra"])

# Asset-page budget per "후보 파일 찾기" call, so a huge DB stays responsive.
# The caller resumes from the returned cursor with '더 찾기'.
_PAGES_PER_CALL = 6


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
        for i in throughput.select_leaves(registry, cfg)
    ]
    return ThroughputLeaves(
        spine_id=spine_id,
        spine_name=(spine.name if spine else ""),
        leaves=leaves,
    )


@router.get("/throughput-targets", response_model=ThroughputTargets)
async def get_throughput_targets(
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputTargets:
    return ThroughputTargets(targets=registry.throughput_config().get("targets", []))


@router.put("/throughput-targets", response_model=ThroughputTargets)
async def set_throughput_targets(
    body: ThroughputTargets,
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputTargets:
    registry.set_throughput_targets(body.targets)
    return ThroughputTargets(targets=registry.throughput_config().get("targets", []))


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


async def _first_asset_over(client, repo: str, lo: int, max_pages: int = 6):
    """First asset in ``repo`` whose size >= ``lo`` (scans a few pages)."""
    tok = None
    for _ in range(max_pages):
        try:
            page = await client.list_assets(repo, tok)
        except NexusError:
            return None
        for a in page.items:
            if (a.file_size or 0) >= lo and a.path:
                return a
        tok = page.continuation_token
        if not tok:
            break
    return None


@router.post("/throughput-provision", response_model=ThroughputProvision)
async def provision_throughput(
    size_mb: int = Query(30, ge=1, le=200),
    repo: str = Query("speedtest"),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputProvision:
    """Create a dedicated raw speed-test repo + dummy file when no suitable
    asset exists: hosted on the Spine, proxied on each Leaf."""
    cfg = registry.throughput_config()
    if not cfg.get("spine_id"):
        raise HTTPException(status_code=400, detail="먼저 Spine 서버를 지정하세요.")
    res = await throughput.provision(registry, get_settings(), size_mb, repo)
    return ThroughputProvision(**res)


@router.get("/throughput-autoconfig", response_model=ThroughputAutoConfig)
async def throughput_autoconfig(
    spine_id: str = Query(..., description="Spine instance id."),
    min_mb: float = Query(30.0, ge=0),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputAutoConfig:
    """Recommend a Spine asset that the most Leaves can measure.

    Looks at which Spine repository each Leaf proxies, picks the repo proxied
    by the most Leaves, and finds an asset >= min_mb in it. The frontend asks
    the user to confirm before applying it.
    """
    from collections import Counter

    spine = registry.get(spine_id)  # 404 if unknown
    leafs = [i for i in registry.monitoring() if i.id != spine_id]
    if not leafs:
        return ThroughputAutoConfig(found=False, reason="측정할 Leaf 서버가 없습니다.")

    # Which Spine repos does each Leaf proxy?
    cover: Counter = Counter()
    for leaf in leafs:
        for seg in await throughput.leaf_spine_repos(leaf, spine):
            cover[seg] += 1
    if not cover:
        return ThroughputAutoConfig(
            found=False, total=len(leafs),
            reason="Spine을 가리키는 프록시 저장소를 가진 Leaf가 없습니다 (다단 구조일 수 있음).",
        )

    client = NexusClient(spine, timeout=get_settings().request_timeout)
    try:
        spine_repo_names = {r.name for r in await client.list_repositories()}
    except NexusError:
        spine_repo_names = set()
    lo = int(min_mb * 1024 * 1024)

    # Try repos most-proxied first; require the repo to exist on the Spine.
    ordered = [r for r, _ in cover.most_common() if not spine_repo_names or r in spine_repo_names]
    for repo in ordered:
        asset = await _first_asset_over(client, repo, lo)
        if asset is not None:
            return ThroughputAutoConfig(
                found=True,
                spine_repo=repo,
                path=asset.path,
                size_bytes=asset.file_size or 0,
                format=asset.format,
                covered=cover[repo],
                total=len(leafs),
            )
    return ThroughputAutoConfig(
        found=False, total=len(leafs),
        reason=f"공통 저장소에서 {min_mb:.0f}MB 이상 측정용 자산을 찾지 못했습니다.",
    )


@router.get("/throughput-assets", response_model=ThroughputAssets)
async def throughput_assets(
    spine_id: str = Query(..., description="Instance id to scan for candidates."),
    min_mb: float = Query(30.0, ge=0),
    limit: int = Query(5, ge=1, le=50, description="Stop once this many are found."),
    repo_index: int = Query(0, ge=0, description="Resume cursor: repo position."),
    token: str = Query("", description="Resume cursor: asset page token."),
    registry: InstanceRegistry = Depends(get_registry),
) -> ThroughputAssets:
    """Find up to ``limit`` Spine assets ≥ ``min_mb``, resumably.

    Scans at most ``_PAGES_PER_CALL`` asset pages per call so a huge DB stays
    responsive; the caller passes ``next_repo_index``/``next_token`` back in to
    continue with '더 찾기'. ``done`` is true once every repo is exhausted.
    """
    spine = registry.get(spine_id)  # 404 if unknown
    client = NexusClient(spine, timeout=get_settings().request_timeout)
    lo = int(min_mb * 1024 * 1024)

    try:
        repos = await client.list_repositories()
    except NexusError:
        repos = []
    # Hosted repos hold the real bytes; skip group repos (no own assets).
    repos = [r for r in repos if (r.type or "").lower() != "group"]

    candidates: list[ThroughputAsset] = []
    pages = 0
    i = repo_index
    tok = token or None
    nxt_index, nxt_token = i, None
    while i < len(repos):
        repo = repos[i]
        try:
            page = await client.list_assets(repo.name, tok)
        except NexusError:
            i += 1
            tok = None
            nxt_index, nxt_token = i, None
            continue
        pages += 1
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
        if page.continuation_token:
            tok = page.continuation_token
            nxt_index, nxt_token = i, page.continuation_token
        else:
            i += 1
            tok = None
            nxt_index, nxt_token = i, None
        if len(candidates) >= limit or pages >= _PAGES_PER_CALL:
            break

    done = i >= len(repos)
    # Smallest-first so the candidates closest to the requested size lead.
    candidates.sort(key=lambda c: c.size_bytes)
    return ThroughputAssets(
        spine_id=spine_id,
        min_mb=min_mb,
        assets=candidates,
        next_repo_index=nxt_index,
        next_token=nxt_token,
        done=done,
    )
