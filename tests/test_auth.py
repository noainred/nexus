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

    blocked = client.get("/api/instances")
    assert blocked.status_code == 401
    # The manager auth gate is flagged so the SPA can tell it apart from an
    # upstream Nexus 401 (which must NOT re-open the login overlay).
    assert blocked.json().get("auth_required") is True

    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    ok = client.post("/api/login", json={"password": "pw123"})
    assert ok.status_code == 200 and "nm_session" in ok.cookies

    assert client.get("/api/instances").status_code == 200  # cookie kept by TestClient


def test_public_read_endpoints_open_when_auth_required(client, monkeypatch, tmp_path):
    """With a password set, status/monitoring GETs stay open; sensitive
    reads and all writes still require login."""
    s = Settings(admin_password="pw123", audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)

    # Public status/monitoring reads: NOT 401 (no instances configured, but the
    # auth gate must let them through — they return 200 with empty data).
    for path in (
        "/api/status",
        "/api/topology",
        "/api/proxy-status",
        "/api/metrics",
        "/api/blobstores",
        "/api/disk-forecast",
        "/api/ping-history",
        "/api/alerts",
        "/api/release-notes",
        "/api/instances/group-order",
    ):
        assert client.get(path).status_code != 401, path

    # Sensitive reads stay protected.
    assert client.get("/api/instances").status_code == 401
    assert client.get("/api/instances/export").status_code == 401
    assert client.get("/api/audit").status_code == 401
    assert client.get("/api/security").status_code == 401
    assert client.get("/api/search?q=x").status_code == 401
    # A look-alike under a public prefix must NOT be treated as public.
    assert client.get(
        "/api/proxy-status/diagnose?instance_id=a&repository=b"
    ).status_code == 401

    # All writes stay protected even on a public path.
    assert client.put("/api/sync-jobs", json={"jobs": []}).status_code == 401


@pytest.mark.parametrize("stored", ["pw123", " pw123 ", "pw123\n", '"pw123"', "'pw123'"])
def test_login_tolerates_env_whitespace_and_quotes(client, monkeypatch, tmp_path, stored):
    """A password configured with stray whitespace/newline/quotes in .env must
    still accept the clean password (common deployment footgun)."""
    s = Settings(admin_password=stored, audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)
    assert client.post("/api/login", json={"password": "pw123"}).status_code == 200


def test_viewer_cannot_export_credentials(client, monkeypatch, tmp_path):
    """읽기 전용 viewer는 자격증명이 담긴 export/백업 다운로드에 접근 불가(403),
    일반 조회는 가능(200), 관리자는 export 200."""
    import app.userstore as us
    from datetime import datetime, timezone
    from app.routers import auth as auth_mod

    s = Settings(admin_password="pw123", audit_file=str(tmp_path / "audit.log"),
                 accounts_file=str(tmp_path / "accounts.json"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)
    monkeypatch.setattr(us, "get_settings", lambda: s)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    us.create("bob", "viewerpw", "viewer", ts)

    # viewer 세션 쿠키
    client.cookies.set(auth_mod.COOKIE, auth_mod.make_user_token("bob", "viewer"))
    assert client.get("/api/instances").status_code == 200        # 조회는 허용
    assert client.get("/api/instances/export").status_code == 403  # 자격증명 export 차단
    client.cookies.clear()

    # 관리자는 허용
    assert client.post("/api/login", json={"password": "pw123"}).status_code == 200
    assert client.get("/api/instances/export").status_code == 200
    client.cookies.clear()


def test_audit_records_writes(client, monkeypatch, tmp_path):
    s = Settings(audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)

    client.put("/api/sync-jobs", json={"jobs": []})  # a write op
    items = client.get("/api/audit").json()
    assert items and items[0]["method"] == "PUT"
    assert items[0]["path"] == "/api/sync-jobs"
    assert items[0]["status"] == 200
