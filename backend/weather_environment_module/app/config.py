"""
Central application configuration.

All tunables (thresholds, TTLs, decay factors, provider credentials) are
loaded here from environment variables so that nothing is hard-coded.

IMPORTANT: The default thresholds below (e.g. HEAVY_RAINFALL_MM_24H) are
PROTOTYPE DEFAULTS for a Smart India Hackathon demonstration. They are
*not* scientifically calibrated for any specific district and MUST be
locally calibrated (e.g. against IMD/GSI landslide advisories) before any
operational use.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Tuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------
    APP_NAME: str = "Weather & Environmental Data Module"
    ENV: str = Field(default="development")
    DEMO_MODE: bool = Field(default=True, description="Run fully offline with synthetic NER data")
    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------------
    # Provider credentials (optional; DEMO_MODE works without any of these)
    # ------------------------------------------------------------------
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"
    OPEN_METEO_HISTORICAL_URL: str = "https://archive-api.open-meteo.com/v1/archive"

    IMD_API_KEY: str = Field(default="", description="Optional. IMD data typically requires registration.")
    IMD_BASE_URL: str = Field(default="https://mausam.imd.gov.in", description="Reference only; IMD has no stable public JSON API.")

    NASA_POWER_BASE_URL: str = "https://power.larc.nasa.gov/api/temporal"
    NASA_EARTHDATA_TOKEN: str = Field(default="", description="Required for SMAP soil moisture via NASA Earthdata")

    # ------------------------------------------------------------------
    # HTTP behaviour
    # ------------------------------------------------------------------
    HTTP_TIMEOUT_SECONDS: float = 8.0
    HTTP_MAX_RETRIES: int = 2

    # ------------------------------------------------------------------
    # Caching TTLs (seconds)
    # ------------------------------------------------------------------
    CACHE_TTL_CURRENT_WEATHER: int = 15 * 60          # 15 minutes
    CACHE_TTL_FORECAST: int = 60 * 60                 # 1 hour
    CACHE_TTL_HISTORICAL: int = 24 * 60 * 60          # 24 hours
    CACHE_TTL_SOIL_MOISTURE: int = 3 * 60 * 60        # 3 hours

    # ------------------------------------------------------------------
    # Data quality / freshness
    # ------------------------------------------------------------------
    STALE_OBSERVATION_MINUTES: int = 180              # older than this => STALE flag
    MAX_REASONABLE_HOURLY_RAINFALL_MM: float = 300.0  # physically-implausible spike threshold
    MIN_LATITUDE: float = -90.0
    MAX_LATITUDE: float = 90.0

    # ------------------------------------------------------------------
    # North Eastern Region approximate bounding box
    # (APPROXIMATE ONLY - not authoritative administrative boundaries)
    # Covers Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram,
    # Nagaland, Sikkim, Tripura.
    # ------------------------------------------------------------------
    NER_BOUNDING_BOX: Tuple[float, float, float, float] = (21.5, 22.0, 29.5, 97.5)
    # (min_lat, min_lon, max_lat, max_lon)

    # ------------------------------------------------------------------
    # Antecedent Precipitation Index (API) decay factor
    # k in API_t = k * API_(t-1) + rainfall_t   (typical range 0.80 - 0.95)
    # ------------------------------------------------------------------
    API_DECAY_FACTOR: float = 0.90
    API_LOOKBACK_DAYS: int = 15

    # ------------------------------------------------------------------
    # Derived-indicator thresholds (PROTOTYPE DEFAULTS - calibrate locally)
    # ------------------------------------------------------------------
    HEAVY_RAINFALL_MM_24H: float = 100.0        # IMD "heavy rainfall" ballpark
    EXTREME_RAINFALL_MM_24H: float = 200.0      # IMD "extremely heavy" ballpark
    PERSISTENT_RAINFALL_HOURS: int = 12         # continuous rain hours
    PERSISTENT_RAINFALL_MIN_MM_PER_HOUR: float = 2.0
    HIGH_SOIL_MOISTURE_FRACTION: float = 0.40   # volumetric soil moisture (m3/m3)
    FORECAST_HEAVY_RAINFALL_MM_24H: float = 80.0
    RAINFALL_ANOMALY_HIGH_PERCENTILE: float = 90.0

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./data/environmental_data.db"

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    API_PREFIX: str = ""
    BATCH_MAX_ITEMS: int = 50
    BATCH_CONCURRENCY: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
