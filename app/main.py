"""FastAPI application entry point for the Nexus integrated manager."""
from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path

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
from .routers.sync import run_loop as sync_run_loop
from .routers import (
    alerts,
    accounts,
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
    repositories,
    search,
    security,
    sync,
    tasks,
    topology,
    update,
)

STATIC_DIR = Path(__file__).parent / "static"


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run the background alert + ping + backup loops for the app's lifetime."""
    tasks = [
        asyncio.create_task(run_loop()),
        asyncio.create_task(ping_run_loop()),
        asyncio.create_task(backup_run_loop()),
        asyncio.create_task(sync_run_loop()),
        asyncio.create_task(disk_run_loop()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="Nexus Integrated Manager",
    description=(
        "Unified management dashboard for multiple Sonatype Nexus "
        "Repository Manager 3 instances: repositories, cleanup policies, "
        "and health monitoring."
    ),
    version=__version__,
    lifespan=lifespan,
)

# Auth gate + audit trail. Auth activates only when admin_password is set;
# every write (POST/PUT/DELETE) to /api is appended to the audit log.
_AUTH_EXEMPT = {"/api/login", "/api/auth-status"}

# Public read-only "service status" surface: even when a password is set, these
# GET endpoints stay open so a global health/monitoring view needs no login.
# Default-deny — anything not matched here (and every write) requires auth.
# Sensitive reads (credentials export, config dumps, audit, security posture,
# repo config, search/downloads) are deliberately NOT listed.
_PUBLIC_READ_RE = re.compile(
    r"^/api/(?:"
    r"status"
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
    r"|instances/[^/]+/(?:status|blobstores)"
    r")$"
)


def _is_public_read(method: str, path: str) -> bool:
    """A GET to an allowlisted status/monitoring endpoint needs no auth."""
    return method == "GET" and _PUBLIC_READ_RE.fullmatch(path) is not None


@app.middleware("http")
async def auth_and_audit(request: Request, call_next):
    settings = get_settings()
    path = request.url.path
    if (
        settings.admin_password
        and path.startswith("/api")
        and path not in _AUTH_EXEMPT
        and not _is_public_read(request.method, path)
        and not auth.is_authenticated(request, settings)
    ):
        # 'auth_required' marks this as the MANAGER login gate, so the SPA can
        # tell it apart from an upstream Nexus 401 (a managed instance with bad
        # credentials) and avoid wrongly popping the login overlay.
        return JSONResponse(
            {"detail": "로그인이 필요합니다.", "auth_required": True},
            status_code=401,
        )
    response = await call_next(request)
    if (
        request.method in ("POST", "PUT", "DELETE")
        and path.startswith("/api")
        and path not in ("/api/login", "/api/logout")
    ):
        try:
            auth.write_audit(settings, {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ip": request.client.host if request.client else "",
                "method": request.method,
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


@app.middleware("http")
async def no_cache_dashboard(request: Request, call_next):
    """Tell browsers to always revalidate the SPA assets.

    Without this, a cached app.js/style.css can keep showing an old UI after
    the code is updated. ETags still allow 304s, so this is cheap.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Liveness probe for the manager itself (not the Nexus instances)."""
    return {"status": "ok", "version": __version__}


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Serve the single-page dashboard assets.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
