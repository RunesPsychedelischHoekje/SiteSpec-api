"""App settings, loaded from environment variables (and a local .env file).

LESSON: same pattern as PromptShield: pydantic-settings reads and type-checks env vars.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SiteSpec API"
    version: str = "0.1.0"
    # RapidAPI adds this shared secret to every request it forwards (X-RapidAPI-Proxy-Secret).
    # Empty = check disabled (local dev).
    rapidapi_proxy_secret: str = ""
    # Goes into our User-Agent so the agencies we call can identify (and contact) us.
    contact: str = "sitespec-api"
    # Seconds to wait for any single upstream call before giving up on it.
    upstream_timeout_s: float = 12.0
    # Site data (flood maps, hazard grids) changes rarely, so a day of caching is safe.
    cache_ttl_s: int = 86400
    cache_max_entries: int = 20000


@lru_cache
def get_settings() -> Settings:
    return Settings()
