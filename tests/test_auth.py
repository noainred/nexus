"""Tests for manager login (optional admin password) and the audit log."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
from app.config import Settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_disabled_by_default(client):
    st = client.get("/api/auth-status").json()
    assert st == {"required": False, "authenticated": True}
    assert client.get("/api/instances").status_code == 200


def test_auth_required_blocks_and_login_unlocks(client, monkeypatch, tmp_path):
    s = Settings(admin_password="pw123", audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)

    assert client.get("/api/instances").status_code == 401
    st = client.get("/api/auth-status").json()
    assert st["required"] is True and st["authenticated"] is False

    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    ok = client.post("/api/login", json={"password": "pw123"})
    assert ok.status_code == 200 and "nm_session" in ok.cookies

    assert client.get("/api/instances").status_code == 200  # cookie kept by TestClient


def test_audit_records_writes(client, monkeypatch, tmp_path):
    s = Settings(audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)

    client.put("/api/sync-jobs", json={"jobs": []})  # a write op
    items = client.get("/api/audit").json()
    assert items and items[0]["method"] == "PUT"
    assert items[0]["path"] == "/api/sync-jobs"
    assert items[0]["status"] == 200
