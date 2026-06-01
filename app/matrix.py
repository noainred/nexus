"""Build the repository comparison matrix from per-instance repository lists.

The matrix answers one question at a glance: for every repository name, does
each managed instance (DMZ, Core, Site1..N) have it, and is its configuration
identical? Core lives in a different region, so configuration drift between
Core and the DMZ/site instances is exactly what we want to surface.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence

from .models import (
    MatrixCell,
    MatrixColumn,
    MatrixRow,
    Repository,
    RepositoryMatrix,
)


def _remote_url(repo: Repository) -> Optional[str]:
    """Extract a proxy repository's upstream URL, if any."""
    proxy = repo.attributes.get("proxy") if isinstance(repo.attributes, dict) else None
    if isinstance(proxy, dict):
        return proxy.get("remoteUrl")
    return None


def _signature(cell: MatrixCell) -> str:
    """Comparable fingerprint of a repository's configuration.

    Two repositories with the same name are considered "the same config" when
    their format, type, and (for proxies) upstream URL all match.
    """
    return f"{cell.format}|{cell.type}|{cell.remote_url or ''}"


def _cell_from_repo(repo: Repository) -> MatrixCell:
    return MatrixCell(
        present=True,
        format=repo.format,
        type=repo.type,
        remote_url=_remote_url(repo),
        online=repo.online,
    )


def build_matrix(
    columns: Sequence[MatrixColumn],
    repos_by_instance: dict[str, Optional[list[Repository]]],
) -> RepositoryMatrix:
    """Assemble the comparison grid.

    ``repos_by_instance`` maps instance id -> list of repositories, or ``None``
    when that instance could not be queried (its column is marked unreachable
    and its cells become "unknown", excluded from drift detection).
    """
    # Build per-instance lookup of repo name -> cell.
    cells_by_instance: dict[str, dict[str, MatrixCell]] = {}
    reachable_ids: list[str] = []
    for column in columns:
        repos = repos_by_instance.get(column.id)
        if repos is None:
            cells_by_instance[column.id] = {}
            continue
        reachable_ids.append(column.id)
        cells_by_instance[column.id] = {
            repo.name: _cell_from_repo(repo) for repo in repos
        }

    # Union of every repository name across reachable instances, sorted.
    repo_names: set[str] = set()
    for instance_id in reachable_ids:
        repo_names.update(cells_by_instance[instance_id].keys())

    rows: list[MatrixRow] = []
    for name in sorted(repo_names):
        cells: dict[str, MatrixCell] = {}
        present_signatures: list[str] = []

        for column in columns:
            repos = repos_by_instance.get(column.id)
            if repos is None:
                cells[column.id] = MatrixCell(present=False, unknown=True)
                continue
            cell = cells_by_instance[column.id].get(name)
            if cell is None:
                cells[column.id] = MatrixCell(present=False)
            else:
                cells[column.id] = cell
                present_signatures.append(_signature(cell))

        # Reference = most common configuration among present cells.
        reference: Optional[str] = None
        if present_signatures:
            reference = Counter(present_signatures).most_common(1)[0][0]

        distinct = set(present_signatures)
        present_count = len(present_signatures)
        reachable_count = len(reachable_ids)

        if reachable_count == 0:
            status = "unknown"
        elif len(distinct) > 1:
            status = "drift"
        elif present_count < reachable_count:
            status = "partial"
        else:
            status = "consistent"

        # Flag each present cell against the reference configuration.
        for column in columns:
            cell = cells[column.id]
            if cell.present:
                cell.matches_reference = _signature(cell) == reference

        rows.append(MatrixRow(repository=name, status=status, cells=cells))

    return RepositoryMatrix(columns=list(columns), rows=rows)
