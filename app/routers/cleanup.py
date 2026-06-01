"""Cleanup policy endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from ..models import CleanupPolicy, CleanupPolicyCreate
from ..nexus_client import NexusClient, NexusError
from ..deps import get_client

router = APIRouter(
    prefix="/api/instances/{instance_id}/cleanup-policies", tags=["cleanup"]
)


def _translate(exc: NexusError) -> HTTPException:
    return HTTPException(status_code=exc.status_code or 502, detail=exc.message)


def _build_criteria(payload: CleanupPolicyCreate) -> dict:
    """Map the simplified create payload to Nexus' criteria object."""
    criteria: dict = {}
    if payload.criteria_last_blob_updated is not None:
        criteria["lastBlobUpdated"] = payload.criteria_last_blob_updated
    if payload.criteria_last_downloaded is not None:
        criteria["lastDownloaded"] = payload.criteria_last_downloaded
    if payload.criteria_release_type:
        criteria["releaseType"] = payload.criteria_release_type
    if payload.criteria_asset_regex:
        criteria["regex"] = payload.criteria_asset_regex
    return criteria


@router.get("", response_model=List[CleanupPolicy])
async def list_cleanup_policies(instance_id: str) -> List[CleanupPolicy]:
    client: NexusClient = get_client(instance_id)
    try:
        return await client.list_cleanup_policies()
    except NexusError as exc:
        raise _translate(exc)


@router.post("", response_model=CleanupPolicy, status_code=201)
async def create_cleanup_policy(
    instance_id: str, body: CleanupPolicyCreate
) -> CleanupPolicy:
    client: NexusClient = get_client(instance_id)
    criteria = _build_criteria(body)
    if not criteria:
        raise HTTPException(
            status_code=400, detail="At least one cleanup criterion is required."
        )
    payload = {
        "name": body.name,
        "format": body.format,
        "notes": body.notes or "",
        "criteria": criteria,
    }
    try:
        await client.create_cleanup_policy(payload)
    except NexusError as exc:
        raise _translate(exc)
    return CleanupPolicy(
        name=body.name,
        format=body.format,
        notes=body.notes,
        criteria=criteria,
    )
