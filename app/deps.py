"""Shared dependencies: the instance registry and per-request client factory."""
from __future__ import annotations

from typing import Dict, List

from fastapi import HTTPException

from .config import (
    InstanceConfig,
    get_settings,
    load_instances,
    save_instances,
)
from .nexus_client import NexusClient


class InstanceRegistry:
    """In-memory registry of managed instances keyed by id.

    Mutations are persisted back to the YAML file so changes survive restarts.
    Insertion order is preserved so the dashboard column order is stable.
    """

    def __init__(self, instances: List[InstanceConfig]) -> None:
        self._instances: Dict[str, InstanceConfig] = {i.id: i for i in instances}

    def all(self) -> List[InstanceConfig]:
        return list(self._instances.values())

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

    def _persist(self) -> None:
        save_instances(self.all())

    def reload(self) -> None:
        self._instances = {i.id: i for i in load_instances()}


# Singleton registry, initialised at import time from the configured file.
registry = InstanceRegistry(load_instances())


def get_registry() -> InstanceRegistry:
    return registry


def get_client(instance_id: str) -> NexusClient:
    """Build a :class:`NexusClient` for the requested instance id."""
    instance = registry.get(instance_id)
    return NexusClient(instance, timeout=get_settings().request_timeout)
