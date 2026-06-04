"""Shared dependencies: the instance registry and per-request client factory."""
from __future__ import annotations

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

    def compare_fields(self) -> List[str]:
        return list(self._compare_fields)

    def set_compare_fields(self, fields: List[str]) -> None:
        allowed = ["format", "type", "remote_url", "online"]
        self._compare_fields = [f for f in fields if f in allowed]
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
        save_instances(self.all(), self._group_order, self._compare_fields)

    def reload(self) -> None:
        doc = load_document()
        self._instances = {i.id: i for i in doc.instances}
        self._group_order = list(doc.group_order)
        self._compare_fields = list(doc.compare_fields)


# Singleton registry, initialised at import time from the configured file.
registry = InstanceRegistry(load_document())


def get_registry() -> InstanceRegistry:
    return registry


def get_client(instance_id: str) -> NexusClient:
    """Build a :class:`NexusClient` for the requested instance id."""
    instance = registry.get(instance_id)
    return NexusClient(instance, timeout=get_settings().request_timeout)
