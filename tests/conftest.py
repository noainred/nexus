"""Shared test fixtures."""
from __future__ import annotations

import pytest

from app.config import InstanceConfig


@pytest.fixture
def instance() -> InstanceConfig:
    return InstanceConfig(
        id="test",
        name="Test Nexus",
        base_url="https://nexus.test",
        username="admin",
        password="secret",
        verify_tls=True,
    )
