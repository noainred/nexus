"""FastAPI application entry point for the Nexus integrated manager."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .routers import (
    cleanup,
    content,
    downloads,
    instances,
    matrix,
    monitoring,
    repositories,
    security,
    tasks,
    topology,
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
