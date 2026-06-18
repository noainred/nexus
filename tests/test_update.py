"""Unit tests for the auto-update GitHub branch-folder source resolution."""
from __future__ import annotations

from app.routers import update as up


def test_gh_contents_api_from_raw_url():
    # raw.githubusercontent.com/<owner>/<repo>/<ref...>/<dir> → contents API.
    # The branch name contains a '/', which must stay in ?ref=.
    url = "https://raw.githubusercontent.com/noainred/nexus/claude/practical-noether-uPpi9/download"
    assert up._gh_contents_api(url) == (
        "https://api.github.com/repos/noainred/nexus/contents/download"
        "?ref=claude/practical-noether-uPpi9"
    )


def test_gh_contents_api_from_tree_and_raw_and_blob():
    base = "https://api.github.com/repos/o/r/contents/download?ref=main"
    assert up._gh_contents_api("https://github.com/o/r/tree/main/download") == base
    assert up._gh_contents_api("https://github.com/o/r/raw/main/download") == base
    assert up._gh_contents_api("https://github.com/o/r/blob/main/download") == base


def test_gh_contents_api_rejects_non_branch_urls():
    # github:owner/repo and the bare repo root are NOT branch folders.
    assert up._gh_contents_api("github:noainred/nexus") is None
    assert up._gh_contents_api("https://github.com/noainred/nexus") is None
    assert up._gh_contents_api("http://mirror.local/path/") is None
    # A ref with no trailing directory segment is ambiguous → None.
    assert up._gh_contents_api("https://github.com/o/r/tree/main") is None


def test_gh_join_keeps_ref_query():
    api = "https://api.github.com/repos/o/r/contents/download?ref=feat/x"
    assert up._gh_join(api, "versions.json") == (
        "https://api.github.com/repos/o/r/contents/download/versions.json?ref=feat/x"
    )
    # No query → plain path join.
    assert up._gh_join("http://m/dir", "a.zip") == "http://m/dir/a.zip"


def test_config_accepts_raw_github_url(tmp_path, monkeypatch):
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(up, "_cfg_path", lambda: Path(tmp_path) / "update-config.json")
    client = TestClient(app)
    raw = "https://raw.githubusercontent.com/noainred/nexus/claude/practical-noether-uPpi9/download"
    resp = client.post("/api/update/config", json={"source": "github", "url": raw, "auto_install": False})
    assert resp.status_code == 200, resp.text
    assert resp.json()["config"]["url"] == raw


def test_config_rejects_bogus_github_url(tmp_path, monkeypatch):
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(up, "_cfg_path", lambda: Path(tmp_path) / "update-config.json")
    client = TestClient(app)
    resp = client.post("/api/update/config", json={"source": "github", "url": "http://not-github/x"})
    assert resp.status_code == 400


def test_column_order_roundtrip(tmp_path, monkeypatch):
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import instances as inst

    monkeypatch.setattr(inst, "_order_path", lambda: Path(tmp_path) / "column-order.json")
    client = TestClient(app)
    assert client.get("/api/instances/column-order").json() == {"order": []}
    r = client.put("/api/instances/column-order", json={"order": ["b", "a", "c"]})
    assert r.status_code == 200 and r.json() == {"order": ["b", "a", "c"]}
    # Persisted: a fresh GET returns the saved order.
    assert client.get("/api/instances/column-order").json() == {"order": ["b", "a", "c"]}


def test_portal_hidden_tabs_roundtrip(tmp_path, monkeypatch):
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import meta

    monkeypatch.setattr(meta, "_portal_path", lambda: Path(tmp_path) / "portal-config.json")
    client = TestClient(app)
    # default: no hidden tabs
    assert client.get("/api/portal").json()["hidden_tabs"] == []
    r = client.put("/api/portal", json={"title": "T", "hidden_tabs": ["search", "alerts"]})
    assert r.status_code == 200 and r.json()["hidden_tabs"] == ["search", "alerts"]
    got = client.get("/api/portal").json()
    assert got["title"] == "T" and got["hidden_tabs"] == ["search", "alerts"]
    # title-only PUT keeps hidden_tabs
    client.put("/api/portal", json={"title": "T2"})
    assert client.get("/api/portal").json()["hidden_tabs"] == ["search", "alerts"]


def test_access_log_analyze(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import accesslog

    log = tmp_path / "request.log"
    log.write_text(
        '192.168.1.50 - admin [17/Jun/2026:15:00:01 +0900] "GET /repository/yum/7/vim.rpm HTTP/1.1" 200 1048576 "-" "yum" 12\n'
        '10.0.0.9 - - [17/Jun/2026:15:01:02 +0900] "HEAD /repository/yum/repomd.xml HTTP/1.1" 200 12 "-" "curl" 3\n'
        '10.0.0.9 - - [17/Jun/2026:15:01:03 +0900] "GET /repository/rocky9/BaseOS/rsync.rpm HTTP/1.1" 206 50000 "-" "dnf" 8\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(accesslog, "_configured", lambda: [("nexus", str(log))])
    client = TestClient(app)

    src = client.get("/api/access-log/sources").json()
    assert src["sources"][0]["path"] == str(log) and src["sources"][0]["exists"]

    recent = client.get(f"/api/access-log/analyze?path={log}").json()
    assert recent["ip_count"] == 2  # HEAD ignored; both IPs have a GET 200/206

    detail = client.get(f"/api/access-log/analyze?path={log}&ip=10.0.0.9").json()
    assert detail["total"] == 1 and detail["detail"][0]["repo"] == "rocky9"

    # path not in the allowlist is rejected
    assert client.get("/api/access-log/analyze?path=/etc/passwd").status_code == 400


def test_topology_layout_roundtrip(tmp_path, monkeypatch):
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import instances as inst

    monkeypatch.setattr(inst, "_topo_path", lambda: Path(tmp_path) / "topo-layout.json")
    client = TestClient(app)
    assert client.get("/api/instances/topology-layout").json() == {"pos": {}}
    pos = {"a": {"x": 10, "y": 20}, "b": {"x": 30.5, "y": 40}}
    r = client.put("/api/instances/topology-layout", json={"pos": pos})
    assert r.status_code == 200
    assert client.get("/api/instances/topology-layout").json()["pos"]["a"] == {"x": 10.0, "y": 20.0}
    # bad entries are dropped
    r2 = client.put("/api/instances/topology-layout", json={"pos": {"c": {"x": "bad"}, "d": {"x": 1, "y": 2}}})
    assert r2.json()["pos"] == {"d": {"x": 1.0, "y": 2.0}}
