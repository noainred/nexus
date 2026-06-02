"""Tests for the repository comparison matrix builder."""
from __future__ import annotations

from app.matrix import build_matrix, build_repo_diff
from app.models import MatrixColumn, Repository


def _repo(name, fmt="raw", type_="hosted", remote_url=None, online=True):
    attrs = {"online": online}
    if remote_url:
        attrs["proxy"] = {"remoteUrl": remote_url}
    return Repository(name=name, format=fmt, type=type_, online=online, attributes=attrs)


COLS = [
    MatrixColumn(id="dmz", name="DMZ"),
    MatrixColumn(id="core", name="Core"),
    MatrixColumn(id="site1", name="Site1"),
]


def test_consistent_when_all_present_and_identical():
    repos = [_repo("pypi", "pypi", "proxy", "https://pypi.org/simple")]
    matrix = build_matrix(
        COLS,
        {"dmz": list(repos), "core": list(repos), "site1": list(repos)},
    )
    row = matrix.rows[0]
    assert row.repository == "pypi"
    assert row.status == "consistent"
    assert all(cell.matches_reference for cell in row.cells.values())


def test_drift_when_remote_url_differs():
    base = _repo("pypi", "pypi", "proxy", "https://pypi.org/simple")
    drifted = _repo("pypi", "pypi", "proxy", "https://mirror.internal/simple")
    matrix = build_matrix(
        COLS,
        {"dmz": [base], "core": [drifted], "site1": [base]},
    )
    row = matrix.rows[0]
    assert row.status == "drift"
    # Reference is the majority config (dmz + site1), so core is the odd one.
    assert row.cells["dmz"].matches_reference is True
    assert row.cells["site1"].matches_reference is True
    assert row.cells["core"].matches_reference is False


def test_partial_when_missing_in_one_instance():
    repos = [_repo("epel")]
    matrix = build_matrix(
        COLS,
        {"dmz": list(repos), "core": list(repos), "site1": []},
    )
    row = matrix.rows[0]
    assert row.status == "partial"
    assert row.cells["site1"].present is False
    assert row.cells["dmz"].present is True


def test_unreachable_instance_marks_unknown_cells():
    repos = [_repo("rocky")]
    matrix = build_matrix(
        COLS,
        {"dmz": list(repos), "core": None, "site1": list(repos)},
    )
    column = next(c for c in matrix.columns if c.id == "core")
    # build_matrix preserves the column objects it is given; the router sets
    # reachability. Here we only assert cell-level unknown handling.
    row = matrix.rows[0]
    assert row.cells["core"].unknown is True
    assert row.cells["core"].present is False
    # Unknown cells are excluded from drift detection -> still consistent.
    assert row.status == "consistent"
    assert column.id == "core"


def test_union_of_repository_names_sorted():
    matrix = build_matrix(
        COLS,
        {
            "dmz": [_repo("rocky")],
            "core": [_repo("epel")],
            "site1": [_repo("pypi")],
        },
    )
    names = [r.repository for r in matrix.rows]
    assert names == ["epel", "pypi", "rocky"]
    # Each only exists in one of three reachable instances -> partial.
    assert all(r.status == "partial" for r in matrix.rows)


def test_format_or_type_difference_is_drift():
    matrix = build_matrix(
        COLS[:2],
        {
            "dmz": [_repo("repo", "raw", "hosted")],
            "core": [_repo("repo", "raw", "proxy", "https://x")],
        },
    )
    assert matrix.rows[0].status == "drift"


# -- field-level repository diff ------------------------------------------

DIFF_COLS = [
    MatrixColumn(id="front1", name="Frontend 1"),
    MatrixColumn(id="back1", name="Backend 1"),
]


def test_repo_diff_flags_only_differing_fields():
    front = {
        "name": "fedora-epel",
        "online": True,
        "storage": {"blobStoreName": "default"},
        "proxy": {"remoteUrl": "https://dl.fedoraproject.org/epel/"},
    }
    back = {
        "name": "fedora-epel",
        "online": True,
        "storage": {"blobStoreName": "default"},
        "proxy": {"remoteUrl": "http://192.168.139.96:8081/repository/fedora-epel/"},
    }
    diff = build_repo_diff("fedora-epel", DIFF_COLS, {"front1": front, "back1": back})

    by_key = {f.key: f for f in diff.fields}
    # The proxy URL differs; everything else matches.
    assert by_key["proxy.remoteUrl"].differs is True
    assert by_key["storage.blobStoreName"].differs is False
    assert by_key["online"].differs is False
    # name/url are excluded from the comparison as pure noise.
    assert "name" not in by_key


def test_repo_diff_missing_on_one_instance_counts_as_difference():
    front = {"online": True, "proxy": {"remoteUrl": "https://x"}}
    back = {"online": True}  # no proxy section
    diff = build_repo_diff("pkg", DIFF_COLS, {"front1": front, "back1": back})
    by_key = {f.key: f for f in diff.fields}
    assert by_key["proxy.remoteUrl"].differs is True
    assert by_key["proxy.remoteUrl"].values["back1"] is None


def test_repo_diff_all_identical_has_no_differences():
    cfg = {"online": True, "storage": {"blobStoreName": "default"}}
    diff = build_repo_diff("repo", DIFF_COLS, {"front1": dict(cfg), "back1": dict(cfg)})
    assert all(not f.differs for f in diff.fields)


def test_repo_diff_unreachable_instance_excluded_from_diff():
    cols = [
        MatrixColumn(id="front1", name="Frontend 1"),
        MatrixColumn(id="back1", name="Backend 1", reachable=False, error="down"),
    ]
    front = {"online": True}
    diff = build_repo_diff("repo", cols, {"front1": front, "back1": None})
    by_key = {f.key: f for f in diff.fields}
    # Only one reachable+present instance -> nothing differs.
    assert by_key["online"].differs is False
    assert by_key["online"].values["back1"] is None
