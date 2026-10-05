"""LESSON: we never call the real government servers in tests (slow, flaky, and FEMA blocks
non-US IPs). Instead httpx.MockTransport answers each request with a response we captured
from the real service, saved in tests/fixtures. `dependency_overrides` swaps the app's HTTP
client for the fake one: the exact payoff of passing dependencies in rather than hard-coding them.
Run with: pytest
"""
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cache import TTLCache
from app.clients import http as http_mod
from app.clients.noaa import parse_atlas14
from app.config import Settings, get_settings
from app.main import app
from app.routers.site import get_cache, get_http
from app.services.climate import climate_for_county

FX = Path(__file__).parent / "fixtures"


def fixture(name: str) -> httpx.Response:
    path = FX / name
    if name.endswith(".json"):
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))
    return httpx.Response(200, text=path.read_text(encoding="utf-8"))


class FakeUpstream:
    """Routes requests to fixtures and counts calls per host."""

    def __init__(self, fema_failures: int = 0, noaa_fixture: str = "noaa_la.txt", fema_fixture: str = "fema_la.json"):
        self.calls: dict[str, int] = {}
        self.fema_failures = fema_failures
        self.noaa_fixture = noaa_fixture
        self.fema_fixture = fema_fixture

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        self.calls[host] = self.calls.get(host, 0) + 1
        q = request.url.params
        if host == "geocoding.geo.census.gov":
            if "onelineaddress" in path:
                return fixture("census_address_nomatch.json" if "Zzyzx" in q["address"] else "census_address.json")
            return fixture("census_coords.json")
        if host == "earthquake.usgs.gov":
            return fixture("usgs_asce7-16.json" if "asce7-16" in path else "usgs_asce7-22.json")
        if host == "hazards.fema.gov":
            if self.fema_failures > 0:
                self.fema_failures -= 1
                return httpx.Response(200, json={"error": {"code": 400, "message": "Failed to execute query.", "details": []}})
            return fixture(self.fema_fixture)
        if host == "hdsc.nws.noaa.gov":
            return fixture(self.noaa_fixture)
        if host == "imagery.geoplatform.gov":
            value = "396" if "ConditionalRisk" in path else "2"
            return httpx.Response(200, json={"objectId": 0, "name": "Pixel", "value": value})
        return httpx.Response(404)


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(http_mod, "BACKOFF_S", 0)


def make_client(upstream: FakeUpstream) -> TestClient:
    fake_http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    cache = TTLCache(60, 100)  # one object per test; a lambda default would be copied on every request
    app.dependency_overrides[get_http] = lambda: fake_http
    app.dependency_overrides[get_cache] = lambda: cache
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    app.dependency_overrides.clear()


ADDRESS = {"address": "200 N Spring St, Los Angeles, CA"}


def test_full_report_by_address():
    client = make_client(FakeUpstream())
    r = client.get("/v1/site", params=ADDRESS)
    assert r.status_code == 200
    body = r.json()
    assert body["location"]["county_fips"] == "06037"
    assert body["location"]["matched_address"].startswith("200 S SPRING ST")
    assert body["seismic"]["status"] == "ok"
    assert body["seismic"]["reference"] == "ASCE7-22"
    assert body["seismic"]["sds"] is not None and body["seismic"]["seismic_design_category"] == "D"
    assert body["flood"] == {
        "status": "ok", "source": "FEMA National Flood Hazard Layer", "message": None, "mapped": True,
        "flood_zone": "X", "zone_subtype": "AREA OF MINIMAL FLOOD HAZARD",
        "in_special_flood_hazard_area": False, "base_flood_elevation_ft": None,
    }
    assert body["climate"]["iecc_climate_zone"] == 3 and body["climate"]["iecc_moisture_regime"] == "B"
    assert body["rainfall"]["depth_inches"]["1h"]["100yr"] == 1.64
    assert body["wildfire"]["any_modeled_risk"] is True
    assert "disclaimer" in body


def test_lat_lon_input():
    client = make_client(FakeUpstream())
    r = client.get("/v1/site", params={"lat": 34.05, "lon": -118.25, "include": "climate"})
    assert r.status_code == 200
    assert r.json()["location"]["matched_address"] is None
    assert r.json()["climate"]["iecc_climate_zone"] == 3


def test_include_limits_upstream_calls():
    up = FakeUpstream()
    client = make_client(up)
    body = client.get("/v1/site", params={**ADDRESS, "include": "climate"}).json()
    assert body["seismic"] is None and body["flood"] is None
    assert set(up.calls) == {"geocoding.geo.census.gov"}  # climate needs only the county


def test_flood_zone_with_base_flood_elevation():
    # Real FEMA answer for Miami Beach: zone AE, in the floodplain, base flood elevation 8 ft.
    client = make_client(FakeUpstream(fema_fixture="fema_miami.json"))
    flood = client.get("/v1/site", params={**ADDRESS, "include": "flood"}).json()["flood"]
    assert (flood["flood_zone"], flood["in_special_flood_hazard_area"], flood["base_flood_elevation_ft"]) == ("AE", True, 8.0)


def test_point_outside_any_flood_polygon():
    client = make_client(FakeUpstream(fema_fixture="fema_none.json"))
    flood = client.get("/v1/site", params={**ADDRESS, "include": "flood"}).json()["flood"]
    assert flood["status"] == "ok" and flood["mapped"] is False and flood["flood_zone"] is None


def test_fema_retry_recovers():
    up = FakeUpstream(fema_failures=2)  # fails twice, succeeds on the third try
    client = make_client(up)
    body = client.get("/v1/site", params={**ADDRESS, "include": "flood"}).json()
    assert body["flood"]["status"] == "ok"
    assert up.calls["hazards.fema.gov"] == 3


def test_fema_down_does_not_sink_report():
    client = make_client(FakeUpstream(fema_failures=99))
    body = client.get("/v1/site", params=ADDRESS).json()
    assert body["flood"]["status"] == "unavailable"
    assert "Try again" in body["flood"]["message"]
    assert body["seismic"]["status"] == "ok" and body["climate"]["status"] == "ok"


def test_rainfall_outside_noaa_coverage():
    client = make_client(FakeUpstream(noaa_fixture="noaa_nodata.txt"))
    body = client.get("/v1/site", params={**ADDRESS, "include": "rainfall"}).json()
    assert body["rainfall"]["status"] == "not_applicable"
    assert body["rainfall"]["depth_inches"] is None


def test_asce7_16_requires_site_specific_study():
    client = make_client(FakeUpstream())
    body = client.get("/v1/site", params={**ADDRESS, "include": "seismic", "seismic_reference": "asce7-16"}).json()
    assert body["seismic"]["sd1"] is None and body["seismic"]["seismic_design_category"] is None
    assert any("11.4.8" in n for n in body["seismic"]["notes"])


def test_second_request_is_served_from_cache():
    up = FakeUpstream()
    client = make_client(up)
    client.get("/v1/site", params=ADDRESS)
    first = dict(up.calls)
    client.get("/v1/site", params=ADDRESS)
    assert up.calls == first  # not one extra upstream call


def test_address_not_found():
    client = make_client(FakeUpstream())
    r = client.get("/v1/site", params={"address": "99999 Nowhere Blvd Zzyzx"})
    assert r.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {},  # neither address nor coordinates
        {"lat": 34.0},  # lon missing
        {"address": "200 N Spring St, Los Angeles", "lat": 34.0},  # lone lat, even with an address
        {"address": "200 N Spring St, Los Angeles", "include": "seismic,lava"},  # unknown section
        {"address": "200 N Spring St, Los Angeles", "seismic_reference": "asce7-16", "site_class": "BC"},
        {"address": "200 N Spring St, Los Angeles", "risk_category": "V"},
        {"lat": 95, "lon": 0},
    ],
)
def test_invalid_input_is_422(params):
    client = make_client(FakeUpstream())
    assert client.get("/v1/site", params=params).status_code == 422


def test_coordinates_win_over_prefilled_address():
    # The API playground pre-fills an example address; a user typing coordinates must still get theirs.
    client = make_client(FakeUpstream())
    body = client.get("/v1/site", params={**ADDRESS, "lat": 34.05, "lon": -118.25, "include": "climate"}).json()
    assert body["location"]["query"] is None and body["location"]["matched_address"] is None


@pytest.mark.parametrize("blank", ["{}", "", "null", "NaN", "undefined"])
def test_console_placeholders_are_ignored(blank):
    # RapidAPI's generated snippets send `lat={}&lon={}` for fields the user left empty.
    client = make_client(FakeUpstream())
    r = client.get("/v1/site", params={**ADDRESS, "lat": blank, "lon": blank, "include": "climate"})
    assert r.status_code == 200
    assert r.json()["location"]["matched_address"].startswith("200 S SPRING ST")


def test_blank_everything_still_asks_for_a_location():
    client = make_client(FakeUpstream())
    assert client.get("/v1/site", params={"address": "{}", "lat": "{}", "lon": "{}"}).status_code == 422


def test_openapi_is_console_friendly():
    spec = TestClient(app).get("/openapi.json").json()
    assert "/health" not in spec["paths"]
    op = spec["paths"]["/v1/site"]["get"]
    assert op["operationId"] == "get_site_report"
    params = {p["name"]: p for p in op["parameters"]}
    assert "x-rapidapi-proxy-secret" not in params
    for name in ("lat", "lon", "address"):
        s = params[name]["schema"]
        assert "anyOf" not in s and "default" not in s  # no "number | null", no "Default: NaN"
    assert params["lat"]["schema"]["type"] == "number"
    assert params["address"]["example"] == "200 N Spring St, Los Angeles, CA"


def test_rapidapi_proxy_secret_enforced():
    client = make_client(FakeUpstream())
    app.dependency_overrides[get_settings] = lambda: Settings(rapidapi_proxy_secret="s3cret")
    assert client.get("/v1/site", params=ADDRESS).status_code == 403
    ok = client.get("/v1/site", params=ADDRESS, headers={"X-RapidAPI-Proxy-Secret": "s3cret"})
    assert ok.status_code == 200


def test_health_is_open():
    assert TestClient(app).get("/health").json()["status"] == "ok"


def test_parse_atlas14_table_is_sane():
    rows = parse_atlas14((FX / "noaa_la.txt").read_text(encoding="utf-8"))
    assert len(rows) == 19 and all(len(r) == 10 for r in rows)
    # Rainfall depth must grow with return period (across) and with duration (down).
    assert all(r == sorted(r) for r in rows)
    assert all(rows[i][6] <= rows[i + 1][6] for i in range(18))


def test_climate_lookup():
    assert climate_for_county("06037")["iecc_climate_zone"] == 3
    assert climate_for_county("27031")["iecc_climate_zone"] == 7  # Cook County, MN
    assert climate_for_county("17031")["iecc_climate_zone"] == 5  # Cook County, IL
    assert climate_for_county("99999") is None
