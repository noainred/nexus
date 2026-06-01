"""API-level tests using FastAPI's TestClient with a stubbed registry."""
from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import deps
from app.config import InstanceConfig
from app.main import app

API = "https://nexus.test/service/rest/v1"


@pytest.fixture(autouse=True)
def stub_registry():
    """Replace the module-level registry with a single test instance."""
    original = deps.registry._instances
    deps.registry._instances = {
        "test": InstanceConfig(
            id="test",
            name="Test Nexus",
            base_url="https://nexus.test",
            username="admin",
            password="secret",
            verify_tls=True,
        )
    }
    yield
    deps.registry._instances = original


@pytest.fixture
def http_client():
    return TestClient(app)


def test_healthz(http_client):
    resp = http_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_instances_hides_credentials(http_client):
    resp = http_client.get("/api/instances")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["id"] == "test"
    assert "password" not in data[0]


@respx.mock
def test_repositories_endpoint(http_client):
    respx.get(f"{API}/repositories").mock(
        return_value=httpx.Response(
            200, json=[{"name": "raw-hosted", "format": "raw", "type": "hosted"}]
        )
    )
    resp = http_client.get("/api/instances/test/repositories")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "raw-hosted"


@respx.mock
def test_repositories_upstream_error_propagates_status(http_client):
    respx.get(f"{API}/repositories").mock(return_value=httpx.Response(401, text="auth"))
    resp = http_client.get("/api/instances/test/repositories")
    assert resp.status_code == 401


def test_unknown_instance_404(http_client):
    resp = http_client.get("/api/instances/nope/repositories")
    assert resp.status_code == 404


@respx.mock
def test_cleanup_requires_criteria(http_client):
    resp = http_client.post(
        "/api/instances/test/cleanup-policies",
        json={"name": "p1", "format": "maven2"},
    )
    assert resp.status_code == 400


@respx.mock
def test_cleanup_create(http_client):
    respx.post(f"{API}/cleanup-policies").mock(return_value=httpx.Response(204))
    resp = http_client.post(
        "/api/instances/test/cleanup-policies",
        json={
            "name": "p1",
            "format": "maven2",
            "criteria_last_blob_updated": 30,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["criteria"] == {"lastBlobUpdated": 30}


@respx.mock
def test_matrix_endpoint_flags_drift(http_client):
    # Two instances, same repo name, different upstream URL -> drift.
    deps.registry._instances["core"] = InstanceConfig(
        id="core",
        name="Core",
        base_url="https://core.test",
        username="admin",
        password="secret",
        verify_tls=True,
    )
    respx.get(f"{API}/repositories").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "pypi",
                    "format": "pypi",
                    "type": "proxy",
                    "attributes": {"proxy": {"remoteUrl": "https://pypi.org/simple"}},
                }
            ],
        )
    )
    respx.get("https://core.test/service/rest/v1/repositories").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "pypi",
                    "format": "pypi",
                    "type": "proxy",
                    "attributes": {"proxy": {"remoteUrl": "https://mirror.local/simple"}},
                }
            ],
        )
    )
    resp = http_client.get("/api/matrix")
    assert resp.status_code == 200
    body = resp.json()
    assert [c["id"] for c in body["columns"]] == ["test", "core"]
    row = body["rows"][0]
    assert row["repository"] == "pypi"
    assert row["status"] == "drift"


@respx.mock
def test_matrix_endpoint_marks_unreachable_column(http_client):
    respx.get(f"{API}/repositories").mock(side_effect=httpx.ConnectError("down"))
    resp = http_client.get("/api/matrix")
    assert resp.status_code == 200
    body = resp.json()
    col = body["columns"][0]
    assert col["reachable"] is False
    assert col["error"]


@respx.mock
def test_status_endpoint_handles_unreachable(http_client):
    respx.get(f"{API}/status").mock(side_effect=httpx.ConnectError("down"))
    resp = http_client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["reachable"] is False
    assert body[0]["error"]
