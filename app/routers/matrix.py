"""Repository comparison-matrix endpoint."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..matrix import build_matrix, build_repo_diff
from ..models import MatrixColumn, Repository, RepositoryDiff, RepositoryMatrix
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["matrix"])


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
    instances = registry.all()
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
