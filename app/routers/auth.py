"""Manager login + audit-log endpoints.

Two coexisting credential sources:
  * the single bootstrap ``admin_password`` (``NEXUS_MANAGER_ADMIN_PASSWORD``),
    always an ``admin`` role — its session cookie is signed with the password
    itself, so changing it invalidates every bootstrap session;
  * named id/pw accounts (``app.userstore``) scoped to a role (admin/viewer) —
    their session cookies are signed with a persisted server secret.

Auth activates when either source exists; otherwise the manager is open (status
screens only). A leaked cookie stops working after the TTL. Both cookie kinds
share the ``nm_session`` cookie; :func:`current_principal` resolves whichever
one is present into a :class:`Principal`.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..config import Settings, get_settings
from .. import userstore

router = APIRouter(prefix="/api", tags=["auth"])

COOKIE = "nm_session"
_SESSION_HOURS = 12
_SESSION_TTL = _SESSION_HOURS * 3600

# Login brute-force throttle (per client IP, in-memory). After _RL_MAX failed
# attempts inside _RL_WINDOW seconds, further attempts are refused until the
# oldest failure ages out of the window. A successful login clears the counter.
_RL_WINDOW = 300
_RL_MAX = 8
_LOGIN_FAILS: Dict[str, List[float]] = {}


def _sign(password: str, msg: str) -> str:
    return hmac.new(password.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _consteq(a: str, b: str) -> bool:
    """Constant-time string compare that tolerates non-ASCII. hmac.compare_digest
    raises TypeError on non-ASCII str args, so compare UTF-8 bytes instead — a
    Korean admin_password must not 500 the login."""
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


def _user_pv(u: Optional[dict]) -> str:
    """Short fingerprint of a user's stored password hash, embedded in the
    session token so a password change invalidates existing sessions."""
    h = (u or {}).get("hash", "")
    return hashlib.sha256(("pv|" + h).encode("utf-8")).hexdigest()[:16]


def make_token(password: str, ttl: int = _SESSION_TTL) -> str:
    """Signed session token of the form ``<exp_hex>.<hmac>`` bound to expiry."""
    exp = int(time.time()) + ttl
    return f"{exp:x}.{_sign(password, 'nexus-manager-v2|' + format(exp, 'x'))}"


def verify_token(password: str, tok: str) -> bool:
    if not tok or "." not in tok:
        return False
    exp_hex, sig = tok.split(".", 1)
    try:
        exp = int(exp_hex, 16)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(sig, _sign(password, "nexus-manager-v2|" + exp_hex))


@dataclass
class Principal:
    username: str
    role: str            # "admin" | "viewer"
    bootstrap: bool = False


def make_user_token(username: str, role: str, ttl: int = _SESSION_TTL) -> str:
    """Signed named-account token: ``<payload_b64>.<hmac>`` where payload holds
    the subject, role and expiry. Signed with the persisted server secret."""
    exp = int(time.time()) + ttl
    pv = _user_pv(userstore.get(username))
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": username, "role": role, "exp": exp, "pv": pv}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return payload + "." + _sign(userstore.server_secret(), "nexus-user-v1|" + payload)


def verify_user_token(tok: str) -> Optional[Principal]:
    if not tok or "." not in tok:
        return None
    payload_b64, sig = tok.rsplit(".", 1)
    try:
        pad = "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        sub, role, exp = data["sub"], data["role"], int(data["exp"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if exp < int(time.time()):
        return None
    if not hmac.compare_digest(sig, _sign(userstore.server_secret(), "nexus-user-v1|" + payload_b64)):
        return None
    # The stored role is authoritative — a deleted/downgraded user's live token
    # must not keep elevated access.
    u = userstore.get(sub)
    if u is None:
        return None
    # Bind to the current password: a password change rotates the fingerprint,
    # invalidating sessions issued before the change (tokens without pv, i.e.
    # issued by an older build, also fail here and force a fresh login).
    if not hmac.compare_digest(str(data.get("pv", "")), _user_pv(u)):
        return None
    return Principal(username=sub, role=u.get("role", "viewer"))


def auth_enabled(settings: Settings) -> bool:
    """Auth is on when a bootstrap password is set or any named account exists."""
    if settings.admin_password:
        return True
    try:
        return userstore.count() > 0
    except Exception:  # noqa: BLE001 - never let a store error open the manager
        return False


def current_principal(request: Request, settings: Settings) -> Optional[Principal]:
    """Resolve the request's session cookie to a Principal, or None."""
    tok = request.cookies.get(COOKIE, "")
    if not tok:
        return None
    pw = settings.admin_password
    if pw and verify_token(pw, tok):
        return Principal(username="admin", role="admin", bootstrap=True)
    return verify_user_token(tok)


def is_authenticated(request: Request, settings: Settings) -> bool:
    if not auth_enabled(settings):
        return True
    return current_principal(request, settings) is not None


def _rl_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _rl_locked(ip: str) -> Optional[int]:
    """Seconds to wait if this IP is currently locked out, else None."""
    now = time.time()
    fails = [t for t in _LOGIN_FAILS.get(ip, []) if now - t < _RL_WINDOW]
    _LOGIN_FAILS[ip] = fails
    if len(fails) >= _RL_MAX:
        return max(1, int(_RL_WINDOW - (now - fails[0])))
    return None


class LoginBody(BaseModel):
    username: str = ""   # empty = bootstrap admin (admin_password)
    password: str = ""


@router.get("/auth-status")
async def auth_status(request: Request) -> dict:
    settings = get_settings()
    required = auth_enabled(settings)
    return {"required": required,
            "authenticated": (not required) or is_authenticated(request, settings)}


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=_SESSION_TTL, httponly=True, samesite="lax",
    )


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    settings = get_settings()
    if not auth_enabled(settings):
        return {"ok": True, "required": False}
    ip = _rl_ip(request)
    wait = _rl_locked(ip)
    if wait is not None:
        raise HTTPException(
            status_code=429,
            detail=f"로그인 시도가 너무 많습니다. {wait}초 후 다시 시도하세요.",
        )
    username = (body.username or "").strip()
    if username:
        role = userstore.verify(username, body.password)
        if not role:
            _LOGIN_FAILS.setdefault(ip, []).append(time.time())
            raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
        _LOGIN_FAILS.pop(ip, None)
        un = userstore.norm_username(username)
        _set_session(response, make_user_token(un, role))
        return {"ok": True, "username": un, "role": role, "bootstrap": False}
    # Bootstrap admin (no username) — the env admin_password.
    if not settings.admin_password or not _consteq(body.password, settings.admin_password):
        _LOGIN_FAILS.setdefault(ip, []).append(time.time())
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    _LOGIN_FAILS.pop(ip, None)  # clear throttle on success
    _set_session(response, make_token(settings.admin_password))
    return {"ok": True, "username": "admin", "role": "admin", "bootstrap": True}


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
    new = not p.exists()
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if new:
        # Audit lines record client IPs and request paths — keep them private.
        from ..storage import restrict_mode
        restrict_mode(p, 0o600)


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
