"""Async client for the Sonatype Nexus Repository Manager 3 REST API.

Each method maps to one or more endpoints under ``/service/rest/v1`` and
returns plain dictionaries / typed models. Network and HTTP-status errors are
normalised into :class:`NexusError` so routers can translate them uniformly.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from .config import InstanceConfig
from .models import (
    BlobStore,
    CleanupPolicy,
    Component,
    ComponentPage,
    Repository,
)


class NexusError(Exception):
    """Raised when a Nexus REST call fails.

    ``status_code`` is the upstream HTTP status when available, otherwise
    ``None`` for connection/transport level failures.
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NexusClient:
    """Thin async wrapper around one Nexus instance's REST API."""

    def __init__(self, instance: InstanceConfig, timeout: float = 15.0) -> None:
        self.instance = instance
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        verify = True if self.instance.verify_tls is None else self.instance.verify_tls
        return httpx.AsyncClient(
            base_url=self.instance.api_root,
            auth=(self.instance.username, self.instance.password),
            timeout=self._timeout,
            verify=verify,
            headers={"Accept": "application/json"},
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with self._client() as client:
                response = await client.request(method, path, **kwargs)
        except httpx.InvalidURL as exc:  # malformed base_url in instances.yaml
            raise NexusError(
                f"Invalid base_url '{self.instance.base_url}': {exc}"
            ) from exc
        except httpx.HTTPError as exc:  # connection refused, DNS, timeout, TLS...
            raise NexusError(f"Connection error: {exc}") from exc

        if response.status_code >= 400:
            raise NexusError(
                f"Nexus returned {response.status_code} for {method} {path}: "
                f"{response.text[:300]}",
                status_code=response.status_code,
            )
        return response

    # -- Status / monitoring ------------------------------------------------

    async def ping(self) -> dict[str, Any]:
        """Return reachability + latency + per-subsystem health.

        Uses the read-only ``/status`` endpoint (writable instances) and the
        detailed ``/status/check`` endpoint when the account can read it.
        """
        start = time.perf_counter()
        # /status returns 200 with empty body when the instance can serve reads.
        await self._request("GET", "/status")
        elapsed_ms = (time.perf_counter() - start) * 1000

        checks: dict[str, bool] = {}
        try:
            resp = await self._request("GET", "/status/check")
            data = resp.json()
            for subsystem, payload in data.items():
                if isinstance(payload, dict) and "healthy" in payload:
                    checks[subsystem] = bool(payload["healthy"])
        except NexusError:
            # /status/check requires extra privileges; absence is not fatal.
            checks = {}

        return {"response_ms": round(elapsed_ms, 1), "checks": checks}

    async def list_blobstores(self) -> list[BlobStore]:
        resp = await self._request("GET", "/blobstores")
        result: list[BlobStore] = []
        for item in resp.json():
            result.append(
                BlobStore(
                    name=item.get("name", "unknown"),
                    type=item.get("type"),
                    total_size_bytes=item.get("totalSizeInBytes"),
                    available_space_bytes=item.get("availableSpaceInBytes"),
                    blob_count=item.get("blobCount"),
                )
            )
        return result

    # -- Repositories -------------------------------------------------------

    async def list_repositories(self) -> list[Repository]:
        resp = await self._request("GET", "/repositories")
        repos: list[Repository] = []
        for item in resp.json():
            repos.append(
                Repository(
                    name=item.get("name", "unknown"),
                    format=item.get("format"),
                    type=item.get("type"),
                    url=item.get("url"),
                    online=item.get("attributes", {}).get("online", item.get("online")),
                    attributes=item.get("attributes", {}),
                )
            )
        return repos

    async def delete_repository(self, name: str) -> None:
        await self._request("DELETE", f"/repositories/{name}")

    # -- Components ---------------------------------------------------------

    async def list_components(
        self, repository: str, continuation_token: Optional[str] = None
    ) -> ComponentPage:
        params: dict[str, str] = {"repository": repository}
        if continuation_token:
            params["continuationToken"] = continuation_token
        resp = await self._request("GET", "/components", params=params)
        data = resp.json()
        items = [
            Component(
                id=item["id"],
                repository=item.get("repository"),
                group=item.get("group"),
                name=item.get("name"),
                version=item.get("version"),
                format=item.get("format"),
            )
            for item in data.get("items", [])
        ]
        return ComponentPage(
            items=items, continuation_token=data.get("continuationToken")
        )

    async def delete_component(self, component_id: str) -> None:
        await self._request("DELETE", f"/components/{component_id}")

    # -- Cleanup policies ---------------------------------------------------
    #
    # Cleanup policies live under the "beta" REST namespace in Nexus 3. We try
    # v1 first and fall back to the beta path for older releases.

    async def list_cleanup_policies(self) -> list[CleanupPolicy]:
        data = await self._cleanup_get("")
        policies: list[CleanupPolicy] = []
        for item in data or []:
            policies.append(
                CleanupPolicy(
                    name=item.get("name", "unknown"),
                    format=item.get("format", "*"),
                    notes=item.get("notes"),
                    mode=item.get("mode", "delete"),
                    criteria=item.get("criteria", {}),
                )
            )
        return policies

    async def create_cleanup_policy(self, payload: dict[str, Any]) -> None:
        await self._cleanup_post("", payload)

    async def _cleanup_get(self, suffix: str) -> Any:
        try:
            resp = await self._request("GET", f"/cleanup-policies{suffix}")
        except NexusError as exc:
            if exc.status_code == 404:
                resp = await self._request_beta("GET", f"/cleanup-policies{suffix}")
            else:
                raise
        return resp.json()

    async def _cleanup_post(self, suffix: str, payload: dict[str, Any]) -> None:
        try:
            await self._request("POST", f"/cleanup-policies{suffix}", json=payload)
        except NexusError as exc:
            if exc.status_code == 404:
                await self._request_beta(
                    "POST", f"/cleanup-policies{suffix}", json=payload
                )
            else:
                raise

    async def _request_beta(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Issue a request against the legacy ``/service/rest/beta`` namespace."""
        beta_root = self.instance.base_url.rstrip("/") + "/service/rest/beta"
        verify = True if self.instance.verify_tls is None else self.instance.verify_tls
        try:
            async with httpx.AsyncClient(
                base_url=beta_root,
                auth=(self.instance.username, self.instance.password),
                timeout=self._timeout,
                verify=verify,
                headers={"Accept": "application/json"},
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.InvalidURL as exc:
            raise NexusError(
                f"Invalid base_url '{self.instance.base_url}': {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise NexusError(f"Connection error: {exc}") from exc
        if response.status_code >= 400:
            raise NexusError(
                f"Nexus returned {response.status_code} for {method} {path}",
                status_code=response.status_code,
            )
        return response
