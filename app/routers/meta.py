"""App metadata endpoints (version, release notes, portal branding)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from .. import __version__
from ..config import get_settings
from ..models import ReleaseNotes
from ..release_notes import RELEASE_NOTES

router = APIRouter(prefix="/api", tags=["meta"])

DEFAULT_TITLE = "Nexus Repository 통합 관리"


@router.get("/release-notes", response_model=ReleaseNotes)
async def release_notes() -> ReleaseNotes:
    return ReleaseNotes(version=__version__, notes=RELEASE_NOTES)


def _portal_path() -> Path:
    p = Path(get_settings().portal_config_file)
    return p if p.is_absolute() else Path(os.getcwd()) / p


def _read_title() -> str:
    p = _portal_path()
    if p.is_file():
        try:
            t = (json.loads(p.read_text(encoding="utf-8")).get("title") or "").strip()
            if t:
                return t
        except Exception:  # noqa: BLE001
            pass
    return DEFAULT_TITLE


class PortalConfig(BaseModel):
    title: str = ""


@router.get("/portal")
async def get_portal() -> dict:
    """Dashboard branding (title) — public so it shows before login too."""
    return {"title": _read_title(), "default_title": DEFAULT_TITLE}


@router.put("/portal")
async def set_portal(body: PortalConfig) -> dict:
    title = (body.title or "").strip() or DEFAULT_TITLE
    p = _portal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"title": title}, ensure_ascii=False), encoding="utf-8")
    return {"title": title}
