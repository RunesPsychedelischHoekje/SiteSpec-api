"""Shared plumbing for calling government APIs.

LESSON: upstream services fail in boring ways (timeouts, 5xx, an error hidden inside a
200 response). Retry the transient ones, then raise ONE exception type so the rest of
the app doesn't care which agency broke.
"""
import asyncio
from collections.abc import Callable

import httpx

BACKOFF_S = 0.4  # module-level so tests can set it to 0


class UpstreamError(Exception):
    """The data source failed or answered garbage; the caller may retry later."""


class OutOfCoverage(Exception):
    """The data source works, but has no data for this place (e.g. outside the US)."""


class AddressNotFound(Exception):
    """The geocoder understood the request but found no matching address."""


async def fetch(
    http: httpx.AsyncClient,
    url: str,
    params: dict,
    *,
    retries: int = 2,
    bad: Callable[[httpx.Response], bool] = lambda r: False,
) -> httpx.Response:
    """GET with retries on network errors, 5xx, and responses the caller calls `bad`."""
    last = "unknown error"
    for attempt in range(retries + 1):
        if attempt:
            await asyncio.sleep(BACKOFF_S * attempt)
        try:
            r = await http.get(url, params=params)
        except httpx.HTTPError as e:
            last = type(e).__name__
            continue
        if r.status_code < 500 and not bad(r):
            return r
        last = f"HTTP {r.status_code}"
    raise UpstreamError(f"{httpx.URL(url).host}: {last}")


def arcgis_error(r: httpx.Response) -> bool:
    """ArcGIS servers often return HTTP 200 with {"error": {...}} as the body."""
    return r.status_code >= 400 or b'"error"' in r.content[:60]
