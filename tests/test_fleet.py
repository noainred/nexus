"""Tests for the fleet-operations features (sync jobs, backup, disk
forecast, DR audit, cleanup audit, proxy status board, search)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import deps
from app.config import InstanceConfig, Settings
from app.main import app

API = "https://nexus.test/service/rest/v1"
INTERNAL = "https://nexus.test/service/rest/internal/ui/repositories"


@pytest.fixture(autouse=True)
def stub_registry():
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


# -- scheduled sync jobs -----------------------------------------------------

def test_sync_jobs_roundtrip(http_client):
    try:
        r = http_client.put("/api/sync-jobs", json={"jobs": [{
            "source_id": "a", "target_id": "b",
            "repository": "maven-central", "time": "03:00", "enabled": True,
        }]})
        assert r.status_code == 200
        job = r.json()["jobs"][0]
        assert job["id"]  # id auto-generated
        assert http_client.get("/api/sync-jobs").json()["jobs"][0]["repository"] == "maven-central"
    finally:
        http_client.put("/api/sync-jobs", json={"jobs": []})


def test_sync_job_run_unknown_id(http_client):
    assert http_client.post("/api/sync-jobs/run?id=nope").status_code == 404


# -- config backup ------------------------------------------------------------

@respx.mock
def test_backup_run_and_download(http_client, tmp_path):
    # Any config-export GET may return an empty list; sections degrade
    # gracefully, so the per-server JSON is still written.
    respx.route(method="GET", host="nexus.test").mock(
        return_value=httpx.Response(200, json=[])
    )
    try:
        r = http_client.put("/api/backup-config", json={
            "enabled": False, "time": "02:00", "keep": 3, "path": str(tmp_path),
        })
        assert r.status_code == 200 and r.json()["path"] == str(tmp_path)

        run = http_client.post("/api/backup-run").json()
        assert run["ok"] == 1 and run["total"] == 1
        assert run["directory"].startswith(str(tmp_path))

        runs = http_client.get("/api/backups").json()
        assert len(runs) == 1 and runs[0]["files"]
        ts, name = runs[0]["timestamp"], runs[0]["files"][0]["name"]
        dl = http_client.get(f"/api/backups/{ts}/{name}")
        assert dl.status_code == 200 and "instance" in dl.json()
    finally:
        http_client.put("/api/backup-config", json={
            "enabled": False, "time": "02:00", "keep": 14, "path": "",
        })


def test_backup_download_rejects_traversal(http_client):
    assert http_client.get("/api/backups/..%2f..%2fetc/passwd.json").status_code == 404


# -- disk saturation forecast --------------------------------------------------

def test_disk_forecast_math(http_client, tmp_path, monkeypatch):
    csv = tmp_path / "disk.csv"
    now = datetime.now(timezone.utc)
    lines = []
    for d in range(10, -1, -1):
        ts = (now - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
        used = 100_000_000_000 + (10 - d) * 5_000_000_000  # +5 GB/day
        lines.append(f"{ts},test,default,{used},200000000000\n")
    csv.write_text("".join(lines))
    monkeypatch.setattr(
        "app.routers.infra.get_settings", lambda: Settings(disk_file=str(csv))
    )
    body = http_client.get("/api/disk-forecast").json()
    assert body["counts"]["crit"] == 1
    row = body["stores"][0]
    assert row["instance_name"] == "Test Nexus"
    assert row["pct"] == 75.0
    assert 4.5e9 < row["growth_per_day"] < 5.5e9
    assert 5 < row["days_to_90"] < 7


# -- DR audit ------------------------------------------------------------------

@respx.mock
def test_dr_audit_ok(http_client):
    recent = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
    respx.get(f"{API}/tasks").mock(return_value=httpx.Response(200, json={
        "items": [{"id": "t1", "name": "Export databases for backup",
                   "type": "db.backup", "currentState": "WAITING",
                   "lastRunResult": "OK", "lastRun": recent}],
    }))
    body = http_client.get("/api/dr-audit").json()
    assert body["counts"]["ok"] == 1
    assert body["servers"][0]["state"] == "ok"


@respx.mock
def test_dr_audit_missing_task_is_crit(http_client):
    respx.get(f"{API}/tasks").mock(return_value=httpx.Response(200, json={"items": []}))
    body = http_client.get("/api/dr-audit").json()
    assert body["servers"][0]["state"] == "crit"


@respx.mock
def test_dr_run_backup(http_client):
    respx.get(f"{API}/tasks").mock(return_value=httpx.Response(200, json={
        "items": [{"id": "t1", "name": "backup", "type": "db.backup",
                   "currentState": "WAITING"}],
    }))
    run = respx.post(f"{API}/tasks/t1/run").mock(return_value=httpx.Response(204))
    body = http_client.post("/api/dr-run-backup").json()
    assert body["servers"][0]["started"] == 1
    assert run.called


# -- cleanup audit --------------------------------------------------------------

@respx.mock
def test_cleanup_audit_flags_missing_compact(http_client):
    respx.get(f"{API}/cleanup-policies").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{API}/tasks").mock(return_value=httpx.Response(200, json={"items": []}))
    respx.get(f"{API}/blobstores").mock(return_value=httpx.Response(200, json=[
        {"name": "default", "type": "File"},
    ]))
    respx.get(f"{API}/repositorySettings").mock(return_value=httpx.Response(200, json=[
        {"name": "maven-central", "format": "maven2", "type": "proxy", "cleanup": None},
        {"name": "docker-hosted", "format": "docker", "type": "hosted",
         "cleanup": {"policyNames": ["p1"]}},
    ]))
    body = http_client.get("/api/cleanup-audit").json()
    row = body["servers"][0]
    assert row["compact_tasks"] == 0
    assert row["repos_without_cleanup"] == 1
    assert row["has_docker"] is True
    assert row["docker_gc_tasks"] == 0


# -- proxy status board ----------------------------------------------------------

@respx.mock
def test_proxy_status_blocked(http_client):
    respx.get(f"{API}/repositories").mock(return_value=httpx.Response(200, json=[
        {"name": "fedora-epel", "format": "yum", "type": "proxy",
         "attributes": {"proxy": {"remoteUrl": "https://mirror.example/epel/"}}},
    ]))
    respx.get(INTERNAL).mock(return_value=httpx.Response(200, json=[
        {"name": "fedora-epel",
         "status": {"online": True,
                    "description": "Remote Auto Blocked and Unavailable",
                    "reason": "java.net.SocketTimeoutException"}},
    ]))
    body = http_client.get("/api/proxy-status").json()
    assert body["counts"]["blocked"] == 1
    item = body["items"][0]
    assert item["state"] == "blocked"
    assert "SocketTimeout" in item["detail"]


# -- fleet search -----------------------------------------------------------------

@respx.mock
def test_search_hits(http_client):
    respx.get(f"{API}/search").mock(return_value=httpx.Response(200, json={
        "items": [{"repository": "maven-central", "format": "maven2",
                   "group": "org.apache", "name": "log4j-core", "version": "2.14"}],
        "continuationToken": None,
    }))
    body = http_client.get("/api/search?q=log4j").json()
    assert body["count"] == 1
    assert body["hits"][0]["instance_name"] == "Test Nexus"


def test_search_requires_query(http_client):
    assert http_client.get("/api/search").status_code == 400


# -- matrix copy validation --------------------------------------------------------

def test_copy_repo_rejects_same_instance(http_client):
    r = http_client.post(
        "/api/matrix/copy-repo?repository=x&source_id=test&target_id=test"
    )
    assert r.status_code == 400
