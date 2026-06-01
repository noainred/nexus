"""Instance listing endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from ..deps import InstanceRegistry, get_registry
from ..models import InstanceSummary

router = APIRouter(prefix="/api/instances", tags=["instances"])


@router.get("", response_model=List[InstanceSummary])
async def list_instances(
    registry: InstanceRegistry = Depends(get_registry),
) -> List[InstanceSummary]:
    """Return the managed instances (without credentials)."""
    return [
        InstanceSummary(id=i.id, name=i.name, base_url=i.base_url)
        for i in registry.all()
    ]
