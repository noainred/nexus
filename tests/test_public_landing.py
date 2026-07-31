"""Guard tests for the public status landing (Nexus Service Dashboard):
the container is served and the SPA wires it to the public data endpoints."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
from app.config import Settings
from app.main import app

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


@pytest.fixture
def client():
    return TestClient(app)


def test_index_has_landing_container(client):
    html = client.get("/").text
    assert 'id="public-landing"' in html


def test_appjs_wires_landing():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function renderPublicLanding" in js
    # Landing pulls live data from the public read endpoints.
    assert "/api/topology" in js and "/api/status" in js
    # Login inside the landing posts to the real login endpoint.
    assert "/api/login" in js


def test_ping_page_public_no_login(client, monkeypatch):
    """The standalone /ping page and its data endpoint must be reachable with
    no login even when auth is required."""
    s = Settings(admin_password="boss")
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)
    page = client.get("/ping")
    assert page.status_code == 200
    assert 'id="infra-charts"' in page.text and "/static/ping.js" in page.text
    assert client.get("/static/ping.js").status_code == 200
    assert client.get("/api/ping-history?days=1").status_code == 200


def test_ping_js_reads_public_endpoint():
    js = (STATIC / "ping.js").read_text(encoding="utf-8")
    assert "/api/ping-history" in js


def test_landing_endpoints_public_when_auth_required(client, monkeypatch):
    """When auth is required and the visitor is anonymous, the endpoints the
    landing reads must stay open (else the public page can't render)."""
    s = Settings(admin_password="boss")
    monkeypatch.setattr(main_mod, "get_settings", lambda: s)
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: s)
    for path in ("/api/auth-status", "/api/me", "/api/topology", "/api/status", "/api/summary"):
        assert client.get(path).status_code == 200, path
    # And a sensitive endpoint still requires login.
    assert client.get("/api/instances").status_code == 401
