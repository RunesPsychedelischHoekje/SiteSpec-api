"""Builds a site report by calling every data source at once.

LESSON: `asyncio.gather` runs the upstream calls concurrently, so the report takes as long as
the SLOWEST source instead of the sum of all of them. Each source is wrapped in `_section`,
which turns exceptions into a status field: the report always comes back, with whatever worked.
"""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.cache import TTLCache
from app.clients import census, fema, noaa, usfs, usgs
from app.clients.http import OutOfCoverage, UpstreamError
from app.schemas import (
    ClimateSection, FloodSection, Location, RainfallSection, SeismicSection, SiteReport, WildfireSection,
)
from app.services.climate import climate_for_county

ALL_SECTIONS = ("seismic", "flood", "climate", "rainfall", "wildfire")
SECTION_TIMEOUT_S = 25.0
RAIN_DURATIONS = ("15m", "1h", "6h", "24h")
RAIN_RETURN_YEARS = (2, 10, 25, 100)

SOURCES = {
    "seismic": "USGS Seismic Design Web Services",
    "flood": "FEMA National Flood Hazard Layer",
    "climate": "PNNL/DOE IECC climate zones by county",
    "rainfall": "NOAA Atlas 14 (partial duration series)",
    "wildfire": "USFS Wildfire Risk to Communities 2024",
}


def _key(kind: str, lat: float, lon: float, *extra: str) -> tuple:
    # 5 decimals is about 1 metre: fine enough that flood-zone boundaries aren't blurred.
    return (kind, round(lat, 5), round(lon, 5), *extra)


async def _cached(cache: TTLCache, key: tuple, fetcher: Callable[[], Awaitable[Any]]) -> Any:
    hit = cache.get(key)
    if hit is not None:
        return hit[0]  # wrapped in a tuple so a cached None ("no flood zone here") still counts as a hit
    value = await fetcher()
    cache.set(key, (value,))
    return value


async def _section(name: str, model: type, build: Callable[[], Awaitable[dict]]):
    """Run one source; map failures to a status instead of raising."""
    source = SOURCES[name]
    try:
        async with asyncio.timeout(SECTION_TIMEOUT_S):
            return model(status="ok", source=source, **await build())
    except OutOfCoverage as e:
        return model(status="not_applicable", source=source, message=str(e))
    except (UpstreamError, TimeoutError) as e:
        return model(status="unavailable", source=source, message=f"Data source did not respond ({e}). Try again shortly.")


async def build_report(
    http: httpx.AsyncClient,
    cache: TTLCache,
    *,
    address: str | None,
    lat: float | None,
    lon: float | None,
    include: tuple[str, ...],
    seismic_reference: str,
    site_class: str,
    risk_category: str,
) -> SiteReport:
    # Step 1: resolve the location (cached by address text, or by point).
    if address:
        loc = await _cached(cache, ("addr", address.strip().lower()), lambda: census.geocode_address(http, address))
    else:
        loc = await _cached(cache, _key("pt", lat, lon), lambda: census.locate_point(http, lat, lon))
    la, lo = loc["latitude"], loc["longitude"]

    # Step 2: every requested section, concurrently.
    async def seismic() -> dict:
        key = _key("seismic", la, lo, seismic_reference, site_class, risk_category)
        d = await _cached(cache, key, lambda: usgs.fetch_seismic(http, la, lo, seismic_reference, site_class, risk_category))
        notes = [d[k] for k in ("fa_note", "fv_note", "fpga_note") if d.get(k)]
        return {
            "reference": seismic_reference.upper(), "site_class": site_class, "risk_category": risk_category,
            "ss": d.get("ss"), "s1": d.get("s1"), "sms": d.get("sms"), "sm1": d.get("sm1"),
            "sds": d.get("sds"), "sd1": d.get("sd1"), "pga_m": d.get("pgam"), "tl": d.get("tl"),
            "seismic_design_category": d.get("sdc"), "notes": notes,
        }

    async def flood() -> dict:
        attrs = await _cached(cache, _key("flood", la, lo), lambda: fema.fetch_flood(http, la, lo))
        if attrs is None:
            return {"mapped": False}
        bfe = attrs.get("STATIC_BFE")
        return {
            "mapped": True,
            "flood_zone": attrs.get("FLD_ZONE"),
            "zone_subtype": attrs.get("ZONE_SUBTY"),
            "in_special_flood_hazard_area": attrs.get("SFHA_TF") == "T",
            "base_flood_elevation_ft": bfe if bfe not in (None, -9999, -9999.0) else None,
        }

    async def climate() -> dict:
        found = climate_for_county(loc["county_fips"])
        if found is None:
            raise OutOfCoverage(f"No climate zone on file for county {loc['county_fips']}.")
        return found

    async def rainfall() -> dict:
        rows = await _cached(cache, _key("rain", la, lo), lambda: noaa.fetch_rainfall(http, la, lo))
        depth = {
            d: {f"{y}yr": rows[noaa.DURATIONS.index(d)][noaa.RETURN_YEARS.index(y)] for y in RAIN_RETURN_YEARS}
            for d in RAIN_DURATIONS
        }
        return {"depth_inches": depth}

    async def wildfire() -> dict:
        v = await _cached(cache, _key("fire", la, lo), lambda: usfs.fetch_wildfire(http, la, lo))
        if all(x is None for x in v.values()):
            raise OutOfCoverage("USFS has no wildfire raster data at this location.")
        return {**v, "any_modeled_risk": any((x or 0) > 0 for x in v.values())}

    jobs = {
        "seismic": (SeismicSection, seismic), "flood": (FloodSection, flood), "climate": (ClimateSection, climate),
        "rainfall": (RainfallSection, rainfall), "wildfire": (WildfireSection, wildfire),
    }
    wanted = [n for n in ALL_SECTIONS if n in include]
    results = await asyncio.gather(*(_section(n, jobs[n][0], jobs[n][1]) for n in wanted))

    return SiteReport(
        location=Location(query=address, **loc),
        **dict(zip(wanted, results)),
    )
