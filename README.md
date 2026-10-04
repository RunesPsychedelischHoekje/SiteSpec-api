# SiteSpec API

Site design and hazard criteria for any US address, in one call. Built with FastAPI.

```
GET /v1/site?address=1 Ocean Dr, Miami Beach, FL
```

Returns five sections, each with its own `status` (`ok`, `unavailable`, `not_applicable`):

| Section | Data | Source |
|---|---|---|
| `seismic` | ASCE 7-22 / 7-16 design values (Ss, S1, SDS, SD1, SDC, PGA) | USGS |
| `flood` | FEMA flood zone, floodplain flag, base flood elevation | FEMA NFHL |
| `climate` | IECC climate zone, moisture regime | PNNL/DOE (bundled CSV) |
| `rainfall` | Design-storm depths (15 min to 24 h, 2 to 100 yr) | NOAA Atlas 14 |
| `wildfire` | Burn probability and conditional risk (raw indexes) | USFS WRC 2024 |

Parameters: `address` or `lat`+`lon`; `include` (comma list); `seismic_reference`, `site_class`, `risk_category`.

## Run locally

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest              # tests use captured fixtures, no network
.venv/Scripts/fastapi dev app/main.py       # docs at http://127.0.0.1:8000/docs
```

**FEMA blocks non-US IP addresses.** Outside the US, use a US VPN for live runs (tests don't need one).
Deploy to a US region (`render.yaml` pins Oregon).

## How it works

- `app/clients/`: one small function per data source, all through `http.fetch` (retries, one error type).
- `app/services/site.py`: calls the sources concurrently with `asyncio.gather`; a failing source becomes `status: unavailable` instead of failing the request.
- `app/cache.py`: 24 h in-memory cache per location; a repeat request costs about 3 ms.
- `tests/fixtures/`: real responses captured from each service.

## Known limits (v1)

- NOAA Atlas 14 doesn't cover the Pacific Northwest (WA, OR, ID): `rainfall` returns `not_applicable` there.
- Wildfire indexes are raw scaled integers: the USFS service metadata doesn't document the scale, so they're not converted to probabilities.
- Wind and snow loads are not included: ASCE 7 values are licensed.
- Census geocoder only matches addresses it knows; new construction may need `lat`/`lon`.
