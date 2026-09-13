"""
weather_adapter.py
===================
BRIDGE between the Weather & Environmental Data microservice (built by the
weather/hydrology teammate) and the central risk-engine schema (schemas.py).

Why this file exists:
    The weather module runs as its OWN FastAPI service and returns a rich
    RiskFeatureResponse (rainfall_24h_mm, rainfall_72h_mm, soil_moisture_m3m3,
    forecast_rainfall_24h_mm, data quality flags, etc.).
    The risk engine's pipeline expects a much simpler schemas.EnvironmentalData
    (rainfall_24h, rainfall_72h, forecast_rainfall, soil_moisture as a 0-100
    percentage). This file calls the weather service over HTTP and converts
    one into the other, in ONE place.

Prerequisite:
    The weather_environment_module service must be running separately, e.g.:
        cd weather_environment_module
        uvicorn app.main:app --reload --port 8001

Usage:
    from weather_adapter import get_environment_for_location

    env = get_environment_for_location(latitude=27.30, longitude=92.40)
    # env is now a schemas.EnvironmentalData, ready to plug into
    # RiskAnalysisRequest(environment=env, ...)
"""

from __future__ import annotations

from typing import Optional

import requests

from schemas import EnvironmentalData

# Base URL of the weather/environmental microservice. Change the port here
# (or override via an env var) if your teammate's service runs elsewhere.
WEATHER_SERVICE_BASE_URL = "http://localhost:8001"


def _soil_moisture_m3m3_to_pct(value: Optional[float]) -> Optional[float]:
    """
    Convert volumetric soil water content (m3/m3, typically ~0.05-0.5) into
    an approximate 0-100 "percent saturation" figure that schemas.EnvironmentalData
    expects.

    NOTE: this is a simplification. True saturation percentage = water content
    / soil porosity, and porosity varies by soil type (~0.4-0.6 typical). We
    don't have per-location porosity yet, so we approximate porosity as 0.5.
    This is good enough for a prototype/demo; flag it for later calibration
    once real soil-type data is available.
    """
    if value is None:
        return None
    assumed_porosity = 0.5
    pct = (value / assumed_porosity) * 100
    return max(0.0, min(100.0, round(pct, 1)))


def get_environment_for_location(
    latitude: float,
    longitude: float,
    timeout_seconds: float = 10.0,
) -> EnvironmentalData:
    """
    Call the weather/environmental microservice for a single coordinate and
    package the result as a schemas.EnvironmentalData for the risk pipeline.

    Raises requests.RequestException if the weather service is unreachable —
    callers should catch this and decide whether to fall back to mock data
    (see mock_data.py) rather than crash the whole pipeline.
    """
    response = requests.get(
        f"{WEATHER_SERVICE_BASE_URL}/environment/risk-features",
        params={"latitude": latitude, "longitude": longitude},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()

    features = data["environmental_features"]

    rainfall_24h = features.get("rainfall_24h_mm")
    if rainfall_24h is None:
        # schemas.EnvironmentalData requires rainfall_24h — fail loudly rather
        # than silently guessing a number for a required safety-relevant field.
        raise ValueError(
            "Weather service did not return rainfall_24h_mm; cannot build "
            "EnvironmentalData without it."
        )

    return EnvironmentalData(
        rainfall_24h=rainfall_24h,
        rainfall_72h=features.get("rainfall_72h_mm"),
        forecast_rainfall=features.get("forecast_rainfall_24h_mm"),
        soil_moisture=_soil_moisture_m3m3_to_pct(features.get("soil_moisture_m3m3")),
    )


if __name__ == "__main__":
    # Quick manual check against a running weather service
    env = get_environment_for_location(latitude=27.30, longitude=92.40)
    print("Converted EnvironmentalData ready for the risk engine:")
    print(env.model_dump_json(indent=2))
