"""Application configuration and managed-instance loading."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class InstanceConfig(BaseModel):
    """Connection details for a single managed Nexus instance."""

    id: str = Field(..., description="Unique, URL-safe identifier.")
    name: str = Field(..., description="Human friendly label.")
    base_url: str = Field(..., description="Root URL of the Nexus instance.")
    username: str = Field(..., description="Account used for management calls.")
    password: str = Field(..., description="Password or token for the account.")
    group: str = Field(default="", description="Group label for the overview.")
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

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_MANAGER_",
        env_file=".env",
        extra="ignore",
    )

    instances_file: str = "instances.yaml"
    request_timeout: float = 15.0
    verify_tls: bool = True

    # Alerting (Slack-compatible incoming webhook; empty disables sending).
    alert_webhook: str = ""
    alert_interval: float = 60.0
    alert_heap_pct: float = 90.0
    alert_disk_pct: float = 90.0


class InstancesDocument(BaseModel):
    """Schema of the instances YAML file."""

    instances: List[InstanceConfig] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()


def load_instances(settings: Optional[Settings] = None) -> List[InstanceConfig]:
    """Load and validate managed instances from the configured YAML file.

    Returns an empty list when the file is absent so the app can still start
    (the dashboard will simply show no instances).
    """
    settings = settings or get_settings()
    path = Path(settings.instances_file)
    if not path.is_absolute():
        path = Path(os.getcwd()) / path

    if not path.exists():
        return []

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        document = InstancesDocument.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - surfaced to operator
        raise RuntimeError(f"Invalid instances file {path}: {exc}") from exc

    seen: set[str] = set()
    for instance in document.instances:
        if instance.id in seen:
            raise RuntimeError(f"Duplicate instance id in {path}: {instance.id!r}")
        seen.add(instance.id)

    # Apply the global TLS default when an instance does not override it.
    for instance in document.instances:
        if instance.verify_tls is None:
            instance.verify_tls = settings.verify_tls

    return document.instances


def _instance_path(settings: Settings) -> Path:
    path = Path(settings.instances_file)
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    return path


def instances_to_dict(instances: List[InstanceConfig]) -> dict:
    """Serialise instances to the plain dict written to YAML / exported."""
    return {
        "instances": [
            {
                "id": c.id,
                "name": c.name,
                "base_url": c.base_url,
                "username": c.username,
                "password": c.password,
                "group": c.group,
                "verify_tls": c.verify_tls,
                "use_in_monitoring": c.use_in_monitoring,
                "use_in_comparison": c.use_in_comparison,
                "is_reference": c.is_reference,
            }
            for c in instances
        ]
    }


def instances_to_yaml(instances: List[InstanceConfig]) -> str:
    return yaml.safe_dump(
        instances_to_dict(instances), allow_unicode=True, sort_keys=False
    )


def parse_instances(raw_text: str) -> List[InstanceConfig]:
    """Parse an exported YAML/JSON config into validated instances."""
    data = yaml.safe_load(raw_text) or {}
    document = InstancesDocument.model_validate(data)
    seen: set[str] = set()
    for instance in document.instances:
        if instance.id in seen:
            raise ValueError(f"Duplicate instance id: {instance.id!r}")
        seen.add(instance.id)
    return document.instances


def save_instances(
    instances: List[InstanceConfig], settings: Optional[Settings] = None
) -> None:
    """Persist the managed instances back to the YAML file."""
    settings = settings or get_settings()
    path = _instance_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(instances_to_yaml(instances), encoding="utf-8")
