"""IECC climate zone by county, from a bundled CSV (PNNL/DOE data, 3,234 counties).

LESSON: static reference data that never changes belongs in a file loaded once at startup,
not behind a network call. lru_cache turns the load into a one-time cost.
"""
import csv
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "iecc_climate_zones.csv"


@lru_cache
def _table() -> dict[str, dict[str, str]]:
    with DATA.open(newline="", encoding="utf-8") as f:
        return {row["State FIPS"] + row["County FIPS"]: row for row in csv.DictReader(f)}


def climate_for_county(county_fips: str) -> dict | None:
    row = _table().get(county_fips)
    if row is None:
        return None
    moisture = row["IECC Moisture Regime"]
    return {
        "iecc_climate_zone": int(row["IECC Climate Zone"]),
        "iecc_moisture_regime": moisture if moisture in ("A", "B", "C") else None,
        "building_america_zone": row["BA Climate Zone"],
    }
