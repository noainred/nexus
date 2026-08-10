"""FastAPI application entry point for the Nexus integrated manager."""

import asyncio
import contextlib
import re
from pathlib import Path
from typing import Dict

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .alerts import run_loop
from .config import get_settings
from .pingmon import run_loop as ping_run_loop
from .backup import run_loop as backup_run_loop
from .diskmon import run_loop as disk_run_loop
from .statusmon import run_loop as status_run_loop
from .routers.sync import run_loop as sync_run_loop
from .routers import (
    alerts,
    accounts,
    accesslog,
    auth,
    backup,
    bulk,
    cleanup,
    content,
    downloads,
    infra,
    instances,
    matrix,
    meta,
    monitoring,
    musers,
    repositories,
    search,
    security,
    sync,
    tasks,
    topology,
    update,
)

STATIC_DIR = Path(__file__).parent / "static"


app = FastAPI(
    title="Nexus Integrated Manager",
    description=(
        "Unified management dashboard for multiple Sonatype Nexus "
        "Repository Manager 3 instances: repositories, cleanup policies, "
        "and health monitoring."
    ),
    version=__version__,
)

# Background loops via startup/shutdown events. (FastAPI 0.83 / Python 3.6 does
# not support the ASGI-lifespan context manager, so use on_event handlers.)
_bg_tasks: list = []


@app.on_event("startup")
async def _start_background_loops() -> None:
    """Run the background alert + ping + backup loops for the app's lifetime."""
    if not get_settings().admin_password:
        # Delivery safety: with no admin password the API accepts writes from
        # anyone who can reach the port. Make that loud in the server log so an
        # operator notices before exposing the manager.
        import logging
        logging.getLogger("uvicorn.error").warning(
            "보안 경고: 관리자 비밀번호(NEXUS_MANAGER_ADMIN_PASSWORD)가 설정되지 "
            "않았습니다. 이 경우 포트에 접근 가능한 누구나 변경 작업을 수행할 수 "
            "있습니다. 운영 환경에서는 .env에 비밀번호를 반드시 설정하세요."
        )
    _bg_tasks.extend([
        asyncio.create_task(run_loop()),
        asyncio.create_task(ping_run_loop()),
        asyncio.create_task(backup_run_loop()),
        asyncio.create_task(sync_run_loop()),
        asyncio.create_task(disk_run_loop()),
        asyncio.create_task(status_run_loop()),
    ])


@app.on_event("shutdown")
async def _stop_background_loops() -> None:
    for task in _bg_tasks:
        task.cancel()
    for task in _bg_tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    _bg_tasks.clear()

# Auth gate + audit trail. Auth activates when a bootstrap password is set OR
# any named account exists; every write (POST/PUT/DELETE) to /api is appended to
# the audit log.
_AUTH_EXEMPT = {"/api/login", "/api/auth-status", "/api/me"}
# Writes any *authenticated* principal may perform (incl. a read-only viewer):
# logging out and changing one's own password.
_SELF_WRITE = {"/api/logout", "/api/me/password"}

# Public read-only "service status" surface: even when a password is set, these
# GET endpoints stay open so a global health/monitoring view needs no login.
# Default-deny — anything not matched here (and every write) requires auth.
# Sensitive reads (credentials export, config dumps, audit, security posture,
# repo config, search/downloads) are deliberately NOT listed.
_PUBLIC_READ_RE = re.compile(
    r"^/api/(?:"
    r"status"
    r"|summary"
    r"|topology"
    r"|proxy-status"
    r"|metrics"
    r"|blobstores"
    r"|disk-forecast"
    r"|disk-history"
    r"|ping-history"
    r"|alerts"
    r"|release-notes"
    r"|portal"
    r"|instances/group-order"
    r"|instances/topology-layout"
    r"|instances/[^/]+/(?:status|blobstores)"
    r")$"
)


def _is_public_read(method: str, path: str) -> bool:
    """A GET to an allowlisted status/monitoring endpoint needs no auth."""
    return method == "GET" and _PUBLIC_READ_RE.fullmatch(path) is not None


# Credential-exposing reads: admin-only. A read-only viewer must never pull
# plaintext server passwords via the instances export or a config-backup
# download (backup files embed instances.yaml). GETs, so not covered by the
# viewer write-block below.
_ADMIN_READ_RE = re.compile(
    r"^/api/(?:instances/export|backups/[^/]+/[^/]+)$"
)


@app.middleware("http")
async def auth_and_audit(request: Request, call_next):
    settings = get_settings()
    path = request.url.path
    method = request.method
    principal = None
    if auth.auth_enabled(settings) and path.startswith("/api") and path not in _AUTH_EXEMPT:
        principal = auth.current_principal(request, settings)
        if principal is None and not _is_public_read(method, path):
            # 'auth_required' marks this as the MANAGER login gate, so the SPA can
            # tell it apart from an upstream Nexus 401 (a managed instance with
            # bad credentials) and avoid wrongly popping the login overlay.
            return JSONResponse(
                {"detail": "로그인이 필요합니다.", "auth_required": True},
                status_code=401,
            )
        if principal is not None:
            # Account management is admin-only (covers reads too — the listing
            # exposes usernames/roles).
            if path.startswith("/api/manager-users") and principal.role != "admin":
                return JSONResponse(
                    {"detail": "관리자만 접근할 수 있습니다."}, status_code=403)
            # Credential-exposing downloads are admin-only (defeats the viewer's
            # read-only guarantee otherwise — plaintext passwords via GET).
            if (method == "GET" and principal.role != "admin"
                    and _ADMIN_READ_RE.fullmatch(path)):
                return JSONResponse(
                    {"detail": "관리자만 내려받을 수 있습니다(자격증명 포함)."},
                    status_code=403)
            # A viewer is read-only: block every write except self-service ones.
            if (principal.role == "viewer"
                    and method in ("POST", "PUT", "DELETE")
                    and path not in _SELF_WRITE):
                return JSONResponse(
                    {"detail": "조회 전용 계정입니다(변경 권한이 없습니다)."},
                    status_code=403)
    response = await call_next(request)
    if (
        method in ("POST", "PUT", "DELETE")
        and path.startswith("/api")
        and path not in ("/api/login", "/api/logout")
    ):
        try:
            auth.write_audit(settings, {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ip": request.client.host if request.client else "",
                "user": principal.username if principal else "",
                "method": method,
                "path": path,
                "query": str(request.url.query or ""),
                "status": response.status_code,
            })
        except Exception:  # noqa: BLE001 - auditing must never break a request
            pass
    return response


app.include_router(auth.router)
app.include_router(instances.router)
app.include_router(repositories.router)
app.include_router(cleanup.router)
app.include_router(monitoring.router)
app.include_router(matrix.router)
app.include_router(downloads.router)
app.include_router(accesslog.router)
app.include_router(tasks.router)
app.include_router(security.router)
app.include_router(content.router)
app.include_router(topology.router)
app.include_router(alerts.router)
app.include_router(infra.router)
app.include_router(sync.router)
app.include_router(search.router)
app.include_router(backup.router)
app.include_router(bulk.router)
app.include_router(cleanup.fleet_router)
app.include_router(meta.router)
app.include_router(update.router)
app.include_router(accounts.router)
app.include_router(musers.router)


# Hardening headers applied to every response. The SPA loads no CDN/inline
# scripts, so a strict CSP is safe; inline *style attributes* in the HTML need
# 'unsafe-inline' for style-src. frame-ancestors/X-Frame-Options block
# clickjacking; nosniff blocks MIME confusion.
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def no_cache_dashboard(request: Request, call_next):
    """Revalidate SPA assets + apply security response headers.

    Without no-cache, a cached app.js/style.css can keep showing an old UI
    after an update. ETags still allow 304s, so this is cheap.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path == "/ping" or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", _CSP)
    return response


@app.get("/healthz", tags=["meta"])
async def healthz() -> Dict[str, str]:
    """Liveness probe for the manager itself (not the Nexus instances)."""
    return {"status": "ok", "version": __version__}


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/ping", include_in_schema=False)
async def ping_page() -> FileResponse:
    """Standalone public 네트워크 Ping 상태 page — no login (reads the public
    /api/ping-history). Not under /api, so the auth middleware never gates it."""
    return FileResponse(STATIC_DIR / "ping.html")


# Serve the single-page dashboard assets.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
