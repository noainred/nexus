"""Repository comparison-matrix endpoint."""
from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..matrix import build_matrix
from ..models import MatrixColumn, Repository, RepositoryMatrix
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
