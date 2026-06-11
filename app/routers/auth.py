"""Manager login (single admin password) + audit-log endpoints.

Authentication is optional: it activates only when ``admin_password`` is set
(``NEXUS_MANAGER_ADMIN_PASSWORD``). The session is a stateless HMAC cookie
derived from the password, so it survives restarts and is invalidated by
changing the password.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["auth"])

COOKIE = "nm_session"
_SESSION_HOURS = 12


def session_token(password: str) -> str:
    return hmac.new(password.encode("utf-8"), b"nexus-manager-v1", hashlib.sha256).hexdigest()


def is_authenticated(request: Request, settings: Settings) -> bool:
    pw = settings.admin_password
    if not pw:
        return True
    tok = request.cookies.get(COOKIE, "")
    return hmac.compare_digest(tok, session_token(pw))


class LoginBody(BaseModel):
    password: str = ""


@router.get("/auth-status")
async def auth_status(request: Request) -> dict:
    settings = get_settings()
    required = bool(settings.admin_password)
    return {"required": required,
            "authenticated": (not required) or is_authenticated(request, settings)}


@router.post("/login")
async def login(body: LoginBody, response: Response) -> dict:
    settings = get_settings()
    if not settings.admin_password:
        return {"ok": True, "required": False}
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    response.set_cookie(
        COOKIE, session_token(settings.admin_password),
        max_age=_SESSION_HOURS * 3600, httponly=True, samesite="lax",
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE)
    return {"ok": True}


def _audit_path(settings: Settings) -> Path:
    p = Path(settings.audit_file)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def write_audit(settings: Settings, entry: dict) -> None:
    p = _audit_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@router.get("/audit")
async def read_audit(limit: int = 200) -> List[dict]:
    """Last ``limit`` audit entries (write operations), newest first."""
    p = _audit_path(get_settings())
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    out: List[dict] = []
    for line in reversed(lines[-max(1, min(limit, 1000)):]):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
