"""Repository comparison-matrix endpoint."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..matrix import build_matrix, build_repo_diff
from ..models import MatrixColumn, Repository, RepositoryDiff, RepositoryMatrix
from ..nexus_client import NexusClient, NexusError
from .. import restore as restore_mod

router = APIRouter(prefix="/api", tags=["matrix"])


@router.post("/matrix/copy-repo")
async def copy_repo_config(
    repository: str = Query(..., description="Repository name to copy."),
    source_id: str = Query(..., description="Instance to copy the config FROM."),
    target_id: str = Query(..., description="Instance to copy the config TO."),
    registry: InstanceRegistry = Depends(get_registry),
) -> dict:
    """Copy one repository's full configuration from one instance to another.

    Reads the source repo's admin config and creates (or overwrites) the same
    repository on the target. Reuses the restore engine in overwrite mode.
    """
    if source_id == target_id:
        raise HTTPException(status_code=400, detail="원본과 대상이 같습니다.")
    src = registry.get(source_id)   # 404 if unknown
    tgt = registry.get(target_id)   # 404 if unknown

    src_client = NexusClient(src, timeout=get_settings().request_timeout)
    try:
        repos = await src_client.list_repositories()
    except NexusError as exc:
        raise HTTPException(status_code=502, detail=f"원본 저장소 목록 조회 실패: {exc.message}")
    by_name = {r.name: r for r in repos}
    if repository not in by_name:
        raise HTTPException(status_code=404, detail=f"원본에 '{repository}' 저장소가 없습니다.")

    # Gather the repo's config plus, for group repos, the configs of every
    # member repository (recursively) so missing members can be created on the
    # target first — otherwise the group create fails ("Member ... does not
    # exist").
    collected: Dict[str, Optional[dict]] = {}

    async def gather(name: str) -> None:
        if name in collected:
            return
        r = by_name.get(name)
        if r is None:
            collected[name] = None  # member missing on source
            return
        fmt = (r.format or "").strip()
        type_ = (r.type or "").strip()
        try:
            cfg = await src_client.get_repository_config(fmt, type_, name)
        except NexusError as exc:
            collected[name] = {"name": name, "_error": exc.message}
            return
        collected[name] = {"name": name, "format": fmt, "type": type_, "config": cfg}
        for member in (cfg.get("group") or {}).get("memberNames") or []:
            await gather(member)

    await gather(repository)

    main = collected.pop(repository)
    if not main or "config" not in main:
        reason = (main or {}).get("_error", "포맷/설정 확인 불가")
        raise HTTPException(status_code=502, detail=f"원본 설정 읽기 실패(권한 등): {reason}")

    members = [e for e in collected.values() if e and "config" in e]
    tgt_client = NexusClient(tgt, timeout=get_settings().request_timeout)

    items: List[dict] = []
    # 1) Ensure member repos exist (create only what is missing).
    if members:
        dep = await restore_mod.apply(
            tgt_client, {"sections": {"repositories": members}}, {"repositories"}, "merge"
        )
        items.extend(dep.get("items", []))
    # 2) Create/overwrite the dragged repo itself.
    res = await restore_mod.apply(
        tgt_client, {"sections": {"repositories": [main]}}, {"repositories"}, "overwrite"
    )
    # Put the dragged repo's result first so the UI surfaces it.
    items = res.get("items", []) + items

    summary = {"ok": 0, "update": 0, "skip": 0, "fail": 0}
    for it in items:
        summary[it["status"]] = summary.get(it["status"], 0) + 1
    return {"items": items, "summary": summary, "mode": "overwrite"}


async def _fetch_repos(
    instance,
) -> Tuple[MatrixColumn, Optional[List[Repository]]]:
    """Fetch one instance's repositories, capturing errors into the column."""
    column = MatrixColumn(id=instance.id, name=instance.name)
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        column.reachable = False
        column.error = exc.message
        return column, None
    return column, repos


@router.get("/matrix", response_model=RepositoryMatrix)
async def repository_matrix(
    registry: InstanceRegistry = Depends(get_registry),
) -> RepositoryMatrix:
    """Compare repository presence and configuration across all instances.

    Columns preserve the order instances are configured (e.g. DMZ, Core,
    Site1..N) so the dashboard grid mirrors the network topology.
    """
    instances = registry.comparison()
    results = await asyncio.gather(*(_fetch_repos(i) for i in instances))

    columns = [column for column, _ in results]
    repos_by_instance = {
        column.id: repos for column, repos in results
    }
    return build_matrix(columns, repos_by_instance)


async def _fetch_repo_config(
    instance, repository: str
) -> Tuple[MatrixColumn, Optional[Dict[str, Any]]]:
    """Fetch one repository's full config on an instance.

    Returns ``(column, None)`` when the repo is absent (column stays reachable)
    or when the instance is unreachable (column flagged with the error).
    """
    column = MatrixColumn(id=instance.id, name=instance.name)
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    try:
        repos = await client.list_repositories()
        match = next((r for r in repos if r.name == repository), None)
        if match is None:
            return column, None  # reachable, but repo not present here
        config = await client.get_repository_config(
            match.format or "", match.type or "", repository
        )
    except NexusError as exc:
        column.reachable = False
        column.error = exc.message
        return column, None
    return column, config


@router.get("/repository-detail", response_model=RepositoryDiff)
async def repository_detail(
    repository: str = Query(..., description="Repository name to compare."),
    registry: InstanceRegistry = Depends(get_registry),
) -> RepositoryDiff:
    """Field-by-field configuration comparison for one repository.

    Drills into the matrix: for the given repository, fetch its full config on
    every instance and diff each setting so drift is pinpointed exactly.
    """
    instances = registry.all()
    results = await asyncio.gather(
        *(_fetch_repo_config(i, repository) for i in instances)
    )
    columns = [column for column, _ in results]
    configs = {column.id: config for column, config in results}
    return build_repo_diff(repository, columns, configs)


@router.get("/compare", response_model=RepositoryDiff)
async def compare_repositories(
    left_instance: str = Query(..., description="Left side instance id."),
    left_repo: str = Query(..., description="Left side repository name."),
    right_instance: str = Query(..., description="Right side instance id."),
    right_repo: str = Query(..., description="Right side repository name."),
    registry: InstanceRegistry = Depends(get_registry),
) -> RepositoryDiff:
    """Compare any two repositories across (possibly different) instances.

    Unlike the matrix/detail views which match by repository name, this lets
    an operator pick an arbitrary repository on server A and compare it,
    field by field, against an arbitrarily named one on server B.
    """
    left = registry.get(left_instance)
    right = registry.get(right_instance)
    (lcol, lcfg), (rcol, rcfg) = await asyncio.gather(
        _fetch_repo_config(left, left_repo),
        _fetch_repo_config(right, right_repo),
    )
    left_column = MatrixColumn(
        id="left",
        name=f"{left.name} / {left_repo}",
        reachable=lcol.reachable,
        error=lcol.error,
    )
    right_column = MatrixColumn(
        id="right",
        name=f"{right.name} / {right_repo}",
        reachable=rcol.reachable,
        error=rcol.error,
    )
    configs = {"left": lcfg, "right": rcfg}
    return build_repo_diff(f"{left_repo} ↔ {right_repo}", [left_column, right_column], configs)
