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
def test_blobstores_all_aggregates_per_instance(http_client):
    respx.get(f"{API}/blobstores").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "default",
                    "type": "File",
                    "totalSizeInBytes": 100,
                    "availableSpaceInBytes": 900,
                    "blobCount": 5,
                },
                {
                    "name": "extra",
                    "type": "File",
                    "totalSizeInBytes": 50,
                    "blobCount": 2,
                },
            ],
        )
    )
    resp = http_client.get("/api/blobstores")
    assert resp.status_code == 200
    body = resp.json()
    site = body[0]
    assert site["id"] == "test"
    assert site["reachable"] is True
    assert len(site["blobstores"]) == 2
    assert site["total_size_bytes"] == 150  # summed across blob stores
    assert site["blob_count"] == 7


@respx.mock
def test_blobstores_all_marks_unreachable(http_client):
    respx.get(f"{API}/blobstores").mock(side_effect=httpx.ConnectError("down"))
    resp = http_client.get("/api/blobstores")
    assert resp.status_code == 200
    site = resp.json()[0]
    assert site["reachable"] is False
    assert site["error"]
    assert site["blobstores"] == []


@respx.mock
def test_repository_detail_diff(http_client):
    deps.registry._instances["core"] = InstanceConfig(
        id="core", name="Core", base_url="https://core.test",
        username="admin", password="secret", verify_tls=True,
    )
    # Both instances list the repo so format/type can be resolved.
    repo_list = [{"name": "epel", "format": "yum", "type": "proxy"}]
    respx.get(f"{API}/repositories").mock(return_value=httpx.Response(200, json=repo_list))
    respx.get("https://core.test/service/rest/v1/repositories").mock(
        return_value=httpx.Response(200, json=repo_list)
    )
    # Full configs differ on proxy.remoteUrl only.
    respx.get(f"{API}/repositories/yum/proxy/epel").mock(
        return_value=httpx.Response(
            200, json={"name": "epel", "online": True, "proxy": {"remoteUrl": "https://a"}}
        )
    )
    respx.get("https://core.test/service/rest/v1/repositories/yum/proxy/epel").mock(
        return_value=httpx.Response(
            200, json={"name": "epel", "online": True, "proxy": {"remoteUrl": "https://b"}}
        )
    )
    resp = http_client.get("/api/repository-detail?repository=epel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["repository"] == "epel"
    by_key = {f["key"]: f for f in body["fields"]}
    assert by_key["proxy.remoteUrl"]["differs"] is True
    assert by_key["online"]["differs"] is False


@respx.mock
def test_compare_two_repositories_across_instances(http_client):
    deps.registry._instances["core"] = InstanceConfig(
        id="core", name="Core", base_url="https://core.test",
        username="admin", password="secret", verify_tls=True,
    )
    # Left side: instance "test", repo "epel".
    respx.get(f"{API}/repositories").mock(
        return_value=httpx.Response(200, json=[{"name": "epel", "format": "yum", "type": "proxy"}])
    )
    respx.get(f"{API}/repositories/yum/proxy/epel").mock(
        return_value=httpx.Response(200, json={"online": True, "proxy": {"remoteUrl": "https://a"}})
    )
    # Right side: instance "core", a differently-named repo "epel-mirror".
    respx.get("https://core.test/service/rest/v1/repositories").mock(
        return_value=httpx.Response(200, json=[{"name": "epel-mirror", "format": "yum", "type": "proxy"}])
    )
    respx.get("https://core.test/service/rest/v1/repositories/yum/proxy/epel-mirror").mock(
        return_value=httpx.Response(200, json={"online": True, "proxy": {"remoteUrl": "https://b"}})
    )
    resp = http_client.get(
        "/api/compare?left_instance=test&left_repo=epel"
        "&right_instance=core&right_repo=epel-mirror"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [c["id"] for c in body["columns"]] == ["left", "right"]
    assert body["columns"][0]["name"] == "Test Nexus / epel"
    by_key = {f["key"]: f for f in body["fields"]}
    assert by_key["proxy.remoteUrl"]["differs"] is True
    assert by_key["online"]["differs"] is False


@respx.mock
def test_download_report_aggregates_assets(http_client):
    # Two assets: one downloaded, one never downloaded; single page.
    respx.get(f"{API}/assets").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "a1",
                        "path": "pkg/foo-1.0.tar.gz",
                        "contentType": "application/gzip",
                        "fileSize": 100,
                        "lastDownloaded": "2026-05-01T10:00:00.000+00:00",
                    },
                    {
                        "id": "a2",
                        "path": "pkg/bar-2.0.tar.gz",
                        "fileSize": 50,
                        "lastDownloaded": None,
                    },
                ],
                "continuationToken": None,
            },
        )
    )
    resp = http_client.get("/api/instances/test/downloads?repository=raw-hosted")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_assets"] == 2
    assert body["downloaded_assets"] == 1
    assert body["total_size_bytes"] == 150
    assert body["downloaded_size_bytes"] == 100
    assert body["truncated"] is False
    assert len(body["items"]) == 1
    assert body["items"][0]["path"] == "pkg/foo-1.0.tar.gz"


@respx.mock
def test_download_report_follows_pagination(http_client):
    route = respx.get(f"{API}/assets")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "items": [
                    {"id": "a1", "path": "p1", "fileSize": 10,
                     "lastDownloaded": "2026-05-02T00:00:00.000+00:00"},
                ],
                "continuationToken": "next",
            },
        ),
        httpx.Response(
            200,
            json={
                "items": [
                    {"id": "a2", "path": "p2", "fileSize": 20,
                     "lastDownloaded": "2026-05-03T00:00:00.000+00:00"},
                ],
                "continuationToken": None,
            },
        ),
    ]
    resp = http_client.get("/api/instances/test/downloads?repository=raw-hosted")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_assets"] == 2
    assert body["downloaded_size_bytes"] == 30
    # Most-recent first.
    assert [i["path"] for i in body["items"]] == ["p2", "p1"]


@respx.mock
def test_downloads_summary_scans_all_non_group_repos(http_client):
    respx.get(f"{API}/repositories").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"name": "raw-hosted", "format": "raw", "type": "hosted"},
                {"name": "maven-public", "format": "maven2", "type": "group"},
            ],
        )
    )
    # Only the hosted repo should be scanned (group is skipped).
    respx.get(f"{API}/assets", params={"repository": "raw-hosted"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": "a1", "path": "p1", "fileSize": 100,
                     "lastDownloaded": "2026-05-01T00:00:00.000+00:00"},
                    {"id": "a2", "path": "p2", "fileSize": 50, "lastDownloaded": None},
                ],
                "continuationToken": None,
            },
        )
    )
    resp = http_client.get("/api/instances/test/downloads-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["repositories"]) == 1
    assert body["repositories"][0]["repository"] == "raw-hosted"
    assert body["total_assets"] == 2
    assert body["downloaded_assets"] == 1
    assert body["total_size_bytes"] == 150
    assert body["downloaded_size_bytes"] == 100


@respx.mock
def test_tasks_list_and_run(http_client):
    respx.get(f"{API}/tasks").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "t1",
                        "name": "Compact blob store",
                        "type": "blobstore.compact",
                        "currentState": "WAITING",
                        "lastRunResult": "OK",
                        "lastRun": "2026-05-01T00:00:00.000+00:00",
                    },
                    {
                        "id": "t2",
                        "name": "Cleanup",
                        "type": "repository.cleanup",
                        "currentState": "RUNNING",
                        "lastRunResult": None,
                    },
                ]
            },
        )
    )
    resp = http_client.get("/api/instances/test/tasks")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["runnable"] is True and body[0]["stoppable"] is False
    assert body[1]["stoppable"] is True and body[1]["runnable"] is False

    run = respx.post(f"{API}/tasks/t1/run").mock(return_value=httpx.Response(204))
    r = http_client.post("/api/instances/test/tasks/t1/run")
    assert r.status_code == 204
    assert run.called


def test_compare_unknown_instance_404(http_client):
    resp = http_client.get(
        "/api/compare?left_instance=nope&left_repo=a&right_instance=test&right_repo=b"
    )
    assert resp.status_code == 404


@respx.mock
def test_status_endpoint_handles_unreachable(http_client):
    respx.get(f"{API}/status").mock(side_effect=httpx.ConnectError("down"))
    resp = http_client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["reachable"] is False
    assert body[0]["error"]
