"""Application entry point: `fastapi dev app/main.py`.

LESSON: `lifespan` runs code once at startup and shutdown. We create ONE shared httpx client
here, so every request reuses open connections instead of paying a new TLS handshake to each
agency. Stored on `app.state`, it is handed to endpoints through a dependency (routers/site.py).
"""
import time
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode

import httpx
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi

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

# What API consoles send for an empty optional field: RapidAPI's generated snippets use `{}`.
BLANK_VALUES = {"", "{}", "null", "none", "nan", "undefined"}
EXAMPLE_ADDRESS = "200 N Spring St, Los Angeles, CA"


@app.middleware("http")
async def drop_blank_query_values(request: Request, call_next):
    """Treat `?lat={}&lon=` like the parameter was never sent, instead of failing validation.

    LESSON: middleware can rewrite the request before routing. Here we strip blank-looking
    query values from the raw query string, so a customer who copies a console snippet unedited
    still gets an answer.
    """
    raw = request.scope.get("query_string", b"")
    if raw:
        pairs = parse_qsl(raw.decode(), keep_blank_values=True)
        kept = [(k, v) for k, v in pairs if v.strip().lower() not in BLANK_VALUES]
        if len(kept) != len(pairs):
            request.scope["query_string"] = urlencode(kept).encode()
    return await call_next(request)


def custom_openapi() -> dict:
    """FastAPI's default spec writes optional params as `number | null` with a null default,
    which RapidAPI renders as "Default: NaN". Collapse them to the plain type and add an example."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title, version=app.version, openapi_version=app.openapi_version,
        description=app.description, routes=app.routes,
    )
    for path in schema["paths"].values():
        for op in path.values():
            for param in op.get("parameters", []):
                s = param.get("schema", {})
                alternatives = [a for a in s.get("anyOf", []) if a.get("type") != "null"]
                if "anyOf" in s and len(alternatives) == 1:
                    del s["anyOf"]
                    s.update(alternatives[0])
                if "default" in s and s["default"] is None:
                    del s["default"]
                if param["name"] == "address":
                    param["example"] = s["example"] = EXAMPLE_ADDRESS  # pre-fills the API playground
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.2f}"
    return response


@app.get("/health", include_in_schema=False)  # for Render's health check only, not part of the public API docs
def health() -> dict[str, str]:
    # Not behind the RapidAPI check, so your host's health checks can reach it.
    return {"status": "ok", "version": settings.version}
