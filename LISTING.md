# RapidAPI listing copy for SiteSpec

Paste each block into the matching field on the RapidAPI **General** tab.

## Name

```
SiteSpec: US Flood, Seismic, Climate & Rainfall Data by Address
```

## Category

Primary: **Real Estate** (proptech, inspection, and construction-tool developers browse here).
If Real Estate isn't offered or feels wrong, use **Data**. You can change it later without losing subscribers.

## Short description

```
Flood zone, seismic design values, IECC climate zone, design-storm rainfall and wildfire exposure for any US address in one API call.
```

## Tags

```
flood zone, FEMA, seismic, earthquake, ASCE 7, climate zone, IECC, rainfall, NOAA, wildfire, construction, building, real estate, hazard, geocoding
```

## Long description

(Markdown. Replace the host in the example with the one RapidAPI shows you.)

---

# SiteSpec: site design and hazard data for any US address

**Five lookups in one call.** Send an address (or coordinates) and get the flood zone, seismic design values, climate zone, design-storm rainfall, and wildfire exposure that normally take five separate trips to five government websites.

Built for tools that need *design* numbers, not just risk scores: home-addition and deck configurators, solar and roofing estimators, inspection reports, permit-prep tools, and proptech apps.

## What you get

| Section | What it returns | Source |
|---|---|---|
| `seismic` | ASCE 7-22 or 7-16 design values: SDS, SD1, Ss, S1, PGA, Seismic Design Category. Choose the site class and risk category. | USGS |
| `flood` | FEMA flood zone (AE, VE, X...), whether the point is in the Special Flood Hazard Area, base flood elevation | FEMA National Flood Hazard Layer |
| `climate` | IECC climate zone 1-8, moisture regime (humid, dry, marine) | PNNL / US DOE |
| `rainfall` | Design-storm depth in inches for 15 min, 1 h, 6 h and 24 h storms at 2, 10, 25 and 100-year return periods | NOAA Atlas 14 |
| `wildfire` | Burn-probability and conditional-risk indexes | USFS Wildfire Risk to Communities |

## Reliable by design

- **One bad source never breaks your response.** Every section carries its own `status`: `ok`, `unavailable` (source down, retry later) or `not_applicable` (no data for that place). You always get the sections that worked.
- **Request only what you need.** `include=flood,climate` skips the other lookups and returns faster.
- **Cached.** Repeat lookups for the same location are served from cache.
- **No database of lookups.** Results are held in a temporary in-memory cache (24 hours) and nothing is stored permanently.

## Example

```
GET /v1/site?address=1 Ocean Dr, Miami Beach, FL
```

```json
{
  "location": {
    "matched_address": "1 OCEAN DR, MIAMI BEACH, FL, 33139",
    "county_name": "Miami-Dade County",
    "county_fips": "12086"
  },
  "seismic":  { "status": "ok", "reference": "ASCE7-22", "site_class": "D", "sds": 0.043, "sd1": 0.029, "seismic_design_category": "A" },
  "flood":    { "status": "ok", "flood_zone": "AE", "in_special_flood_hazard_area": true, "base_flood_elevation_ft": 8.0 },
  "climate":  { "status": "ok", "iecc_climate_zone": 1, "iecc_moisture_regime": "A", "building_america_zone": "Hot-Humid" },
  "rainfall": { "status": "ok", "depth_inches": { "1h": { "100yr": 5.18 }, "24h": { "100yr": 14.0 } } },
  "wildfire": { "status": "ok", "burn_probability_index": 0, "conditional_risk_index": 0, "any_modeled_risk": false }
}
```

(Response shortened for display.)

## Quick start (Python)

```python
import requests

resp = requests.get(
    "https://sitespec.p.rapidapi.com/v1/site",
    headers={
        "X-RapidAPI-Key": "YOUR_RAPIDAPI_KEY",
        "X-RapidAPI-Host": "sitespec.p.rapidapi.com",
    },
    params={"address": "200 N Spring St, Los Angeles, CA"},
)
site = resp.json()
print(site["flood"]["flood_zone"], site["seismic"]["seismic_design_category"])
```

## Parameters

| Parameter | Description |
|---|---|
| `address` | US street address. Use this **or** `lat` + `lon`. |
| `lat`, `lon` | Coordinates (WGS84), for new construction or addresses the geocoder doesn't know. |
| `include` | Comma-separated sections: `seismic,flood,climate,rainfall,wildfire` (default: all). |
| `seismic_reference` | `asce7-22` (default) or `asce7-16`. |
| `site_class` | Soil class A, B, BC, C, CD, D, DE or E (default `D`, the usual choice when soil is unknown). |
| `risk_category` | I, II, III or IV (default II, typical buildings). |

## Use cases

- **Deck, addition and ADU configurators:** show required seismic category and flood constraints before the customer talks to a contractor.
- **Solar and roofing estimators:** pull climate zone and design-storm rainfall automatically.
- **Inspection and appraisal reports:** add flood zone and hazard sections without manual lookups.
- **Permit-prep tools:** pre-fill site criteria that permit applications ask for.
- **Insurance and lending workflows:** screen properties for flood and wildfire exposure.

## Good to know

- **United States only.** Addresses are matched with the US Census geocoder; coordinates must fall inside a US county.
- **Screening data, not a determination.** Values come from US government sources and are provided for informational screening. They are not a substitute for a site-specific study, an official flood determination, or your local building department's requirements. Have a licensed professional verify values before design or insurance decisions.
- **NOAA Atlas 14 does not cover WA, OR and ID**, so `rainfall` returns `not_applicable` there.
- **Wildfire values are raw indexes.** The USFS data doesn't document a unit scale, so we pass the integers through unchanged: use them for relative comparison (0 means none modeled), not as probabilities.
- **Wind and snow loads are not included** (ASCE 7 values are licensed).
- **ASCE 7-16 note:** for some sites the standard requires a site-specific study, in which case `sd1` and the Seismic Design Category are `null`, with an explanatory entry in `notes`.
- First lookup for a location typically takes 1-2 seconds; cached repeats are much faster.

Questions or a data type you'd like added? Open a thread in the **Discussions** tab.
