"""Download-usage report endpoint.

Aggregates per-asset ``lastDownloaded`` / ``fileSize`` to show which packages
users actually downloaded and how much storage they account for.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..deps import get_client
from ..models import AssetDownload, DownloadReport
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api/instances/{instance_id}", tags=["downloads"])

# Safety cap so a huge repository cannot make a single request page forever.
_MAX_PAGES = 50


@router.get("/downloads", response_model=DownloadReport)
async def download_report(
    instance_id: str,
    repository: str = Query(..., description="Repository to scan."),
    limit: int = Query(200, ge=1, le=1000, description="Max rows to return."),
) -> DownloadReport:
    """Scan a repository's assets and summarise actual download usage.

    Counts every asset, flags those ever downloaded (``lastDownloaded`` set),
    and sums their sizes. The returned ``items`` are the downloaded assets,
    most-recent first, capped at ``limit``.
    """
    client: NexusClient = get_client(instance_id)

    total_assets = 0
    downloaded_assets = 0
    total_size = 0
    downloaded_size = 0
    downloaded: list[AssetDownload] = []
    token = None
    pages = 0
    truncated = False

    try:
        while True:
            page = await client.list_assets(repository, token)
            for asset in page.items:
                total_assets += 1
                size = asset.file_size or 0
                total_size += size
                if asset.last_downloaded:
                    downloaded_assets += 1
                    downloaded_size += size
                    downloaded.append(
                        AssetDownload(
                            path=asset.path or asset.id,
                            size_bytes=asset.file_size,
                            last_downloaded=asset.last_downloaded,
                            content_type=asset.content_type,
                        )
                    )
            token = page.continuation_token
            pages += 1
            if not token:
                break
            if pages >= _MAX_PAGES:
                truncated = True
                break
    except NexusError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    downloaded.sort(key=lambda a: a.last_downloaded or "", reverse=True)

    return DownloadReport(
        repository=repository,
        total_assets=total_assets,
        downloaded_assets=downloaded_assets,
        total_size_bytes=total_size,
        downloaded_size_bytes=downloaded_size,
        truncated=truncated,
        items=downloaded[:limit],
    )
