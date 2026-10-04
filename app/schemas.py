"""Response models.

LESSON: these classes ARE your API documentation. FastAPI turns them into the OpenAPI
schema that RapidAPI shows customers, so field names and descriptions are product copy.
Every section has a `status`, so one failing data source never sinks the whole report.
"""
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "unavailable", "not_applicable"]


class Section(BaseModel):
    status: Status = Field(description="`ok`, `unavailable` (source down, retry later) or `not_applicable` (no data for this place).")
    source: str
    message: str | None = None


class Location(BaseModel):
    query: str | None = Field(None, description="The address you sent, if any.")
    matched_address: str | None = Field(None, description="The address as the US Census geocoder normalized it.")
    latitude: float
    longitude: float
    state_fips: str
    county_fips: str = Field(description="5-digit state+county FIPS code, e.g. `06037`.")
    county_name: str


class SeismicSection(Section):
    reference: str | None = Field(None, description="Design standard, e.g. `ASCE7-22`.")
    site_class: str | None = None
    risk_category: str | None = None
    ss: float | None = Field(None, description="Mapped MCER spectral acceleration, short period (g).")
    s1: float | None = Field(None, description="Mapped MCER spectral acceleration, 1-second period (g).")
    sms: float | None = None
    sm1: float | None = None
    sds: float | None = Field(None, description="Design spectral acceleration, short period (g).")
    sd1: float | None = Field(None, description="Design spectral acceleration, 1-second period (g). `null` when the standard requires a site-specific study.")
    pga_m: float | None = Field(None, description="Site-modified peak ground acceleration (g).")
    tl: float | None = Field(None, description="Long-period transition period (s).")
    seismic_design_category: str | None = Field(None, description="`null` when the standard requires a site-specific study (see `notes`).")
    notes: list[str] = []


class FloodSection(Section):
    mapped: bool | None = Field(None, description="`false` when no FEMA flood zone polygon covers the point (often unmapped or open water).")
    flood_zone: str | None = Field(None, description="FEMA zone: A, AE, AH, AO, V, VE, X, D ...")
    zone_subtype: str | None = None
    in_special_flood_hazard_area: bool | None = Field(None, description="`true` for the 1%-annual-chance floodplain, where flood insurance is mandatory for federally backed mortgages.")
    base_flood_elevation_ft: float | None = None


class ClimateSection(Section):
    iecc_climate_zone: int | None = Field(None, description="IECC climate zone 1 (hot) to 8 (subarctic).")
    iecc_moisture_regime: Literal["A", "B", "C"] | None = Field(None, description="A = humid, B = dry, C = marine.")
    building_america_zone: str | None = None


class RainfallSection(Section):
    depth_inches: dict[str, dict[str, float]] | None = Field(
        None,
        description="Design-storm rainfall depth in inches, keyed by duration then return period, e.g. `depth_inches['1h']['100yr']`.",
    )


class WildfireSection(Section):
    burn_probability_index: int | None = Field(None, description="USFS annual burn probability, as the raw scaled integer from the source raster (higher = more likely). 0 = none modeled.")
    conditional_risk_index: int | None = Field(None, description="USFS conditional risk to potential structures, raw scaled integer (higher = worse outcome if a fire occurs).")
    any_modeled_risk: bool | None = Field(None, description="`true` if either index is above zero.")


class SiteReport(BaseModel):
    location: Location
    seismic: SeismicSection | None = None
    flood: FloodSection | None = None
    climate: ClimateSection | None = None
    rainfall: RainfallSection | None = None
    wildfire: WildfireSection | None = None
    disclaimer: str = (
        "Informational screening data compiled from US government sources. It is not a substitute for "
        "a site-specific study, an official flood determination, or the requirements of the local building "
        "department. Have a licensed professional verify values before design or insurance decisions."
    )
