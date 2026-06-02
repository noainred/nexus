"""Pydantic models for API requests and responses."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class InstanceSummary(BaseModel):
    """Public view of a managed instance (never exposes credentials)."""

    id: str
    name: str
    base_url: str


class InstanceStatus(BaseModel):
    """Health/monitoring snapshot for one instance."""

    id: str
    name: str
    base_url: str
    reachable: bool
    healthy: bool
    response_ms: Optional[float] = None
    error: Optional[str] = None
    checks: dict[str, bool] = Field(default_factory=dict)
    repository_count: Optional[int] = None


class Repository(BaseModel):
    """A Nexus repository as returned by the REST API."""

    name: str
    format: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    online: Optional[bool] = None
    # Raw attributes passed through for advanced views.
    attributes: dict[str, Any] = Field(default_factory=dict)


class Component(BaseModel):
    """A component (a group of assets) inside a repository."""

    id: str
    repository: Optional[str] = None
    group: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    format: Optional[str] = None


class ComponentPage(BaseModel):
    """A page of components plus the token for the next page."""

    items: List[Component] = Field(default_factory=list)
    continuation_token: Optional[str] = None


class Asset(BaseModel):
    """A single asset (file) inside a repository."""

    id: str
    path: Optional[str] = None
    repository: Optional[str] = None
    format: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    last_downloaded: Optional[str] = None


class AssetPage(BaseModel):
    """A page of assets plus the token for the next page."""

    items: List[Asset] = Field(default_factory=list)
    continuation_token: Optional[str] = None


class AssetDownload(BaseModel):
    """A downloaded asset shown in the usage report."""

    path: str
    size_bytes: Optional[int] = None
    last_downloaded: Optional[str] = None
    content_type: Optional[str] = None


class DownloadReport(BaseModel):
    """Aggregated download usage for one repository."""

    repository: str
    total_assets: int = 0
    downloaded_assets: int = 0
    total_size_bytes: int = 0
    downloaded_size_bytes: int = 0
    # True when the scan hit the page cap and numbers are a lower bound.
    truncated: bool = False
    items: List[AssetDownload] = Field(default_factory=list)


class BlobStore(BaseModel):
    """Blob store usage information used by the monitoring view."""

    name: str
    type: Optional[str] = None
    total_size_bytes: Optional[int] = None
    available_space_bytes: Optional[int] = None
    blob_count: Optional[int] = None


class InstanceBlobStores(BaseModel):
    """Per-instance blob store usage for the site-by-site overview."""

    id: str
    name: str
    reachable: bool = True
    error: Optional[str] = None
    blobstores: List[BlobStore] = Field(default_factory=list)
    total_size_bytes: Optional[int] = None
    blob_count: Optional[int] = None


class CleanupPolicy(BaseModel):
    """A cleanup policy definition."""

    name: str
    format: str = "*"
    notes: Optional[str] = None
    mode: str = "delete"
    criteria: dict[str, Any] = Field(default_factory=dict)


class CleanupPolicyCreate(BaseModel):
    """Payload for creating or updating a cleanup policy."""

    name: str = Field(..., min_length=1)
    format: str = "*"
    notes: Optional[str] = None
    criteria_last_blob_updated: Optional[int] = Field(
        default=None,
        description="Delete components not updated for N days.",
    )
    criteria_last_downloaded: Optional[int] = Field(
        default=None,
        description="Delete components not downloaded for N days.",
    )
    criteria_release_type: Optional[str] = Field(
        default=None,
        description="RELEASES or PRERELEASES (maven/format dependent).",
    )
    criteria_asset_regex: Optional[str] = None


class ApiError(BaseModel):
    """Uniform error envelope returned to the frontend."""

    detail: str


# -- Repository comparison matrix -----------------------------------------


class MatrixColumn(BaseModel):
    """One instance column in the comparison matrix."""

    id: str
    name: str
    reachable: bool = True
    error: Optional[str] = None


class MatrixCell(BaseModel):
    """A single repository's state within one instance."""

    present: bool = False
    # ``unknown`` is True when the owning instance could not be queried.
    unknown: bool = False
    format: Optional[str] = None
    type: Optional[str] = None
    remote_url: Optional[str] = None
    online: Optional[bool] = None
    # None when not present; otherwise True if this cell matches the row's
    # reference configuration, False when it drifts from it.
    matches_reference: Optional[bool] = None


class MatrixRow(BaseModel):
    """One repository name compared across every instance."""

    repository: str
    # consistent | drift | partial | unknown
    status: str
    cells: dict[str, MatrixCell] = Field(default_factory=dict)


class RepositoryMatrix(BaseModel):
    """Full comparison grid: repositories (rows) x instances (columns)."""

    columns: List[MatrixColumn] = Field(default_factory=list)
    rows: List[MatrixRow] = Field(default_factory=list)


class RepoDiffField(BaseModel):
    """One configuration field compared across instances."""

    key: str
    # instance id -> stringified value (None when absent / unreachable).
    values: dict[str, Optional[str]] = Field(default_factory=dict)
    differs: bool = False


class RepositoryDiff(BaseModel):
    """Field-by-field configuration comparison for one repository."""

    repository: str
    columns: List[MatrixColumn] = Field(default_factory=list)
    fields: List[RepoDiffField] = Field(default_factory=list)
