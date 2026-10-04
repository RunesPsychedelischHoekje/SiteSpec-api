"""Application entry point: `fastapi dev app/main.py`.

LESSON: `lifespan` runs code once at startup and shutdown. We create ONE shared httpx client
here, so every request reuses open connections instead of paying a new TLS handshake to each
agency. Stored on `app.state`, it is handed to endpoints through a dependency (routers/site.py).
"""
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from app.cache import TTLCache
from app.config import get_settings
from app.routers import site

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.upstream_timeout_s),
        headers={"User-Agent": f"SiteSpecAPI/{settings.version} ({settings.contact})"},
        follow_redirects=True,
    )
    app.state.cache = TTLCache(settings.cache_ttl_s, settings.cache_max_entries)
    yield
    await app.state.http.aclose()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    description=(
        "**SiteSpec**: site design and hazard criteria for any US address, in one call. "
        "Seismic design values (ASCE 7-22 / 7-16), FEMA flood zone, IECC climate zone, NOAA design-storm "
        "rainfall, and wildfire exposure, combined from five US government sources. Each section reports "
        "its own status, so a slow source never blocks the rest.\n\n"
        "Screening data only: verify with a licensed professional and the local building department."
    ),
)
app.include_router(site.router)


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.2f}"
    return response


@app.get("/health", tags=["Meta"], summary="Liveness check")
def health() -> dict[str, str]:
    # Not behind the RapidAPI check, so your host's health checks can reach it.
    return {"status": "ok", "version": settings.version}
