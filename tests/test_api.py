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


def test_release_notes(http_client):
    from app import __version__

    resp = http_client.get("/api/release-notes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == __version__
    # Newest entry first and matches the app version.
    assert body["notes"][0]["version"] == __version__
    assert body["notes"][0]["changes"]
    assert body["notes"][0]["changes"][0]["type"] in {"added", "changed", "removed"}


def test_list_instances_hides_credentials(http_client):
    resp = http_client.get("/api/instances")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["id"] == "test"
    assert "password" not in data[0]
    assert data[0]["use_in_monitoring"] is True
    assert data[0]["use_in_comparison"] is True


@respx.mock
def test_instance_test_connection_ok(http_client):
    respx.get("https://probe.test/service/rest/v1/status").mock(
        return_value=httpx.Response(200)
    )
    respx.get("https://probe.test/service/rest/v1/status/check").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get("https://probe.test/service/rest/v1/repositories").mock(
        return_value=httpx.Response(200, json=[{"name": "r", "format": "raw", "type": "hosted"}])
    )
    resp = http_client.post(
        "/api/instances/test",
        json={"base_url": "https://probe.test", "username": "admin", "password": "p"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reachable"] is True
    assert body["repository_count"] == 1


@respx.mock
def test_instance_test_connection_fails(http_client):
    respx.get("https://down.test/service/rest/v1/status").mock(
        side_effect=httpx.ConnectError("nope")
    )
    resp = http_client.post(
        "/api/instances/test", json={"base_url": "https://down.test"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reachable"] is False
    assert body["error"]


def test_set_reference_is_exclusive(http_client, monkeypatch):
    monkeypatch.setattr(deps, "save_instances", lambda *a, **k: None)
    deps.registry._instances["core"] = InstanceConfig(
        id="core", name="Core", base_url="http://core.test",
        username="admin", password="secret",
    )
    # Designate "test" as reference.
    r1 = http_client.post("/api/instances/test/reference")
    assert r1.status_code == 200
    flags = {i["id"]: i["is_reference"] for i in r1.json()}
    assert flags == {"test": True, "core": False}

    # Designating "core" moves the reference (exclusive).
    r2 = http_client.post("/api/instances/core/reference")
    flags = {i["id"]: i["is_reference"] for i in r2.json()}
    assert flags == {"test": False, "core": True}

    # Toggling the current reference clears it.
    r3 = http_client.post("/api/instances/core/reference")
    flags = {i["id"]: i["is_reference"] for i in r3.json()}
    assert flags == {"test": False, "core": False}


def test_export_and_import(http_client, monkeypatch):
    monkeypatch.setattr(deps, "save_instances", lambda *a, **k: None)

    # Export returns YAML including the password (a full backup).
    exp = http_client.get("/api/instances/export")
    assert exp.status_code == 200
    assert "attachment" in exp.headers["content-disposition"]
    assert "password: secret" in exp.text

    # Import (replace) swaps the whole list.
    new_yaml = (
        "instances:\n"
        "  - id: imported\n"
        "    name: Imported\n"
        "    base_url: http://imp:8081\n"
        "    username: admin\n"
        "    password: pw\n"
    )
    imp = http_client.post(
        "/api/instances/import?mode=replace",
        content=new_yaml,
        headers={"Content-Type": "application/x-yaml"},
    )
    assert imp.status_code == 200
    ids = {i["id"] for i in imp.json()}
    assert ids == {"imported"}
    assert "imported" in deps.registry._instances

    # Invalid payload -> 400
    bad = http_client.post("/api/instances/import", content="not: [valid")
    assert bad.status_code == 400


def test_ping_config(http_client, monkeypatch):
    monkeypatch.setattr(deps, "save_instances", lambda *a, **k: None)
    r = http_client.get("/api/instances/ping-config")
    body = r.json()
    assert set(body) == {"interval", "warn_pct", "crit_pct"}

    r2 = http_client.put(
        "/api/instances/ping-config",
        json={"interval": 5, "warn_pct": 30, "crit_pct": 10},
    )
    cfg = r2.json()
    assert cfg["interval"] == 10.0          # clamped to >= 10
    assert cfg["warn_pct"] == 30.0
    assert cfg["crit_pct"] == 30.0          # raised to >= warn
    assert deps.registry.ping_interval() == 10.0


def test_compare_fields(http_client, monkeypatch):
    monkeypatch.setattr(deps, "save_instances", lambda *a, **k: None)
    deps.registry._compare_fields = ["format", "type", "remote_url"]

    r = http_client.get("/api/instances/compare-fields")
    assert r.json()["fields"] == ["format", "type", "remote_url"]

    # Invalid fields are filtered out; valid ones kept.
    r2 = http_client.put(
        "/api/instances/compare-fields",
        json={"fields": ["format", "online", "bogus"]},
    )
    assert r2.json()["fields"] == ["format", "online"]
    assert deps.registry._compare_fields == ["format", "online"]


def test_group_order(http_client, monkeypatch):
    monkeypatch.setattr(deps, "save_instances", lambda *a, **k: None)
    deps.registry._instances["test"].group = "DMZ"
    deps.registry._instances["oc"] = InstanceConfig(
        id="oc", name="OC", base_url="http://oc", username="a", password="p", group="OC2"
    )
    deps.registry._group_order = []

    # Default: present groups (sorted) when no explicit order saved.
    r = http_client.get("/api/instances/group-order")
    assert set(r.json()["groups"]) == {"DMZ", "OC2"}

    # Set an explicit order; it is returned and persisted.
    r2 = http_client.put("/api/instances/group-order", json={"groups": ["OC2", "DMZ"]})
    assert r2.status_code == 200
    assert r2.json()["groups"] == ["OC2", "DMZ"]
    assert deps.registry._group_order == ["OC2", "DMZ"]


def test_instance_crud(http_client, monkeypatch, tmp_path):
    # Avoid touching a real instances.yaml during the test.
    monkeypatch.setattr(deps, "save_instances", lambda *a, **k: None)

    # Create
    resp = http_client.post(
        "/api/instances",
        json={
            "id": "new1",
            "name": "New One",
            "base_url": "http://new.test:8081",
            "username": "admin",
            "password": "pw",
            "use_in_monitoring": False,
            "use_in_comparison": True,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["use_in_monitoring"] is False
    assert "new1" in deps.registry._instances

    # Duplicate id -> 409
    dup = http_client.post(
        "/api/instances",
        json={"id": "new1", "name": "x", "base_url": "http://x", "password": "p"},
    )
    assert dup.status_code == 409

    # Update keeps password when blank
    upd = http_client.put(
        "/api/instances/new1",
        json={
            "name": "Renamed",
            "base_url": "http://new.test:8081",
            "username": "admin",
            "password": "",
            "use_in_monitoring": True,
            "use_in_comparison": True,
        },
    )
    assert upd.status_code == 200
    assert deps.registry._instances["new1"].name == "Renamed"
    assert deps.registry._instances["new1"].password == "pw"  # preserved

    # Delete
    dele = http_client.delete("/api/instances/new1")
    assert dele.status_code == 204
    assert "new1" not in deps.registry._instances


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
def test_metrics_parses_heap_and_threads(http_client):
    respx.get("https://nexus.test/service/rest/metrics/data").mock(
        return_value=httpx.Response(
            200,
            json={
                "gauges": {
                    "jvm.memory.heap.used": {"value": 800},
                    "jvm.memory.heap.max": {"value": 1000},
                    "jvm.memory.heap.usage": {"value": 0.8},
                    "jvm.threads.count": {"value": 142},
                    "jvm.attribute.uptime": {"value": 90000000},
                }
            },
        )
    )
    resp = http_client.get("/api/metrics")
    assert resp.status_code == 200
    m = resp.json()[0]
    assert m["heap_used_bytes"] == 800
    assert m["heap_usage_pct"] == 80.0
    assert m["thread_count"] == 142


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
def test_downloads_batch_scans_only_given_repos(http_client):
    respx.get(f"{API}/assets", params={"repository": "r1"}).mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": "a", "path": "p", "fileSize": 10,
                              "lastDownloaded": "2026-05-01T00:00:00.000+00:00"}],
                  "continuationToken": None},
        )
    )
    respx.get(f"{API}/assets", params={"repository": "r2"}).mock(
        return_value=httpx.Response(
            200, json={"items": [], "continuationToken": None}
        )
    )
    resp = http_client.get(
        "/api/instances/test/downloads-batch?repository=r1&repository=r2"
    )
    assert resp.status_code == 200
    body = {r["repository"]: r for r in resp.json()}
    assert body["r1"]["total_assets"] == 1
    assert body["r1"]["downloaded_assets"] == 1
    assert body["r2"]["total_assets"] == 0


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


def test_ping_query_colors(tmp_path):
    from datetime import datetime, timedelta, timezone
    from app import pingmon

    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    f = tmp_path / "ping.csv"
    # baseline (median) of [10,10,12,20,40] = 12; distinct hourly timestamps.
    rows = [
        f"{(now - timedelta(hours=i)).strftime(fmt)},a,{v}"
        for i, v in enumerate([10, 10, 12, 20, 40])
    ]
    f.write_text("\n".join(rows) + "\n", encoding="utf-8")

    class S:
        ping_file = str(f)

    out = pingmon.query(1, {"a": "A"}, settings=S())
    s = out["series"][0]
    assert s["baseline"] == 12.0
    colors = {p["v"]: p["color"] for p in s["points"]}
    assert colors.get(40.0) == "crit"   # 3.3x baseline
    assert colors.get(20.0) == "crit"   # 1.67x baseline
    assert colors.get(10.0) == "ok"


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


@respx.mock
def test_content_compare_detects_missing_component(http_client):
    deps.registry._instances["core"] = InstanceConfig(
        id="core", name="Core", base_url="https://core.test",
        username="admin", password="secret", verify_tls=True,
    )
    # test has 2 components; core is missing one of them.
    respx.get(f"{API}/components").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": "1", "group": "g", "name": "a", "version": "1.0"},
                    {"id": "2", "group": "g", "name": "b", "version": "1.0"},
                ],
                "continuationToken": None,
            },
        )
    )
    respx.get("https://core.test/service/rest/v1/components").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{"id": "9", "group": "g", "name": "a", "version": "1.0"}],
                "continuationToken": None,
            },
        )
    )
    resp = http_client.get("/api/content-compare?repository=raw-hosted")
    assert resp.status_code == 200
    body = resp.json()
    by_key = {r["key"]: r for r in body["rows"]}
    assert by_key["g:a:1.0"]["consistent"] is True
    assert by_key["g:b:1.0"]["consistent"] is False
    assert by_key["g:b:1.0"]["present"]["core"] is False


@respx.mock
def test_alerts_fire_on_node_down(http_client):
    # test instance is unreachable -> a critical down alert.
    respx.get(f"{API}/status").mock(side_effect=httpx.ConnectError("down"))
    respx.get(f"{API}/repositories").mock(side_effect=httpx.ConnectError("down"))
    respx.get(f"{API}/blobstores").mock(side_effect=httpx.ConnectError("down"))
    respx.get("https://nexus.test/service/rest/metrics/data").mock(
        side_effect=httpx.ConnectError("down")
    )
    respx.get("https://nexus.test/service/metrics/data").mock(
        side_effect=httpx.ConnectError("down")
    )
    resp = http_client.get("/api/alerts?refresh=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["webhook_configured"] is False
    assert any(a["key"] == "down:test" and a["severity"] == "critical" for a in body["alerts"])


@respx.mock
def test_topology_internal_link_and_broken(http_client):
    # core is a managed node; test proxies it. core is unreachable -> broken.
    deps.registry._instances["core"] = InstanceConfig(
        id="core", name="Core", base_url="http://core.test:8081",
        username="admin", password="secret", verify_tls=True,
    )
    respx.get(f"{API}/repositories").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "maven-proxy",
                    "format": "maven2",
                    "type": "proxy",
                    "attributes": {"proxy": {"remoteUrl": "http://core.test:8081/repository/maven/"}},
                },
                {
                    "name": "pypi",
                    "format": "pypi",
                    "type": "proxy",
                    "attributes": {"proxy": {"remoteUrl": "https://pypi.org/simple"}},
                },
            ],
        )
    )
    respx.get("http://core.test:8081/service/rest/v1/repositories").mock(
        side_effect=httpx.ConnectError("down")
    )
    resp = http_client.get("/api/topology")
    assert resp.status_code == 200
    body = resp.json()
    by_id = {n["id"]: n for n in body["nodes"]}
    links = {p["repository"]: p for p in by_id["test"]["proxies"]}
    assert links["maven-proxy"]["internal"] is True
    assert links["maven-proxy"]["target_id"] == "core"
    assert links["maven-proxy"]["broken"] is True       # core is down
    assert links["pypi"]["internal"] is False            # external upstream
    assert body["broken_links"] >= 1


@respx.mock
def test_security_check(http_client):
    respx.get(f"{API}/security/anonymous").mock(
        return_value=httpx.Response(200, json={"enabled": True, "userId": "anonymous"})
    )
    respx.get(f"{API}/security/users").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"userId": "admin", "status": "active", "roles": ["nx-admin"]},
                {"userId": "dev", "status": "active", "roles": ["nx-anonymous"]},
            ],
        )
    )
    resp = http_client.get("/api/security")
    assert resp.status_code == 200
    s = resp.json()[0]
    assert s["anonymous_enabled"] is True
    assert s["admin_active"] is True
    assert s["admin_users"] == ["admin"]
    assert s["user_count"] == 2


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
