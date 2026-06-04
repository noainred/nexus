"""App metadata endpoints (version, release notes)."""
from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..models import ReleaseNotes
from ..release_notes import RELEASE_NOTES

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/release-notes", response_model=ReleaseNotes)
async def release_notes() -> ReleaseNotes:
    return ReleaseNotes(version=__version__, notes=RELEASE_NOTES)
