"""FEMA National Flood Hazard Layer: which flood zone is a point in?

FEMA's ArcGIS server blocks non-US IPs and sporadically returns {"error": {"code": 400}}
under load, so `fetch` retries those. No key needed.
"""
import httpx

from app.clients.http import UpstreamError, arcgis_error, fetch

URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"  # layer 28 = Flood Hazard Zones


async def fetch_flood(http: httpx.AsyncClient, lat: float, lon: float) -> dict | None:
    """Return the zone's attributes, or None if the point is not inside any mapped zone."""
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
        "returnGeometry": "false",
        "f": "json",
    }
    r = await fetch(http, URL, params, retries=3, bad=arcgis_error)
    try:
        features = r.json()["features"]
    except (ValueError, KeyError) as e:
        raise UpstreamError("fema: unexpected response shape") from e
    if not features:
        return None
    # A point on a zone boundary can hit two polygons; prefer the Special Flood Hazard Area.
    features.sort(key=lambda f: f["attributes"].get("SFHA_TF") != "T")
    return features[0]["attributes"]
