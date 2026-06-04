"""Download-usage report endpoints.

Aggregates per-asset ``lastDownloaded`` / ``fileSize`` to show which packages
users actually downloaded and how much storage they account for — for a single
repository (detail) or for every repository on a server (overview).
"""
from __future__ import annotations

import asyncio
from typing import List, Tuple

from fastapi import APIRouter, HTTPException, Query

from ..deps import get_client
from ..models import (
    AssetDownload,
    DownloadReport,
    RepoDownloadSummary,
    ServerDownloadSummary,
)
from ..nexus_client import NexusClient, NexusError

router = APIRouter(prefix="/api/instances/{instance_id}", tags=["downloads"])

# Safety cap so a huge repository cannot make a single request page forever.
_MAX_PAGES = 50
# Max repositories scanned at once in the server-wide summary.
_SUMMARY_CONCURRENCY = 6


async def _scan_repo(
    client: NexusClient, repository: str, collect_items: bool
) -> Tuple[int, int, int, int, bool, List[AssetDownload]]:
    """Page a repository's assets, aggregating download usage.

    Returns ``(total, downloaded, total_size, downloaded_size, truncated,
    items)``. ``items`` is only populated when ``collect_items`` is True.
    """
    total = downloaded = total_size = downloaded_size = 0
    items: List[AssetDownload] = []
    token = None
    pages = 0
    truncated = False

    while True:
        page = await client.list_assets(repository, token)
        for asset in page.items:
            total += 1
            size = asset.file_size or 0
            total_size += size
            if asset.last_downloaded:
                downloaded += 1
                downloaded_size += size
                if collect_items:
                    items.append(
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

    return total, downloaded, total_size, downloaded_size, truncated, items


@router.get("/downloads", response_model=DownloadReport)
async def download_report(
    instance_id: str,
    repository: str = Query(..., description="Repository to scan."),
    limit: int = Query(200, ge=1, le=1000, description="Max rows to return."),
) -> DownloadReport:
    """Scan one repository's assets and summarise actual download usage."""
    client: NexusClient = get_client(instance_id)
    try:
        total, downloaded, total_size, dl_size, truncated, items = await _scan_repo(
            client, repository, collect_items=True
        )
    except NexusError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    items.sort(key=lambda a: a.last_downloaded or "", reverse=True)
    return DownloadReport(
        repository=repository,
        total_assets=total,
        downloaded_assets=downloaded,
        total_size_bytes=total_size,
        downloaded_size_bytes=dl_size,
        truncated=truncated,
        items=items[:limit],
    )


@router.get("/downloads-summary", response_model=ServerDownloadSummary)
async def downloads_summary(instance_id: str) -> ServerDownloadSummary:
    """Download usage for every repository on the server.

    Group repositories are skipped: their /assets view aggregates member repo
    assets and would double-count against the hosted/proxy repos.
    """
    client: NexusClient = get_client(instance_id)
    try:
        repos = await client.list_repositories()
    except NexusError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=exc.message)

    scannable = [r for r in repos if (r.type or "").lower() != "group"]

    # Limit concurrency so scanning many repos at once doesn't overwhelm the
    # Nexus server (which otherwise surfaces as spurious connection errors).
    sem = asyncio.Semaphore(_SUMMARY_CONCURRENCY)

    async def summarise(repo) -> RepoDownloadSummary:
        async with sem:
            try:
                total, downloaded, total_size, dl_size, truncated, _ = await _scan_repo(
                    client, repo.name, collect_items=False
                )
            except NexusError as exc:
                return RepoDownloadSummary(
                    repository=repo.name,
                    format=repo.format,
                    type=repo.type,
                    error=exc.message,
                )
        return RepoDownloadSummary(
            repository=repo.name,
            format=repo.format,
            type=repo.type,
            total_assets=total,
            downloaded_assets=downloaded,
            total_size_bytes=total_size,
            downloaded_size_bytes=dl_size,
            truncated=truncated,
        )

    summaries = await asyncio.gather(*(summarise(r) for r in scannable))
    summaries = sorted(summaries, key=lambda s: s.repository.lower())

    return ServerDownloadSummary(
        instance_id=instance_id,
        total_assets=sum(s.total_assets for s in summaries),
        downloaded_assets=sum(s.downloaded_assets for s in summaries),
        total_size_bytes=sum(s.total_size_bytes for s in summaries),
        downloaded_size_bytes=sum(s.downloaded_size_bytes for s in summaries),
        repositories=list(summaries),
    )
