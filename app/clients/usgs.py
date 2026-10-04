"""USGS seismic design values (ASCE 7-16 / 7-22). Public domain, no key."""
import httpx

from app.clients.http import OutOfCoverage, UpstreamError, fetch

URL = "https://earthquake.usgs.gov/ws/building-codes/{reference}/calculate"


async def fetch_seismic(
    http: httpx.AsyncClient, lat: float, lon: float, reference: str, site_class: str, risk_category: str
) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "riskCategory": risk_category,
        "siteClass": site_class,
        "title": "SiteSpec",
    }
    r = await fetch(http, URL.format(reference=reference), params)
    if r.status_code >= 400:
        raise UpstreamError(f"usgs: HTTP {r.status_code}")
    body = r.json()
    if body.get("request", {}).get("status") != "success":
        # USGS answers 200 with status "error" for places it has no grid for.
        raise OutOfCoverage("USGS has no seismic design data for this location or parameter combination.")
    return body["response"]["data"]
