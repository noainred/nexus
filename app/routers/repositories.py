"""Repository and component management endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Response

from ..models import ComponentPage, Repository
from ..nexus_client import NexusClient, NexusError
from ..deps import get_client

router = APIRouter(prefix="/api/instances/{instance_id}", tags=["repositories"])


def _translate(exc: NexusError) -> HTTPException:
    status = exc.status_code or 502
    return HTTPException(status_code=status, detail=exc.message)


@router.get("/repositories", response_model=List[Repository])
async def list_repositories(instance_id: str) -> List[Repository]:
    client: NexusClient = get_client(instance_id)
    try:
        return await client.list_repositories()
    except NexusError as exc:
        raise _translate(exc)


@router.delete("/repositories/{name}", status_code=204, response_class=Response)
async def delete_repository(instance_id: str, name: str) -> Response:
    client: NexusClient = get_client(instance_id)
    try:
        await client.delete_repository(name)
    except NexusError as exc:
        raise _translate(exc)
    return Response(status_code=204)


@router.get("/components", response_model=ComponentPage)
async def list_components(
    instance_id: str,
    repository: str = Query(..., description="Repository name to browse."),
    continuation_token: Optional[str] = Query(default=None),
) -> ComponentPage:
    client: NexusClient = get_client(instance_id)
    try:
        return await client.list_components(repository, continuation_token)
    except NexusError as exc:
        raise _translate(exc)


@router.delete("/components/{component_id}", status_code=204, response_class=Response)
async def delete_component(instance_id: str, component_id: str) -> Response:
    client: NexusClient = get_client(instance_id)
    try:
        await client.delete_component(component_id)
    except NexusError as exc:
        raise _translate(exc)
    return Response(status_code=204)
