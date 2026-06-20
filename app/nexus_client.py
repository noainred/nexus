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
    Asset,
    AssetPage,
    BlobStore,
    CleanupPolicy,
    Component,
    ComponentPage,
    Repository,
    Task,
)


def _describe(exc: Exception) -> str:
    """Readable detail for an httpx error (timeouts often have empty str())."""
    if isinstance(exc, httpx.TimeoutException):
        return ("연결 시간 초과 — 매니저 호스트에서 서버에 닿지 못했습니다"
                " (주소·포트·방화벽/라우팅 확인)")
    if isinstance(exc, httpx.ConnectError):
        return ("연결 실패 — 주소·포트가 맞는지, 매니저 호스트에서 접근 가능한지"
                " 확인하세요 (포트 미개방/거부)")
    text = str(exc).strip()
    return text or type(exc).__name__


# The repository *format* reported by /repositories (e.g. "maven2") is not
# always the segment used by the typed admin endpoints (.../repositories/
# {format}/{type}/{name}). Map the known exceptions here.
_FORMAT_PATH_SEG = {"maven2": "maven"}


def _fmt_seg(fmt: str) -> str:
    return _FORMAT_PATH_SEG.get((fmt or "").lower(), fmt)


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
        # Cap the *connect* phase well below the overall timeout so an
        # unreachable host (wrong port / firewall DROP / different subnet)
        # fails in a few seconds instead of hanging the whole request_timeout.
        # The read timeout stays at self._timeout for legitimately slow Nexus.
        connect = min(self._timeout, 6.0)
        return httpx.AsyncClient(
            base_url=self.instance.api_root,
            auth=(self.instance.username, self.instance.password),
            timeout=httpx.Timeout(self._timeout, connect=connect),
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
            raise NexusError(f"Connection error: {_describe(exc)}") from exc

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

    async def server_version(self) -> Optional[str]:
        """Nexus version from the ``Server`` response header.

        Nexus answers e.g. ``Server: Nexus/3.68.0-04 (OSS)`` on the read-only
        ``/status`` endpoint. Returns None when a reverse proxy stripped the
        header or the node is unreachable — callers degrade gracefully (no
        version means "not scanned", never "safe").
        """
        try:
            resp = await self._request("GET", "/status")
        except NexusError:
            return None
        srv = (resp.headers.get("Server") or "").strip()
        if not srv:
            return None
        # Drop the "Nexus/" prefix for a cleaner display ("3.68.0-04 (OSS)").
        return srv[6:].strip() if srv.lower().startswith("nexus/") else srv

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

    async def list_repository_settings(self) -> list[dict[str, Any]]:
        """All repositories with full settings in one call (incl. cleanup).

        ``GET /repositorySettings`` (3.21+) returns every repo's config —
        much cheaper than fetching each repo's config individually.
        """
        resp = await self._request("GET", "/repositorySettings")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def repo_statuses(self) -> list[dict[str, Any]]:
        """Per-repository runtime status (online / 'Remote Auto Blocked' …).

        Uses the internal UI endpoint the Nexus web UI itself relies on —
        the public v1 API does not expose auto-block state. May 404 on some
        versions; callers should degrade gracefully.
        """
        url = self.instance.base_url.rstrip("/") + "/service/rest/internal/ui/repositories"
        verify = True if self.instance.verify_tls is None else self.instance.verify_tls
        try:
            async with httpx.AsyncClient(
                auth=(self.instance.username, self.instance.password),
                timeout=self._timeout,
                verify=verify,
                headers={"Accept": "application/json"},
            ) as client:
                resp = await client.get(url, params={"withAll": "true"})
        except httpx.HTTPError as exc:
            raise NexusError(f"Connection error: {_describe(exc)}") from exc
        if resp.status_code >= 400:
            raise NexusError(
                f"Nexus returned {resp.status_code} for internal repositories",
                status_code=resp.status_code,
            )
        data = resp.json()
        return data if isinstance(data, list) else []

    # -- Repository provisioning (speed-test infra) -------------------------

    async def create_raw_hosted(self, name: str, blob_store: str) -> None:
        """Create a raw(hosted) repository (idempotent-friendly via caller)."""
        payload = {
            "name": name,
            "online": True,
            "storage": {
                "blobStoreName": blob_store,
                "strictContentTypeValidation": False,
                "writePolicy": "ALLOW",
            },
        }
        await self._request("POST", "/repositories/raw/hosted", json=payload)

    async def create_raw_proxy(
        self,
        name: str,
        remote_url: str,
        blob_store: str,
        auth: Optional[tuple] = None,
    ) -> None:
        """Create a raw(proxy) repository pointing at ``remote_url``."""
        http_client: dict[str, Any] = {"blocked": False, "autoBlock": True}
        if auth:
            http_client["authentication"] = {
                "type": "username",
                "username": auth[0],
                "password": auth[1],
            }
        payload = {
            "name": name,
            "online": True,
            "storage": {
                "blobStoreName": blob_store,
                "strictContentTypeValidation": False,
            },
            "proxy": {
                "remoteUrl": remote_url,
                "contentMaxAge": 1440,
                "metadataMaxAge": 1440,
            },
            "negativeCache": {"enabled": False, "timeToLive": 1440},
            "httpClient": http_client,
        }
        await self._request("POST", "/repositories/raw/proxy", json=payload)

    async def upload_raw_content(self, repo: str, path: str, data: bytes) -> None:
        """PUT raw bytes to a hosted raw repo's content path."""
        base = self.instance.base_url.rstrip("/")
        url = f"{base}/repository/{repo}/{path.lstrip('/')}"
        verify = True if self.instance.verify_tls is None else self.instance.verify_tls
        try:
            async with httpx.AsyncClient(
                auth=(self.instance.username, self.instance.password),
                timeout=max(self._timeout, 120.0),
                verify=verify,
            ) as client:
                resp = await client.put(
                    url, content=data, headers={"Content-Type": "application/octet-stream"}
                )
        except httpx.HTTPError as exc:
            raise NexusError(f"Upload failed: {_describe(exc)}") from exc
        if resp.status_code >= 400:
            raise NexusError(
                f"Upload returned {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )

    async def get_repository_config(
        self, fmt: str, type_: str, name: str
    ) -> dict[str, Any]:
        """Return the full configuration for a single repository.

        Uses the admin endpoint ``/repositories/{format}/{type}/{name}`` which
        exposes storage, cleanup, proxy, negativeCache and httpClient settings
        used by the detailed cross-instance comparison.
        """
        resp = await self._request(
            "GET", f"/repositories/{_fmt_seg(fmt)}/{type_}/{name}"
        )
        return resp.json()

    # -- Configuration export ----------------------------------------------

    async def export_configuration(self) -> dict[str, Any]:
        """Collect the readable Nexus configuration into one JSON-able dict.

        Every section is best-effort: a section the account cannot read (or
        that the server version does not expose) is recorded under ``errors``
        instead of failing the whole export. Passwords are never returned by
        these read endpoints (Nexus redacts them), so the result is safe to
        store as a configuration snapshot/backup.
        """
        sections: dict[str, Any] = {}
        errors: dict[str, str] = {}

        async def grab(key: str, path: str) -> None:
            try:
                resp = await self._request("GET", path)
                sections[key] = resp.json()
            except NexusError as exc:
                errors[key] = exc.message

        # Simple single-call config sections.
        await grab("blobStores", "/blobstores")
        # Enrich file blob stores with their on-disk path/quota (the list view
        # omits it, but a restore needs it to recreate the store).
        if isinstance(sections.get("blobStores"), list):
            for bs in sections["blobStores"]:
                if isinstance(bs, dict) and (bs.get("type") or "").lower() == "file":
                    try:
                        resp = await self._request(
                            "GET", f"/blobstores/file/{bs.get('name')}"
                        )
                        bs["detail"] = resp.json()
                    except NexusError:
                        pass
        await grab("routingRules", "/routing-rules")
        await grab("anonymous", "/security/anonymous")
        await grab("users", "/security/users")
        await grab("roles", "/security/roles")
        await grab("privileges", "/security/privileges")
        await grab("contentSelectors", "/security/content-selectors")
        await grab("activeRealms", "/security/realms/active")
        await grab("tasks", "/tasks")

        # Cleanup policies live under v1 or the legacy beta namespace.
        try:
            sections["cleanupPolicies"] = await self._cleanup_get("")
        except NexusError as exc:
            errors["cleanupPolicies"] = exc.message

        # Repositories: list, then the full config for each one.
        repositories: list = []
        try:
            repos = await self.list_repositories()
        except NexusError as exc:
            errors["repositories"] = exc.message
            repos = []
        for repo in repos:
            fmt = (repo.format or "").strip()
            type_ = (repo.type or "").strip()
            entry: dict[str, Any] = {
                "name": repo.name,
                "format": repo.format,
                "type": repo.type,
                "url": repo.url,
                "online": repo.online,
            }
            if fmt and type_:
                try:
                    entry["config"] = await self.get_repository_config(
                        fmt, type_, repo.name
                    )
                except NexusError as exc:
                    entry["configError"] = exc.message
            repositories.append(entry)
        sections["repositories"] = repositories

        return {"sections": sections, "errors": errors}

    # -- Configuration restore (create from a snapshot) --------------------

    async def existing_names(self, path: str, key: str = "name") -> set:
        """Return the set of existing item names for a list endpoint."""
        try:
            resp = await self._request("GET", path)
        except NexusError:
            return set()
        data = resp.json()
        if not isinstance(data, list):
            return set()
        return {str(item.get(key)) for item in data if isinstance(item, dict)}

    async def create_blobstore_file(self, payload: dict[str, Any]) -> None:
        await self._request("POST", "/blobstores/file", json=payload)

    async def create_content_selector(self, payload: dict[str, Any]) -> None:
        await self._request("POST", "/security/content-selectors", json=payload)

    async def create_privilege(self, ptype: str, payload: dict[str, Any]) -> None:
        await self._request("POST", f"/security/privileges/{ptype}", json=payload)

    async def create_role(self, payload: dict[str, Any]) -> None:
        await self._request("POST", "/security/roles", json=payload)

    async def create_user(self, payload: dict[str, Any]) -> None:
        await self._request("POST", "/security/users", json=payload)

    async def change_password(self, user_id: str, new_password: str) -> None:
        """Change a user's password (Nexus expects the new password as a
        text/plain request body)."""
        await self._request(
            "PUT",
            f"/security/users/{user_id}/change-password",
            content=new_password.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )

    async def create_routing_rule(self, payload: dict[str, Any]) -> None:
        await self._request("POST", "/routing-rules", json=payload)

    async def create_repository(
        self, fmt: str, type_: str, payload: dict[str, Any]
    ) -> None:
        await self._request("POST", f"/repositories/{_fmt_seg(fmt)}/{type_}", json=payload)

    # -- Configuration restore: update existing (overwrite mode) -----------

    async def update_content_selector(self, name: str, payload: dict[str, Any]) -> None:
        await self._request("PUT", f"/security/content-selectors/{name}", json=payload)

    async def update_privilege(self, ptype: str, name: str, payload: dict[str, Any]) -> None:
        await self._request("PUT", f"/security/privileges/{ptype}/{name}", json=payload)

    async def update_role(self, role_id: str, payload: dict[str, Any]) -> None:
        await self._request("PUT", f"/security/roles/{role_id}", json=payload)

    async def update_user(self, user_id: str, payload: dict[str, Any]) -> None:
        await self._request("PUT", f"/security/users/{user_id}", json=payload)

    async def update_routing_rule(self, name: str, payload: dict[str, Any]) -> None:
        await self._request("PUT", f"/routing-rules/{name}", json=payload)

    async def update_repository(
        self, fmt: str, type_: str, name: str, payload: dict[str, Any]
    ) -> None:
        await self._request(
            "PUT", f"/repositories/{_fmt_seg(fmt)}/{type_}/{name}", json=payload
        )

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

    async def search_components(
        self, params: dict[str, str], max_pages: int = 5
    ) -> list[dict[str, Any]]:
        """Search components via /search, returning a few pages of matches."""
        out: list[dict[str, Any]] = []
        token: Optional[str] = None
        pages = 0
        while True:
            p = dict(params)
            if token:
                p["continuationToken"] = token
            resp = await self._request("GET", "/search", params=p)
            data = resp.json()
            for it in data.get("items", []):
                out.append({
                    "repository": it.get("repository"),
                    "format": it.get("format"),
                    "group": it.get("group"),
                    "name": it.get("name"),
                    "version": it.get("version"),
                })
            token = data.get("continuationToken")
            pages += 1
            if not token or pages >= max_pages:
                break
        return out

    # -- Assets (used for download usage) -----------------------------------

    async def list_assets(
        self, repository: str, continuation_token: Optional[str] = None
    ) -> AssetPage:
        """One page of assets, each carrying fileSize and lastDownloaded."""
        params: dict[str, str] = {"repository": repository}
        if continuation_token:
            params["continuationToken"] = continuation_token
        resp = await self._request("GET", "/assets", params=params)
        data = resp.json()
        items = [
            Asset(
                id=item["id"],
                path=item.get("path"),
                repository=item.get("repository"),
                format=item.get("format"),
                content_type=item.get("contentType"),
                file_size=item.get("fileSize"),
                last_downloaded=item.get("lastDownloaded"),
            )
            for item in data.get("items", [])
        ]
        return AssetPage(items=items, continuation_token=data.get("continuationToken"))

    # -- Metrics ------------------------------------------------------------

    async def get_metrics(self) -> dict[str, Any]:
        """Dropwizard metrics JSON from the (non-v1) /service/metrics endpoint.

        Requires the ``nx-metrics-all`` privilege. Tries the 3.81+ path first
        and falls back to the legacy path.
        """
        base = self.instance.base_url.rstrip("/")
        verify = True if self.instance.verify_tls is None else self.instance.verify_tls
        last_status: Optional[int] = None
        for path in ("/service/rest/metrics/data", "/service/metrics/data"):
            try:
                async with httpx.AsyncClient(
                    auth=(self.instance.username, self.instance.password),
                    timeout=self._timeout,
                    verify=verify,
                    headers={"Accept": "application/json"},
                ) as client:
                    resp = await client.get(base + path)
            except httpx.HTTPError as exc:
                raise NexusError(f"Connection error: {_describe(exc)}") from exc
            if resp.status_code < 400:
                return resp.json()
            last_status = resp.status_code
            if resp.status_code != 404:
                break
        raise NexusError(
            f"Metrics endpoint returned {last_status}", status_code=last_status
        )

    # -- Security -----------------------------------------------------------

    async def get_anonymous(self) -> dict[str, Any]:
        resp = await self._request("GET", "/security/anonymous")
        return resp.json()

    async def list_users(self) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/security/users")
        return resp.json()

    # -- Scheduled tasks ----------------------------------------------------

    async def list_tasks(self) -> list[Task]:
        resp = await self._request("GET", "/tasks")
        data = resp.json()
        tasks: list[Task] = []
        for item in data.get("items", []):
            state = item.get("currentState")
            tasks.append(
                Task(
                    id=item["id"],
                    name=item.get("name"),
                    type=item.get("type"),
                    message=item.get("message"),
                    current_state=state,
                    last_run_result=item.get("lastRunResult"),
                    last_run=item.get("lastRun"),
                    next_run=item.get("nextRun"),
                    runnable=state in (None, "WAITING"),
                    stoppable=state == "RUNNING",
                )
            )
        return tasks

    async def run_task(self, task_id: str) -> None:
        await self._request("POST", f"/tasks/{task_id}/run")

    async def stop_task(self, task_id: str) -> None:
        await self._request("POST", f"/tasks/{task_id}/stop")

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
            raise NexusError(f"Connection error: {_describe(exc)}") from exc
        if response.status_code >= 400:
            raise NexusError(
                f"Nexus returned {response.status_code} for {method} {path}",
                status_code=response.status_code,
            )
        return response
