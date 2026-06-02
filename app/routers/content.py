"""Cross-site content (component) synchronisation comparison."""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Set, Tuple

from fastapi import APIRouter, Depends, Query

from ..config import get_settings
from ..deps import InstanceRegistry, get_registry
from ..models import ContentMatrix, ContentRow, MatrixColumn
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api", tags=["content"])

_MAX_PAGES = 50


def _component_key(comp) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    parts = [p for p in (comp.group, comp.name, comp.version) if p]
    display = ":".join(parts) if parts else comp.id
    return display, comp.group, comp.name, comp.version


async def _fetch_keys(
    instance, repository: str
) -> Tuple[MatrixColumn, Optional[Dict[str, ContentRow]], bool]:
    """Collect a repository's component keys on one instance.

    Returns (column, keys-or-None, truncated). ``keys`` is None when the repo
    is absent there (column.error set) or the instance is unreachable
    (column.reachable False).
    """
    column = MatrixColumn(id=instance.id, name=instance.name)
    client = NexusClient(instance, timeout=get_settings().request_timeout)
    found: Dict[str, ContentRow] = {}
    token = None
    pages = 0
    truncated = False
    try:
        while True:
            page = await client.list_components(repository, token)
            for comp in page.items:
                display, group, name, version = _component_key(comp)
                found[display] = ContentRow(
                    key=display, group=group, name=name, version=version
                )
            token = page.continuation_token
            pages += 1
            if not token:
                break
            if pages >= _MAX_PAGES:
                truncated = True
                break
    except NexusError as exc:
        if exc.status_code is None:
            column.reachable = False
            column.error = exc.message
        else:
            # 4xx commonly means the repository does not exist on this instance.
            column.error = "저장소 없음"
        return column, None, False
    return column, found, truncated


@router.get("/content-compare", response_model=ContentMatrix)
async def content_compare(
    repository: str = Query(..., description="Repository name to compare."),
    registry: InstanceRegistry = Depends(get_registry),
) -> ContentMatrix:
    """Compare which components actually exist in a repository across sites.

    Unlike the config matrix, this reads the real artifacts so silent content
    drift between sites (no Pro replication) is caught.
    """
    instances = registry.all()
    results = await asyncio.gather(
        *(_fetch_keys(i, repository) for i in instances)
    )

    columns = [col for col, _, _ in results]
    keys_by_instance: Dict[str, Optional[Dict[str, ContentRow]]] = {
        col.id: keys for col, keys, _ in results
    }
    truncated = any(t for _, _, t in results)

    applicable = [cid for cid, keys in keys_by_instance.items() if keys is not None]

    all_keys: Set[str] = set()
    meta: Dict[str, ContentRow] = {}
    for cid in applicable:
        for key, row in keys_by_instance[cid].items():
            all_keys.add(key)
            meta.setdefault(key, row)

    rows = []
    for key in sorted(all_keys):
        present = {
            cid: (key in keys_by_instance[cid]) for cid in applicable
        }
        base = meta[key]
        rows.append(
            ContentRow(
                key=key,
                group=base.group,
                name=base.name,
                version=base.version,
                present=present,
                consistent=all(present.values()) if present else True,
            )
        )

    return ContentMatrix(
        repository=repository, columns=columns, rows=rows, truncated=truncated
    )
