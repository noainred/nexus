"""App metadata endpoints (version, release notes, portal branding)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

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


def _read_config() -> dict:
    p = _portal_path()
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except Exception:  # noqa: BLE001
            pass
    return {}


def _read_title() -> str:
    t = (_read_config().get("title") or "").strip()
    return t or DEFAULT_TITLE


class PortalConfig(BaseModel):
    title: str = ""
    hidden_tabs: Optional[List[str]] = None   # None = keep existing


@router.get("/portal")
async def get_portal() -> dict:
    """Dashboard branding (title) + hidden tabs — public so it applies before
    login too."""
    cfg = _read_config()
    return {
        "title": _read_title(),
        "default_title": DEFAULT_TITLE,
        "hidden_tabs": [str(x) for x in (cfg.get("hidden_tabs") or [])],
    }


@router.put("/portal")
async def set_portal(body: PortalConfig) -> dict:
    cfg = _read_config()
    cfg["title"] = (body.title or "").strip() or DEFAULT_TITLE
    if body.hidden_tabs is not None:
        cfg["hidden_tabs"] = [str(x) for x in body.hidden_tabs if x]
    p = _portal_path()
    from ..storage import atomic_write_text
    atomic_write_text(p, json.dumps(cfg, ensure_ascii=False))
    return {"title": cfg["title"], "hidden_tabs": cfg.get("hidden_tabs") or []}
