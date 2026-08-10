"""Manager account management (id/pw login accounts).

Admin-only CRUD for named accounts, plus self-service endpoints (``/api/me``,
``/api/me/password``). Access control is enforced in the app middleware:
``/api/manager-users*`` requires an ``admin`` principal, and ``/api/me/password``
is allowed for any authenticated principal (so a viewer can change their own
password). Passwords are hashed in :mod:`app.userstore`.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .. import userstore
from ..config import get_settings
from . import auth

router = APIRouter(prefix="/api", tags=["manager-users"])


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/me")
async def whoami(request: Request) -> dict:
    """Identify the current session for the SPA (who am I / what can I do)."""
    settings = get_settings()
    if not auth.auth_enabled(settings):
        # Open mode — no login required, treat as full access.
        return {"authenticated": False, "auth_enabled": False,
                "username": None, "role": "admin", "bootstrap": False}
    p = auth.current_principal(request, settings)
    if p is None:
        return {"authenticated": False, "auth_enabled": True,
                "username": None, "role": None, "bootstrap": False}
    return {"authenticated": True, "auth_enabled": True,
            "username": p.username, "role": p.role, "bootstrap": p.bootstrap}


@router.get("/manager-users")
async def list_manager_users() -> dict:
    return {"users": userstore.list_users()}


class CreateUserBody(BaseModel):
    username: str
    password: str
    role: str = "viewer"


@router.post("/manager-users")
async def create_manager_user(body: CreateUserBody) -> dict:
    try:
        u = userstore.create(body.username, body.password, body.role, _now())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, **u}


class UpdateUserBody(BaseModel):
    password: str = ""            # empty = keep current
    role: str = ""                # empty = keep current


@router.put("/manager-users/{username}")
async def update_manager_user(username: str, body: UpdateUserBody) -> dict:
    try:
        u = userstore.update(
            username, _now(),
            password=(body.password or None),
            role=(body.role or None),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="존재하지 않는 계정입니다.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, **u}


@router.delete("/manager-users/{username}")
async def delete_manager_user(username: str) -> dict:
    if not userstore.delete(username):
        raise HTTPException(status_code=404, detail="존재하지 않는 계정입니다.")
    return {"ok": True}


class MyPasswordBody(BaseModel):
    old_password: str = ""
    new_password: str = ""


@router.post("/me/password")
async def change_my_password(body: MyPasswordBody, request: Request, response: Response) -> dict:
    """Let the logged-in named user change their own password."""
    settings = get_settings()
    p = auth.current_principal(request, settings)
    if p is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    if p.bootstrap:
        raise HTTPException(
            status_code=400,
            detail="환경변수 관리자 비밀번호는 여기서 변경할 수 없습니다(.env에서 변경).",
        )
    if userstore.verify(p.username, body.old_password) is None:
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
    try:
        userstore.update(p.username, _now(), password=body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # A password change rotates the token fingerprint, which invalidates ALL of
    # this user's existing sessions (including this one). Re-issue the caller's
    # cookie with a fresh token so they aren't logged out of the session that
    # just made the change — other sessions still get invalidated.
    auth._set_session(response, auth.make_user_token(p.username, p.role))
    return {"ok": True}
