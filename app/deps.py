"""Shared dependencies: the instance registry and per-request client factory."""

from typing import Dict, List

from fastapi import HTTPException

from .config import (
    InstanceConfig,
    InstancesDocument,
    get_settings,
    load_document,
    save_instances,
)
from .nexus_client import NexusClient


class InstanceRegistry:
    """In-memory registry of managed instances keyed by id.

    Mutations are persisted back to the YAML file so changes survive restarts.
    Insertion order is preserved so the dashboard column order is stable.
    """

    def __init__(self, document: InstancesDocument) -> None:
        self._instances: Dict[str, InstanceConfig] = {
            i.id: i for i in document.instances
        }
        self._group_order: List[str] = list(document.group_order)
        self._compare_fields: List[str] = list(document.compare_fields)
        self._ping_interval: float = document.ping_interval
        self._ping_warn_pct: float = document.ping_warn_pct
        self._ping_crit_pct: float = document.ping_crit_pct
        self._backup_enabled: bool = document.backup_enabled
        self._backup_time: str = document.backup_time
        self._backup_keep: int = document.backup_keep
        self._backup_path: str = document.backup_path
        self._sync_jobs: List[dict] = [dict(j) for j in document.sync_jobs]

    def sync_jobs(self) -> List[dict]:
        return [dict(j) for j in self._sync_jobs]

    def set_sync_jobs(self, jobs: List[dict]) -> None:
        self._sync_jobs = [dict(j) for j in jobs]
        self._persist()

    def backup_config(self) -> dict:
        return {
            "enabled": self._backup_enabled,
            "time": self._backup_time,
            "keep": self._backup_keep,
            "path": self._backup_path,
        }

    def set_backup_config(self, enabled: bool, time: str, keep: int, path: str = "") -> None:
        self._backup_enabled = bool(enabled)
        self._backup_time = (time or "02:00").strip()
        self._backup_keep = max(1, int(keep))
        self._backup_path = (path or "").strip()
        self._persist()

    def compare_fields(self) -> List[str]:
        return list(self._compare_fields)

    def set_compare_fields(self, fields: List[str]) -> None:
        allowed = ["format", "type", "remote_url", "online"]
        self._compare_fields = [f for f in fields if f in allowed]
        self._persist()

    def ping_interval(self) -> float:
        return self._ping_interval

    def ping_config(self) -> dict:
        return {
            "interval": self._ping_interval,
            "warn_pct": self._ping_warn_pct,
            "crit_pct": self._ping_crit_pct,
        }

    def set_ping_config(self, interval: float, warn_pct: float, crit_pct: float) -> None:
        self._ping_interval = max(10.0, float(interval))
        self._ping_warn_pct = max(0.0, float(warn_pct))
        self._ping_crit_pct = max(self._ping_warn_pct, float(crit_pct))
        self._persist()

    def all(self) -> List[InstanceConfig]:
        return list(self._instances.values())

    def group_order(self) -> List[str]:
        """Saved group order, plus any present-but-unordered groups appended."""
        present = []
        for inst in self._instances.values():
            g = (inst.group or "").strip()
            if g and g not in present:
                present.append(g)
        ordered = [g for g in self._group_order if g in present]
        extra = sorted(g for g in present if g not in ordered)
        return ordered + extra

    def set_group_order(self, order: List[str]) -> None:
        self._group_order = [g for g in order if g]
        self._persist()

    def monitoring(self) -> List[InstanceConfig]:
        return [i for i in self._instances.values() if i.use_in_monitoring]

    def comparison(self) -> List[InstanceConfig]:
        return [i for i in self._instances.values() if i.use_in_comparison]

    def get(self, instance_id: str) -> InstanceConfig:
        try:
            return self._instances[instance_id]
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"Unknown instance: {instance_id!r}"
            )

    def add(self, config: InstanceConfig) -> None:
        if config.id in self._instances:
            raise HTTPException(
                status_code=409, detail=f"Instance id already exists: {config.id!r}"
            )
        self._instances[config.id] = config
        self._persist()

    def update(self, instance_id: str, config: InstanceConfig) -> None:
        if instance_id not in self._instances:
            raise HTTPException(
                status_code=404, detail=f"Unknown instance: {instance_id!r}"
            )
        # Replace in place, preserving column order (id stays the same).
        self._instances[instance_id] = config
        self._persist()

    def remove(self, instance_id: str) -> None:
        if instance_id not in self._instances:
            raise HTTPException(
                status_code=404, detail=f"Unknown instance: {instance_id!r}"
            )
        del self._instances[instance_id]
        self._persist()

    def set_reference(self, instance_id: str) -> None:
        if instance_id not in self._instances:
            raise HTTPException(
                status_code=404, detail=f"Unknown instance: {instance_id!r}"
            )
        for key, cfg in self._instances.items():
            cfg.is_reference = key == instance_id
        self._persist()

    def clear_reference(self) -> None:
        for cfg in self._instances.values():
            cfg.is_reference = False
        self._persist()

    def replace_all(self, instances: List[InstanceConfig]) -> None:
        self._instances = {i.id: i for i in instances}
        self._persist()

    def merge(self, instances: List[InstanceConfig]) -> None:
        for i in instances:
            self._instances[i.id] = i  # upsert by id
        self._persist()

    def _persist(self) -> None:
        save_instances(
            self.all(),
            self._group_order,
            self._compare_fields,
            self.ping_config(),
            self.backup_config(),
            self._sync_jobs,
        )

    def reload(self) -> None:
        doc = load_document()
        self._instances = {i.id: i for i in doc.instances}
        self._group_order = list(doc.group_order)
        self._compare_fields = list(doc.compare_fields)
        self._ping_interval = doc.ping_interval
        self._ping_warn_pct = doc.ping_warn_pct
        self._ping_crit_pct = doc.ping_crit_pct
        self._backup_enabled = doc.backup_enabled
        self._backup_time = doc.backup_time
        self._backup_keep = doc.backup_keep
        self._backup_path = doc.backup_path
        self._sync_jobs = [dict(j) for j in doc.sync_jobs]


# Singleton registry, initialised at import time from the configured file.
registry = InstanceRegistry(load_document())


def get_registry() -> InstanceRegistry:
    return registry


def get_client(instance_id: str) -> NexusClient:
    """Build a :class:`NexusClient` for the requested instance id."""
    instance = registry.get(instance_id)
    return NexusClient(instance, timeout=get_settings().request_timeout)
