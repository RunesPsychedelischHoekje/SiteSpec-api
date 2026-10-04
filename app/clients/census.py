"""US Census geocoder: address -> coordinates + county (free, no key).

The county FIPS code is the join key for county-level tables such as IECC climate zones.
"""
import httpx

from app.clients.http import AddressNotFound, OutOfCoverage, UpstreamError, fetch

BASE = "https://geocoding.geo.census.gov/geocoder/geographies"
COMMON = {"benchmark": "Public_AR_Current", "vintage": "Current_Current", "layers": "Counties", "format": "json"}


def _county(geographies: dict) -> dict:
    counties = geographies.get("Counties") or []
    if not counties:
        raise OutOfCoverage("The point is not inside a US county.")
    c = counties[0]
    return {"state_fips": c["STATE"], "county_fips": c["STATE"] + c["COUNTY"], "county_name": c["NAME"]}


async def geocode_address(http: httpx.AsyncClient, address: str) -> dict:
    r = await fetch(http, f"{BASE}/onelineaddress", {**COMMON, "address": address})
    if r.status_code != 200:
        raise UpstreamError(f"census geocoder: HTTP {r.status_code}")
    matches = r.json().get("result", {}).get("addressMatches", [])
    if not matches:
        raise AddressNotFound(address)
    m = matches[0]
    return {
        "matched_address": m["matchedAddress"],
        "latitude": m["coordinates"]["y"],
        "longitude": m["coordinates"]["x"],
        **_county(m["geographies"]),
    }


async def locate_point(http: httpx.AsyncClient, lat: float, lon: float) -> dict:
    r = await fetch(http, f"{BASE}/coordinates", {**COMMON, "x": lon, "y": lat})
    if r.status_code != 200:
        raise UpstreamError(f"census geocoder: HTTP {r.status_code}")
    geos = r.json().get("result", {}).get("geographies", {})
    return {"matched_address": None, "latitude": lat, "longitude": lon, **_county(geos)}
