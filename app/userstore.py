"""Manager login accounts (id + password), coexisting with the single
bootstrap ``admin_password``.

Named accounts let several people sign in with their own id and be scoped to a
role. Passwords are stored only as a salted PBKDF2-HMAC-SHA256 hash (stdlib —
no extra dependency for the air-gapped build), in ``accounts.json`` written
atomically with 0600 perms. The file also holds a random server secret used to
sign user session cookies (so sessions survive a restart).
"""

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path
from typing import List, Optional

from .config import get_settings
from .storage import atomic_write_text

ROLES = ("admin", "viewer")
_ITERS = 200_000
_USERNAME_RE = re.compile(r"[a-z0-9._-]{3,32}")


def _store_path() -> Path:
    s = get_settings()
    p = Path(getattr(s, "accounts_file", "accounts.json"))
    return p if p.is_absolute() else Path(os.getcwd()) / p


def _load() -> dict:
    p = _store_path()
    if p.is_file():
        try:
            d = json.loads(p.read_text("utf-8"))
            if isinstance(d, dict):
                d.setdefault("users", [])
                return d
        except Exception:  # noqa: BLE001 - corrupt store must not lock everyone out
            pass
    return {"users": []}


def _save(store: dict) -> None:
    atomic_write_text(
        _store_path(), json.dumps(store, ensure_ascii=False, indent=2), mode=0o600
    )


def _hash(password: str, salt: bytes, iters: int = _ITERS) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters).hex()


def norm_username(u: str) -> str:
    return (u or "").strip().lower()


def valid_username(un: str) -> bool:
    return _USERNAME_RE.fullmatch(un or "") is not None


def server_secret() -> str:
    """Stable HMAC key for signing user session tokens, created on first use."""
    store = _load()
    sec = store.get("secret")
    if not sec:
        sec = secrets.token_hex(32)
        store["secret"] = sec
        _save(store)
    return sec


def count() -> int:
    return len(_load().get("users", []))


def list_users() -> List[dict]:
    """Public listing (no salts/hashes)."""
    return [
        {"username": u.get("username"), "role": u.get("role", "viewer"),
         "created_at": u.get("created_at"), "updated_at": u.get("updated_at")}
        for u in _load().get("users", [])
    ]


def get(username: str) -> Optional[dict]:
    un = norm_username(username)
    return next((u for u in _load().get("users", []) if u.get("username") == un), None)


def verify(username: str, password: str) -> Optional[str]:
    """Return the user's role when credentials match, else None."""
    u = get(username)
    if not u:
        return None
    try:
        salt = bytes.fromhex(u.get("salt", ""))
    except ValueError:
        return None
    calc = _hash(password, salt, int(u.get("iters", _ITERS)))
    if hmac.compare_digest(calc, u.get("hash", "")):
        return u.get("role", "viewer")
    return None


def create(username: str, password: str, role: str, ts: str) -> dict:
    un = norm_username(username)
    if not valid_username(un):
        raise ValueError("아이디는 영문 소문자/숫자/._- 3~32자여야 합니다.")
    if not password or len(password) < 4:
        raise ValueError("비밀번호는 4자 이상이어야 합니다.")
    if role not in ROLES:
        raise ValueError("역할은 admin 또는 viewer 여야 합니다.")
    store = _load()
    if any(u.get("username") == un for u in store["users"]):
        raise ValueError("이미 존재하는 아이디입니다.")
    salt = secrets.token_bytes(16)
    store["users"].append({
        "username": un, "role": role, "salt": salt.hex(),
        "hash": _hash(password, salt), "iters": _ITERS,
        "created_at": ts, "updated_at": ts,
    })
    _save(store)
    return {"username": un, "role": role}


def update(username: str, ts: str, *,
           password: Optional[str] = None, role: Optional[str] = None) -> dict:
    un = norm_username(username)
    store = _load()
    u = next((x for x in store["users"] if x.get("username") == un), None)
    if u is None:
        raise KeyError(un)
    if role is not None:
        if role not in ROLES:
            raise ValueError("역할은 admin 또는 viewer 여야 합니다.")
        u["role"] = role
    if password is not None:
        if len(password) < 4:
            raise ValueError("비밀번호는 4자 이상이어야 합니다.")
        salt = secrets.token_bytes(16)
        u["salt"], u["hash"], u["iters"] = salt.hex(), _hash(password, salt), _ITERS
    u["updated_at"] = ts
    _save(store)
    return {"username": un, "role": u.get("role", "viewer")}


def delete(username: str) -> bool:
    un = norm_username(username)
    store = _load()
    before = len(store["users"])
    store["users"] = [u for u in store["users"] if u.get("username") != un]
    if len(store["users"]) != before:
        _save(store)
        return True
    return False
