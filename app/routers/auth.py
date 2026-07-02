"""Manager login (single admin password) + audit-log endpoints.

Authentication is optional: it activates only when ``admin_password`` is set
(``NEXUS_MANAGER_ADMIN_PASSWORD``). The session is a stateless cookie signed
with the admin password as the HMAC key and bound to an expiry timestamp:
changing the password invalidates every session, and a leaked cookie stops
working after the TTL even without a password change. Because the key is the
password (not a per-process random), sessions survive a manager restart.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..config import Settings, get_settings

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


def is_authenticated(request: Request, settings: Settings) -> bool:
    pw = settings.admin_password
    if not pw:
        return True
    return verify_token(pw, request.cookies.get(COOKIE, ""))


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
    password: str = ""


@router.get("/auth-status")
async def auth_status(request: Request) -> dict:
    settings = get_settings()
    required = bool(settings.admin_password)
    return {"required": required,
            "authenticated": (not required) or is_authenticated(request, settings)}


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    settings = get_settings()
    if not settings.admin_password:
        return {"ok": True, "required": False}
    ip = _rl_ip(request)
    wait = _rl_locked(ip)
    if wait is not None:
        raise HTTPException(
            status_code=429,
            detail=f"로그인 시도가 너무 많습니다. {wait}초 후 다시 시도하세요.",
        )
    if not hmac.compare_digest(body.password, settings.admin_password):
        _LOGIN_FAILS.setdefault(ip, []).append(time.time())
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    _LOGIN_FAILS.pop(ip, None)  # clear throttle on success
    response.set_cookie(
        COOKIE, make_token(settings.admin_password),
        max_age=_SESSION_TTL, httponly=True, samesite="lax",
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
