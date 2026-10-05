"""The site report endpoint.

LESSON: `Annotated[..., Query(...)]` declares and validates query parameters. FastAPI rejects
bad input with a 422 before your code runs, and the same declarations feed the OpenAPI docs.
"""
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.cache import TTLCache
from app.clients.http import AddressNotFound, OutOfCoverage, UpstreamError
from app.schemas import SiteReport
from app.security import verify_rapidapi
from app.services.site import ALL_SECTIONS, build_report

router = APIRouter(prefix="/v1", tags=["Site"], dependencies=[Depends(verify_rapidapi)])


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


def get_cache(request: Request) -> TTLCache:
    return request.app.state.cache


@router.get(
    "/site",
    operation_id="get_site_report",  # otherwise FastAPI derives an ugly id: site_report_v1_site_get
    summary="Site report: seismic, flood, climate, rainfall, wildfire",
    responses={
        404: {"description": "No matching US address found."},
        422: {"description": "Invalid input, or the coordinates are outside the United States."},
        502: {"description": "The address geocoder is not responding. Retry shortly, or send lat/lon."},
    },
)
async def site_report(
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    cache: Annotated[TTLCache, Depends(get_cache)],
    address: Annotated[str | None, Query(min_length=5, max_length=200, description="US street address, e.g. `200 N Spring St, Los Angeles, CA`. Use this OR lat/lon.")] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90, description="Latitude (WGS84). Use with `lon`. If you send both an address and coordinates, the coordinates are used.")] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180, description="Longitude (WGS84). Use with `lat`.")] = None,
    include: Annotated[str, Query(description="Comma-separated sections to return. Fewer sections = faster. Options: seismic, flood, climate, rainfall, wildfire.")] = ",".join(ALL_SECTIONS),
    seismic_reference: Annotated[Literal["asce7-22", "asce7-16"], Query(description="Design standard for the seismic values.")] = "asce7-22",
    site_class: Annotated[Literal["A", "B", "BC", "C", "CD", "D", "DE", "E"], Query(description="Soil site class. `D` is the standard default when soil is unknown. BC/CD/DE exist only in ASCE 7-22.")] = "D",
    risk_category: Annotated[Literal["I", "II", "III", "IV"], Query(description="Building risk category (II = typical buildings).")] = "II",
) -> SiteReport:
    """One call returns the site design and hazard criteria that normally take five separate lookups.

    All data comes from US government sources; each section reports its own `status`, so a slow
    source never blocks the rest. Provide an `address`, or `lat` and `lon`.
    """
    if (lat is None) != (lon is None):
        raise HTTPException(422, "Provide both `lat` and `lon`.")
    if lat is None and address is None:
        raise HTTPException(422, "Provide `address`, or both `lat` and `lon`.")
    if lat is not None:
        address = None  # coordinates win: the API playground pre-fills an example address

    wanted = tuple(s.strip().lower() for s in include.split(",") if s.strip())
    unknown = [s for s in wanted if s not in ALL_SECTIONS]
    if unknown or not wanted:
        raise HTTPException(422, f"Unknown section(s) {unknown}. Valid: {', '.join(ALL_SECTIONS)}.")
    if seismic_reference == "asce7-16" and site_class in ("BC", "CD", "DE"):
        raise HTTPException(422, "Site classes BC, CD and DE exist only in ASCE 7-22.")

    try:
        return await build_report(
            http, cache, address=address, lat=lat, lon=lon, include=wanted,
            seismic_reference=seismic_reference, site_class=site_class, risk_category=risk_category,
        )
    except AddressNotFound:
        raise HTTPException(404, "No matching US address found. Check spelling, or use lat/lon.")
    except OutOfCoverage as e:
        raise HTTPException(422, f"{e} This API covers the United States.")
    except UpstreamError:
        raise HTTPException(502, "The US Census geocoder is not responding. Try again shortly, or use lat/lon.")
