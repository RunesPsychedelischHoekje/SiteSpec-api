"""NOAA Atlas 14 rainfall depths for design storms. Public domain, no key.

The service answers in a JavaScript-ish text format (`quantiles = [[...], ...];`), not JSON.
Rows are storm durations, columns are return periods (average recurrence interval).
"""
import ast
import re

import httpx

from app.clients.http import OutOfCoverage, UpstreamError, fetch

URL = "https://hdsc.nws.noaa.gov/cgi-bin/new/cgi_readH5.py"
DURATIONS = ["5m", "10m", "15m", "30m", "1h", "2h", "3h", "6h", "12h", "24h",
             "2d", "3d", "4d", "7d", "10d", "20d", "30d", "45d", "60d"]
RETURN_YEARS = [1, 2, 5, 10, 25, 50, 100, 200, 500, 1000]


def parse_atlas14(text: str) -> list[list[float]]:
    if "result = 'values'" not in text:
        # e.g. "Error 3.0: Selected location is not within a project area" (Pacific Northwest, outside US)
        raise OutOfCoverage("NOAA Atlas 14 does not cover this location.")
    m = re.search(r"quantiles\s*=\s*(\[\[.*?\]\])\s*;", text, re.S)
    if not m:
        raise UpstreamError("noaa: no quantiles in response")
    rows = [[float(v) for v in row] for row in ast.literal_eval(m.group(1))]
    if len(rows) != len(DURATIONS) or any(len(r) != len(RETURN_YEARS) for r in rows):
        raise UpstreamError("noaa: unexpected table shape")
    return rows


async def fetch_rainfall(http: httpx.AsyncClient, lat: float, lon: float) -> list[list[float]]:
    params = {"lat": lat, "lon": lon, "type": "pf", "data": "depth", "units": "english", "series": "pds"}
    r = await fetch(http, URL, params)
    if r.status_code != 200:
        raise UpstreamError(f"noaa: HTTP {r.status_code}")
    return parse_atlas14(r.text)
