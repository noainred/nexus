"""Tests for CVE version scanning, session-token expiry, login rate-limit,
and security response headers (delivery hardening batch)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
import app.routers.auth as auth_mod
from app.config import Settings
from app.main import app
from app.routers.auth import make_token, verify_token
from app.vulndb import parse_version, scan_version


@pytest.fixture
def client():
    return TestClient(app)


# -- CVE version scan -------------------------------------------------------

def test_parse_version_extracts_triple():
    assert parse_version("3.68.0-04 (OSS)") == (3, 68, 0)
    assert parse_version("Nexus/3.73.0") == (3, 73, 0)
    assert parse_version(None) is None
    assert parse_version("no-version-here") is None


def test_scan_flags_vulnerable_and_clears_when_patched():
    assert [v["id"] for v in scan_version("3.68.0")] == ["CVE-2024-4956", "CVE-2024-5764"]
    # Path-traversal CVE fixed in 3.68.1; encryption CVE still open until 3.73.0.
    assert [v["id"] for v in scan_version("3.68.1")] == ["CVE-2024-5764"]
    assert scan_version("3.73.0") == []
    assert [v["id"] for v in scan_version("3.83.0")] == ["CVE-2025-13488"]
    assert scan_version("3.85.0") == []


def test_unknown_version_is_not_scanned_not_safe():
    # No version => empty list, never a "safe" claim.
    assert scan_version(None) == []
    assert scan_version("") == []


# -- Session token expiry ---------------------------------------------------

def test_token_roundtrip_and_password_binding():
    tok = make_token("pw123")
    assert verify_token("pw123", tok) is True
    assert verify_token("other", tok) is False        # password change invalidates
    assert verify_token("pw123", "garbage") is False


def test_expired_token_rejected():
    assert verify_token("pw123", make_token("pw123", ttl=-1)) is False


# -- Login rate-limit -------------------------------------------------------

def test_login_rate_limit_locks_after_repeated_failures(client, monkeypatch, tmp_path):
    s = Settings(admin_password="pw123", audit_file=str(tmp_path / "audit.log"))
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)
    auth_mod._LOGIN_FAILS.clear()

    # Up to _RL_MAX wrong attempts return 401; the next is throttled with 429.
    for _ in range(auth_mod._RL_MAX):
        assert client.post("/api/login", json={"password": "bad"}).status_code == 401
    assert client.post("/api/login", json={"password": "bad"}).status_code == 429
    # Even the correct password is refused while locked out.
    assert client.post("/api/login", json={"password": "pw123"}).status_code == 429
    auth_mod._LOGIN_FAILS.clear()


def test_security_headers_present(client):
    r = client.get("/healthz")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "frame-ancestors 'none'" in r.headers.get("Content-Security-Policy", "")
