"""Manager id/pw accounts: hashing, coexist login, roles (admin/viewer),
account CRUD, and self-service password change."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
import app.routers.auth as auth_mod
from app import userstore
from app.config import Settings
from app.main import app


@pytest.fixture
def env(tmp_path, monkeypatch):
    store = tmp_path / "accounts.json"
    s = Settings(admin_password="boss", accounts_file=str(store),
                 audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)
    monkeypatch.setattr("app.routers.musers.get_settings", lambda: s)
    monkeypatch.setattr(userstore, "_store_path", lambda: store)
    auth_mod._LOGIN_FAILS.clear()
    return s


@pytest.fixture
def client():
    return TestClient(app)


# -- userstore unit ---------------------------------------------------------

def test_userstore_hash_and_roles(env):
    userstore.create("Alice", "pw12345", "admin", "t")
    assert userstore.verify("alice", "pw12345") == "admin"     # case-insensitive id
    assert userstore.verify("alice", "wrong") is None
    # Password is never stored in the clear.
    raw = env.accounts_file
    import pathlib
    assert "pw12345" not in pathlib.Path(raw).read_text()
    userstore.update("alice", "t2", role="viewer")
    assert userstore.verify("alice", "pw12345") == "viewer"
    assert userstore.delete("alice") is True
    assert userstore.verify("alice", "pw12345") is None


def test_userstore_rejects_bad_input(env):
    with pytest.raises(ValueError):
        userstore.create("ab", "pw12345", "admin", "t")     # id too short
    with pytest.raises(ValueError):
        userstore.create("alice", "x", "admin", "t")        # pw too short
    with pytest.raises(ValueError):
        userstore.create("alice", "pw12345", "root", "t")   # bad role


# -- login coexistence ------------------------------------------------------

def test_bootstrap_admin_still_works(env, client):
    r = client.post("/api/login", json={"password": "boss"})
    assert r.status_code == 200 and r.json()["role"] == "admin" and r.json()["bootstrap"] is True
    assert client.get("/api/instances").status_code == 200  # admin can read/manage


def test_named_admin_and_viewer_login(env, client):
    userstore.create("adm", "adminpw", "admin", "t")
    userstore.create("viewer1", "viewpw", "viewer", "t")

    # viewer: can read, cannot write, can change own password
    assert client.post("/api/login", json={"username": "viewer1", "password": "viewpw"}).status_code == 200
    assert client.get("/api/instances").status_code == 200
    assert client.put("/api/instances/ping-config",
                      json={"interval": 30, "warn_pct": 20, "crit_pct": 50}).status_code == 403
    assert client.get("/api/manager-users").status_code == 403           # admin-only
    assert client.post("/api/me/password",
                       json={"old_password": "viewpw", "new_password": "newpw2"}).status_code == 200
    assert client.get("/api/me").json()["role"] == "viewer"


def test_named_admin_can_manage_accounts(env, client):
    userstore.create("adm", "adminpw", "admin", "t")
    assert client.post("/api/login", json={"username": "adm", "password": "adminpw"}).status_code == 200
    # create + list + role change + delete
    assert client.post("/api/manager-users",
                       json={"username": "bob", "password": "bobpw1", "role": "viewer"}).status_code == 200
    names = [u["username"] for u in client.get("/api/manager-users").json()["users"]]
    assert "bob" in names and "adm" in names
    assert client.put("/api/manager-users/bob", json={"role": "admin"}).status_code == 200
    assert client.delete("/api/manager-users/bob").status_code == 200


def test_auth_enabled_by_accounts_without_password(tmp_path, monkeypatch, client):
    """With no admin_password but a named account, auth is still required."""
    store = tmp_path / "accounts.json"
    s = Settings(admin_password="", accounts_file=str(store),
                 audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)
    monkeypatch.setattr("app.routers.musers.get_settings", lambda: s)
    monkeypatch.setattr(userstore, "_store_path", lambda: store)
    auth_mod._LOGIN_FAILS.clear()
    userstore.create("solo", "solopw", "admin", "t")

    assert client.get("/api/auth-status").json()["required"] is True
    assert client.get("/api/instances").status_code == 401          # anonymous blocked
    assert client.post("/api/login", json={"username": "solo", "password": "solopw"}).status_code == 200
    assert client.get("/api/instances").status_code == 200


def test_me_reachable_anonymously(env, client):
    """/api/me must answer without a login (so the SPA can render public mode
    without wrongly popping the login overlay)."""
    r = client.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is False and body.get("auth_required") is None


def test_bootstrap_admin_cannot_change_env_password(env, client):
    client.post("/api/login", json={"password": "boss"})
    r = client.post("/api/me/password", json={"old_password": "boss", "new_password": "x2345"})
    assert r.status_code == 400  # env password isn't managed here
