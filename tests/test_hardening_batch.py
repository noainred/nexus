"""Tests for the crash-safety / security / optimization batch:
atomic writes, secret file permissions, backup token redaction, disk-history
cache + purge, and the fast ping-timestamp parser."""
from __future__ import annotations

import json
import stat
from datetime import datetime, timezone

import pytest

from app.config import Settings, InstanceConfig, save_instances
from app.storage import atomic_write_text


# -- atomic_write_text ------------------------------------------------------

def test_atomic_write_creates_content_and_mode(tmp_path):
    p = tmp_path / "sub" / "f.json"
    atomic_write_text(p, '{"a":1}', mode=0o600)
    assert p.read_text() == '{"a":1}'
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    # No leftover temp files in the directory.
    assert [x.name for x in p.parent.iterdir()] == ["f.json"]


def test_atomic_write_leaves_original_on_error(tmp_path, monkeypatch):
    p = tmp_path / "f.txt"
    atomic_write_text(p, "original")
    import app.storage as storage_mod

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(storage_mod.os, "replace", boom)
    with pytest.raises(RuntimeError):
        atomic_write_text(p, "new-data")
    assert p.read_text() == "original"                 # untouched
    assert [x.name for x in tmp_path.iterdir()] == ["f.txt"]  # temp cleaned up


# -- instances.yaml is written 0600 (holds node passwords) ------------------

def test_save_instances_is_private(tmp_path):
    s = Settings(instances_file=str(tmp_path / "instances.yaml"))
    inst = InstanceConfig(id="a", name="A", base_url="http://x:8081",
                          username="admin", password="secretpw")
    save_instances([inst], settings=s)
    p = tmp_path / "instances.yaml"
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert "secretpw" in p.read_text()


# -- backup redacts the auto-update token -----------------------------------

def test_portal_backup_redacts_update_token(tmp_path):
    import app.backup as backup_mod
    uc = tmp_path / "update-config.json"
    uc.write_text(json.dumps({"source": "github", "url": "github:o/r",
                              "token": "ghp_SECRET", "interval": 300}), encoding="utf-8")
    s = Settings(update_config_file=str(uc), instances_file=str(tmp_path / "none.yaml"))
    entry = backup_mod._write_portal_backup(tmp_path, s)
    written = json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))
    assert written["update_config"]["token"] == ""
    assert written["update_config"]["token_redacted"] is True
    assert "ghp_SECRET" not in json.dumps(written)


def test_portal_backup_file_is_owner_only(tmp_path):
    """자격증명이 담기는 _portal.json은 0600으로 기록돼야 한다."""
    import os
    import stat
    import app.backup as backup_mod
    s = Settings(update_config_file=str(tmp_path / "u.json"),
                 instances_file=str(tmp_path / "none.yaml"))
    entry = backup_mod._write_portal_backup(tmp_path, s)
    mode = stat.S_IMODE(os.stat(tmp_path / entry["file"]).st_mode)
    assert mode & 0o077 == 0, oct(mode)   # group/other 권한 없음


def test_prune_only_touches_timestamp_dirs(tmp_path):
    """_prune는 타임스탬프 형식 폴더만 삭제하고 무관한 디렉터리는 보존해야 한다."""
    import app.backup as backup_mod
    (tmp_path / "projects").mkdir()
    (tmp_path / "archive").mkdir()
    for ts in ("20260101-000000", "20260102-000000", "20260103-000000"):
        (tmp_path / ts).mkdir()
    backup_mod._prune(tmp_path, keep=1)
    names = {p.name for p in tmp_path.iterdir()}
    assert "projects" in names and "archive" in names      # 무관 폴더 보존
    assert "20260103-000000" in names                      # 최신 1개 유지
    assert "20260101-000000" not in names and "20260102-000000" not in names


# -- disk-history purge + parse cache ---------------------------------------

def test_diskmon_purge_and_cache(tmp_path, monkeypatch):
    import app.diskmon as diskmon
    csv = tmp_path / "disk.csv"
    csv.write_text(
        "2026-06-01T00:00:00Z,a,default,10,100\n"
        "2026-06-01T00:00:00Z,b,default,20,100\n",
        encoding="utf-8",
    )
    s = Settings(disk_file=str(csv))
    diskmon._read_cache.clear()

    first = diskmon._read(s)
    assert set(first.keys()) == {("a", "default"), ("b", "default")}
    # Second read is served from cache: it must not touch the file at all.
    monkeypatch.setattr(diskmon.Path, "read_text",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("re-read")))
    assert diskmon._read(s) is first

    monkeypatch.undo()
    removed = diskmon.purge("a", s)
    assert removed == 1
    after = diskmon._read(s)  # mtime/size changed → cache invalidated
    assert set(after.keys()) == {("b", "default")}


# -- fast ping timestamp parser matches strptime ----------------------------

@pytest.mark.parametrize("ts", [
    "2026-06-27T15:01:06Z", "2000-01-01T00:00:00Z", "2026-12-31T23:59:59Z",
])
def test_ping_epoch_matches_strptime(ts):
    from app.pingmon import _epoch, _TS_FMT
    expected = datetime.strptime(ts, _TS_FMT).replace(tzinfo=timezone.utc).timestamp()
    assert _epoch(ts) == expected


def test_ping_epoch_rejects_garbage():
    from app.pingmon import _epoch
    with pytest.raises(ValueError):
        _epoch("not-a-timestamp!!")
