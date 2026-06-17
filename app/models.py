"""Pydantic models for API requests and responses."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class InstanceSummary(BaseModel):
    """Public view of a managed instance (never exposes the password)."""

    id: str
    name: str
    base_url: str
    alt_url: str = ""
    username: Optional[str] = None
    group: str = ""
    tier: int = 0
    timezone: str = ""
    verify_tls: Optional[bool] = None
    use_in_monitoring: bool = True
    use_in_comparison: bool = True
    is_reference: bool = False


class InstanceCreate(BaseModel):
    """Payload to add a managed instance."""

    id: str = Field(..., min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    alt_url: str = ""
    username: str = ""
    password: str = ""
    group: str = ""
    tier: int = 0
    timezone: str = ""
    verify_tls: Optional[bool] = None
    use_in_monitoring: bool = True
    use_in_comparison: bool = True


class InstanceUpdate(BaseModel):
    """Payload to edit a managed instance (id is taken from the path)."""

    name: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    alt_url: str = ""
    username: str = ""
    # Blank password means "keep the existing one".
    password: Optional[str] = None
    group: str = ""
    tier: int = 0
    timezone: str = ""
    verify_tls: Optional[bool] = None
    use_in_monitoring: bool = True
    use_in_comparison: bool = True


class GroupOrder(BaseModel):
    """Display order of instance groups in the overview."""

    groups: List[str] = Field(default_factory=list)


class CompareFields(BaseModel):
    """Which repository attributes the comparison matrix uses for drift."""

    fields: List[str] = Field(default_factory=list)


class PingConfig(BaseModel):
    """Ping monitoring settings (interval + colour thresholds)."""

    interval: float = 60.0
    warn_pct: float = 20.0
    crit_pct: float = 50.0


class PingPoint(BaseModel):
    t: int            # epoch seconds
    v: float          # ping ms
    color: str        # ok | warn | crit


class PingSeries(BaseModel):
    id: str
    name: str
    group: str = ""
    baseline: Optional[float] = None
    points: List[PingPoint] = Field(default_factory=list)


class PingHistory(BaseModel):
    days: int
    warn_pct: float = 20.0
    crit_pct: float = 50.0
    series: List[PingSeries] = Field(default_factory=list)


class SyncJob(BaseModel):
    """One scheduled proxy cache-warming job."""

    id: str = ""
    source_id: str
    target_id: str
    repository: str
    time: str = "03:00"        # daily HH:MM (local time)
    enabled: bool = True


class SyncJobs(BaseModel):
    jobs: List[SyncJob] = Field(default_factory=list)


class BackupConfig(BaseModel):
    """Scheduled configuration-backup settings."""

    enabled: bool = False
    time: str = "02:00"        # daily HH:MM (local time)
    keep: int = 14             # how many backup runs to retain
    path: str = ""             # directory to write backups to ("" = default)


class InstanceTestRequest(BaseModel):
    """Connection-test payload (does not persist anything)."""

    base_url: str = Field(..., min_length=1)
    username: str = ""
    password: str = ""
    verify_tls: Optional[bool] = None


class InstanceTestResult(BaseModel):
    """Outcome of a connection test."""

    reachable: bool = False
    healthy: bool = False
    response_ms: Optional[float] = None
    repository_count: Optional[int] = None
    error: Optional[str] = None


class InstanceStatus(BaseModel):
    """Health/monitoring snapshot for one instance."""

    id: str
    name: str
    base_url: str
    group: str = ""
    reachable: bool
    healthy: bool
    response_ms: Optional[float] = None
    error: Optional[str] = None
    checks: dict[str, bool] = Field(default_factory=dict)
    repository_count: Optional[int] = None
    checked_at: Optional[str] = None   # when this status was last measured
    cached: bool = False               # True when served from the poller cache


class InstanceSecurity(BaseModel):
    """Security posture snapshot for one instance."""

    id: str
    name: str
    reachable: bool = True
    error: Optional[str] = None
    anonymous_enabled: Optional[bool] = None
    admin_active: Optional[bool] = None
    admin_users: List[str] = Field(default_factory=list)
    user_count: Optional[int] = None
    issues: List[str] = Field(default_factory=list)
    risk: str = "ok"   # ok | warn | unknown


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


class RepoDownloadSummary(BaseModel):
    """Per-repository usage totals (no asset list) for the server overview."""

    repository: str
    format: Optional[str] = None
    type: Optional[str] = None
    total_assets: int = 0
    downloaded_assets: int = 0
    total_size_bytes: int = 0
    downloaded_size_bytes: int = 0
    truncated: bool = False
    error: Optional[str] = None


class ServerDownloadSummary(BaseModel):
    """Download usage for every repository on one server."""

    instance_id: str
    total_assets: int = 0
    downloaded_assets: int = 0
    total_size_bytes: int = 0
    downloaded_size_bytes: int = 0
    repositories: List[RepoDownloadSummary] = Field(default_factory=list)


class Task(BaseModel):
    """A scheduled task as returned by the Nexus tasks API."""

    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    message: Optional[str] = None
    current_state: Optional[str] = None
    last_run_result: Optional[str] = None
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    runnable: bool = False
    stoppable: bool = False


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


class ReleaseChange(BaseModel):
    type: str   # added | changed | removed
    text: str


class ReleaseEntry(BaseModel):
    version: str
    date: str
    changes: List[ReleaseChange] = Field(default_factory=list)


class ReleaseNotes(BaseModel):
    version: str
    notes: List[ReleaseEntry] = Field(default_factory=list)


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


class Alert(BaseModel):
    """A single active alert condition."""

    key: str
    severity: str = "warning"   # warning | critical
    node: Optional[str] = None
    message: str


class AlertsStatus(BaseModel):
    """Current alert state plus notifier configuration."""

    webhook_configured: bool = False
    interval: float = 60.0
    alerts: List[Alert] = Field(default_factory=list)


class NodeMetrics(BaseModel):
    """JVM / resource metrics for one node (from /service/metrics/data)."""

    id: str
    name: str
    reachable: bool = True
    error: Optional[str] = None
    heap_used_bytes: Optional[int] = None
    heap_max_bytes: Optional[int] = None
    heap_usage_pct: Optional[float] = None
    thread_count: Optional[int] = None
    uptime_ms: Optional[int] = None


class ProxyLink(BaseModel):
    """A proxy repository's upstream link (an edge in the topology)."""

    repository: str
    remote_url: str
    target_host: str
    target_id: Optional[str] = None   # matched managed node id, else external
    internal: bool = False
    remote_reachable: Optional[bool] = None
    broken: bool = False


class TopologyNode(BaseModel):
    """One node (instance) plus its outgoing proxy links."""

    id: str
    name: str
    base_url: str
    tier: int = 0
    reachable: bool = True
    error: Optional[str] = None
    proxies: List[ProxyLink] = Field(default_factory=list)


class Topology(BaseModel):
    """Proxy-derived topology across all managed nodes."""

    nodes: List[TopologyNode] = Field(default_factory=list)
    broken_links: int = 0


class ContentRow(BaseModel):
    """One component compared across instances (presence only)."""

    key: str
    group: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    present: dict[str, bool] = Field(default_factory=dict)
    consistent: bool = True


class ContentMatrix(BaseModel):
    """Actual component presence for one repository across instances."""

    repository: str
    columns: List[MatrixColumn] = Field(default_factory=list)
    rows: List[ContentRow] = Field(default_factory=list)
    truncated: bool = False


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
