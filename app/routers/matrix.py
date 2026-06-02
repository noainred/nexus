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
