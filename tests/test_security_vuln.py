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


# -- Outbound TLS verification honors settings.verify_tls -------------------

class _CapClient:
    """Fake httpx.AsyncClient that records its kwargs and refuses connections,
    so we can assert which `verify` value the outbound call used."""
    captured: dict = {}

    def __init__(self, **kw):
        import httpx
        _CapClient.captured = kw
        self._err = httpx.ConnectError("blocked in test")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *a, **k):
        raise self._err

    async def post(self, *a, **k):
        raise self._err


def test_alert_manager_lock_not_bound_at_import(monkeypatch):
    """AlertManager를 (import처럼) 실행 루프 밖에서 생성한 뒤 asyncio.run 안에서
    경합(동시 evaluate)시켜도 'Future attached to a different loop'로 터지지 않아야
    한다 — 락은 import 시점이 아니라 실행 루프에서 지연 생성돼야 한다."""
    import asyncio
    import app.alerts as alerts_mod

    mgr = alerts_mod.AlertManager()   # 실행 루프 없는 시점(모듈 import와 동일)

    async def slow_current(registry, settings):
        await asyncio.sleep(0.05)     # 락 보유 중 await → 두 번째 호출이 대기(slow path)
        return []

    monkeypatch.setattr(alerts_mod, "_current_alerts", slow_current)
    settings = Settings()

    async def contend():
        # 동시 두 호출: 한쪽이 락을 잡고 sleep하는 동안 다른 쪽이 락을 기다린다.
        return await asyncio.gather(
            mgr.evaluate(None, settings), mgr.evaluate(None, settings)
        )

    asyncio.run(contend())   # RuntimeError 없이 완료돼야 통과


@pytest.mark.parametrize("verify_tls", [True, False])
def test_alert_send_honors_verify_tls(monkeypatch, verify_tls):
    import asyncio
    import app.alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "get_settings", lambda: Settings(verify_tls=verify_tls))
    monkeypatch.setattr(alerts_mod.httpx, "AsyncClient", _CapClient)
    asyncio.run(alerts_mod._send("http://hook.example/x", "hi"))
    assert _CapClient.captured.get("verify") is verify_tls


@pytest.mark.parametrize("verify_tls", [True, False])
def test_topology_probe_honors_verify_tls(monkeypatch, verify_tls):
    import asyncio
    import app.routers.topology as topo_mod
    monkeypatch.setattr(topo_mod, "get_settings", lambda: Settings(verify_tls=verify_tls))
    monkeypatch.setattr(topo_mod.httpx, "AsyncClient", _CapClient)
    assert asyncio.run(topo_mod._probe("https://x.example/", 2.0)) is False
    assert _CapClient.captured.get("verify") is verify_tls


@pytest.mark.parametrize("verify_tls", [True, False])
def test_update_edge_check_honors_verify_tls(monkeypatch, verify_tls):
    import asyncio
    import app.routers.update as upd_mod
    monkeypatch.setattr(upd_mod, "get_settings", lambda: Settings(verify_tls=verify_tls))
    monkeypatch.setattr(upd_mod.httpx, "AsyncClient", _CapClient)
    asyncio.run(upd_mod._check_edges(["http://edge.example/"], "1.0.0"))
    assert _CapClient.captured.get("verify") is verify_tls
