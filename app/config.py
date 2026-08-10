"""Application configuration and managed-instance loading."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set

import yaml
from pydantic import BaseModel, BaseSettings, Field, ValidationError, validator


class InstanceConfig(BaseModel):
    """Connection details for a single managed Nexus instance."""

    id: str = Field(..., description="Unique, URL-safe identifier.")
    name: str = Field(..., description="Human friendly label.")
    base_url: str = Field(..., description="Root URL of the Nexus instance.")
    alt_url: str = Field(
        default="",
        description=(
            "Alternate URL/host of the same server (e.g. FQDN when base_url "
            "is an IP). Used so proxies pointing at either form are matched."
        ),
    )
    username: str = Field(..., description="Account used for management calls.")
    password: str = Field(..., description="Password or token for the account.")
    group: str = Field(default="", description="Group label for the overview.")
    tier: int = Field(
        default=0,
        description="Manual hierarchy tier for the topology board (1=top..N); "
        "0 means auto-derive from proxy links.",
    )
    timezone: str = Field(
        default="",
        description="IANA timezone of the server (e.g. Asia/Seoul); optional.",
    )
    verify_tls: Optional[bool] = Field(
        default=None,
        description="Per-instance TLS verification override.",
    )
    use_in_monitoring: bool = Field(
        default=True,
        description="Include this instance in monitoring aggregates.",
    )
    use_in_comparison: bool = Field(
        default=True,
        description="Include this instance in comparison views.",
    )
    is_reference: bool = Field(
        default=False,
        description="Designated baseline/reference instance for comparisons.",
    )

    @property
    def api_root(self) -> str:
        """Base path for Nexus REST v1 endpoints."""
        return f"{self.base_url.rstrip('/')}/service/rest/v1"


class Settings(BaseSettings):
    """Process-wide settings, populated from environment variables."""

    class Config:
        env_prefix = "NEXUS_MANAGER_"
        env_file = ".env"
        extra = "ignore"

    instances_file: str = "instances.yaml"
    request_timeout: float = 15.0
    verify_tls: bool = True
    # Server-saved instance/column order (비교 매트릭스 등 공통 순서).
    column_order_file: str = "column-order.json"
    # Server-saved tier-board (topology) node layout — shared by all users.
    topo_layout_file: str = "topo-layout.json"
    # Nexus request.log files the manager may read server-side for the
    # download-tracking (IP) tab. Comma/newline-separated "라벨=경로" or just
    # paths (absolute, glob allowed). Only files listed here are readable.
    request_log_paths: str = ""
    # Persisted access-log config (template/paths) editable in the UI.
    access_log_config_file: str = "access-log-config.json"
    # Background status poller: how often (seconds) to refresh the cached
    # node status the dashboard reads instantly.
    status_poll_interval: float = 20.0

    # Alerting (Slack-compatible incoming webhook; empty disables sending).
    alert_webhook: str = ""
    alert_interval: float = 60.0
    alert_heap_pct: float = 90.0
    alert_disk_pct: float = 90.0
    alert_drift: bool = False   # also alert on repository config drift

    # Infra ping monitoring.
    ping_file: str = "ping-history.csv"
    ping_interval: float = 60.0

    # Scheduled configuration backups.
    backup_dir: str = "backups"

    # Blob-store disk usage sampling (saturation forecast).
    disk_file: str = "disk-history.csv"

    # Manager access control + audit trail.
    # When admin_password is set (NEXUS_MANAGER_ADMIN_PASSWORD), every /api
    # call requires login; write operations are appended to audit_file.
    admin_password: str = ""
    audit_file: str = "audit.log"
    # Manager login accounts (id/pw, PBKDF2-hashed) — coexist with admin_password.
    accounts_file: str = "accounts.json"

    # Portal-driven auto-update view (mirrors the deploy/auto-update.sh watcher).
    update_dir: str = "updates"
    update_url: str = ""
    update_config_file: str = "update-config.json"
    update_log: str = "auto-update.log"

    # Portal branding (dashboard title), editable from 서버 설정.
    portal_config_file: str = "portal-config.json"

    @validator("admin_password")
    def _clean_admin_password(cls, v: str) -> str:
        """Tolerate the common .env footgun where the password picks up a
        trailing newline, surrounding whitespace, or wrapping quotes — these
        would otherwise make every login fail with a "correct" password."""
        if not isinstance(v, str):
            return v
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        return v


class InstancesDocument(BaseModel):
    """Schema of the instances YAML file."""

    instances: List[InstanceConfig] = Field(default_factory=list)
    group_order: List[str] = Field(default_factory=list)
    compare_fields: List[str] = Field(
        default_factory=lambda: ["format", "type", "remote_url"]
    )
    ping_interval: float = 60.0
    ping_warn_pct: float = 20.0
    ping_crit_pct: float = 50.0
    backup_enabled: bool = False
    backup_time: str = "02:00"
    backup_keep: int = 14
    backup_path: str = ""
    sync_jobs: List[dict] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()


def _instance_path(settings: Settings) -> Path:
    path = Path(settings.instances_file)
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    return path


def _validate_document(raw: dict, where: str = "config") -> InstancesDocument:
    try:
        document = InstancesDocument.parse_obj(raw)
    except ValidationError as exc:  # pragma: no cover - surfaced to operator
        raise RuntimeError(f"Invalid instances {where}: {exc}") from exc
    seen: Set[str] = set()
    for instance in document.instances:
        if instance.id in seen:
            raise RuntimeError(f"Duplicate instance id in {where}: {instance.id!r}")
        seen.add(instance.id)
    return document


def load_document(settings: Optional[Settings] = None) -> InstancesDocument:
    """Load and validate the full instances document (instances + group order)."""
    settings = settings or get_settings()
    path = _instance_path(settings)
    if not path.exists():
        return InstancesDocument()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    document = _validate_document(raw, where=str(path))
    for instance in document.instances:
        if instance.verify_tls is None:
            instance.verify_tls = settings.verify_tls
    return document


def load_instances(settings: Optional[Settings] = None) -> List[InstanceConfig]:
    """Convenience wrapper returning just the instances list."""
    return load_document(settings).instances


def instances_to_dict(
    instances: List[InstanceConfig],
    group_order: Optional[List[str]] = None,
    compare_fields: Optional[List[str]] = None,
    ping: Optional[dict] = None,
    backup: Optional[dict] = None,
    sync_jobs: Optional[List[dict]] = None,
) -> dict:
    """Serialise instances to the plain dict written to YAML / exported."""
    data: dict = {
        "instances": [
            {
                "id": c.id,
                "name": c.name,
                "base_url": c.base_url,
                "alt_url": c.alt_url,
                "username": c.username,
                "password": c.password,
                "group": c.group,
                "tier": c.tier,
                "timezone": c.timezone,
                "verify_tls": c.verify_tls,
                "use_in_monitoring": c.use_in_monitoring,
                "use_in_comparison": c.use_in_comparison,
                "is_reference": c.is_reference,
            }
            for c in instances
        ]
    }
    if group_order:
        data["group_order"] = list(group_order)
    if compare_fields is not None:
        data["compare_fields"] = list(compare_fields)
    if ping:
        data["ping_interval"] = ping.get("interval", 60.0)
        data["ping_warn_pct"] = ping.get("warn_pct", 20.0)
        data["ping_crit_pct"] = ping.get("crit_pct", 50.0)
    if backup:
        data["backup_enabled"] = bool(backup.get("enabled", False))
        data["backup_time"] = backup.get("time", "02:00")
        data["backup_keep"] = int(backup.get("keep", 14))
        data["backup_path"] = backup.get("path", "")
    if sync_jobs is not None:
        data["sync_jobs"] = list(sync_jobs)
    return data


def instances_to_yaml(
    instances: List[InstanceConfig],
    group_order: Optional[List[str]] = None,
    compare_fields: Optional[List[str]] = None,
    ping: Optional[dict] = None,
    backup: Optional[dict] = None,
    sync_jobs: Optional[List[dict]] = None,
) -> str:
    return yaml.safe_dump(
        instances_to_dict(instances, group_order, compare_fields, ping, backup, sync_jobs),
        allow_unicode=True,
        sort_keys=False,
    )


def parse_document(raw_text: str) -> InstancesDocument:
    """Parse an exported YAML/JSON config into a validated document."""
    data = yaml.safe_load(raw_text) or {}
    return _validate_document(data, where="imported file")


def save_instances(
    instances: List[InstanceConfig],
    group_order: Optional[List[str]] = None,
    compare_fields: Optional[List[str]] = None,
    ping: Optional[dict] = None,
    backup: Optional[dict] = None,
    sync_jobs: Optional[List[dict]] = None,
    settings: Optional[Settings] = None,
) -> None:
    """Persist the managed instances (and view prefs) back to the YAML file."""
    settings = settings or get_settings()
    path = _instance_path(settings)
    # instances.yaml holds per-node passwords in plaintext → atomic + 0600 so a
    # crash mid-write can't corrupt the whole server list and the credentials
    # aren't left world-readable.
    from .storage import atomic_write_text
    atomic_write_text(
        path,
        instances_to_yaml(instances, group_order, compare_fields, ping, backup, sync_jobs),
        mode=0o600,
    )
