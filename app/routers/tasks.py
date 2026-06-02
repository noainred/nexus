"""Scheduled task monitoring and execution endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Response

from ..deps import get_client
from ..models import Task
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api/instances/{instance_id}/tasks", tags=["tasks"])


def _translate(exc: NexusError) -> HTTPException:
    return HTTPException(status_code=exc.status_code or 502, detail=exc.message)


@router.get("", response_model=List[Task])
async def list_tasks(instance_id: str) -> List[Task]:
    client: NexusClient = get_client(instance_id)
    try:
        return await client.list_tasks()
    except NexusError as exc:
        raise _translate(exc)


@router.post("/{task_id}/run", status_code=204, response_class=Response)
async def run_task(instance_id: str, task_id: str) -> Response:
    client: NexusClient = get_client(instance_id)
    try:
        await client.run_task(task_id)
    except NexusError as exc:
        raise _translate(exc)
    return Response(status_code=204)


@router.post("/{task_id}/stop", status_code=204, response_class=Response)
async def stop_task(instance_id: str, task_id: str) -> Response:
    client: NexusClient = get_client(instance_id)
    try:
        await client.stop_task(task_id)
    except NexusError as exc:
        raise _translate(exc)
    return Response(status_code=204)
