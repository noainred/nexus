"""Application configuration and managed-instance loading."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

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
    verify_tls: bool | None = Field(
        default=None,
        description="Per-instance TLS verification override.",
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


class InstancesDocument(BaseModel):
    """Schema of the instances YAML file."""

    instances: List[InstanceConfig] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()


def load_instances(settings: Settings | None = None) -> List[InstanceConfig]:
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
