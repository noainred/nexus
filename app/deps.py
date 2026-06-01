"""Shared dependencies: the instance registry and per-request client factory."""
from __future__ import annotations

from typing import Dict, List

from fastapi import HTTPException

from .config import InstanceConfig, get_settings, load_instances
from .nexus_client import NexusClient


class InstanceRegistry:
    """In-memory registry of managed instances keyed by id."""

    def __init__(self, instances: List[InstanceConfig]) -> None:
        self._instances: Dict[str, InstanceConfig] = {i.id: i for i in instances}

    def all(self) -> List[InstanceConfig]:
        return list(self._instances.values())

    def get(self, instance_id: str) -> InstanceConfig:
        try:
            return self._instances[instance_id]
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"Unknown instance: {instance_id!r}"
            )

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
