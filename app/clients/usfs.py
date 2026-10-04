"""USFS Wildfire Risk to Communities (2024), via the federal geoplatform mirror.

The official apps.fs.usda.gov server returns 403; imagery.geoplatform.gov serves the same rasters.
Each raster is queried at a point with ArcGIS `identify`. Values are unlabeled scaled integers
(the service metadata does not state the scale), so we pass them through as raw indexes.
"""
import asyncio
import json

import httpx

from app.clients.http import UpstreamError, arcgis_error, fetch

BASE = "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WRC_{name}/ImageServer/identify"


async def _identify(http: httpx.AsyncClient, name: str, lat: float, lon: float) -> int | None:
    # The point must carry its spatial reference; bare "x,y" is read as Web Mercator meters.
    geometry = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
    params = {"geometry": geometry, "geometryType": "esriGeometryPoint", "returnGeometry": "false", "f": "json"}
    r = await fetch(http, BASE.format(name=name), params, bad=arcgis_error)
    try:
        value = r.json()["value"]
    except (ValueError, KeyError) as e:
        raise UpstreamError("usfs: unexpected response shape") from e
    return None if value == "NoData" else int(float(value))


async def fetch_wildfire(http: httpx.AsyncClient, lat: float, lon: float) -> dict[str, int | None]:
    burn, risk = await asyncio.gather(
        _identify(http, "BurnProbability", lat, lon),
        _identify(http, "ConditionalRiskToPotentialStructures", lat, lon),
    )
    return {"burn_probability_index": burn, "conditional_risk_index": risk}
