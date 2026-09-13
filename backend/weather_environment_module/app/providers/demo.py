"""
Demo provider.

Generates realistic, clearly-labelled synthetic environmental data for the
North Eastern Region so the whole platform can be demonstrated offline,
without internet access or API credentials (DEMO_MODE=true).

The synthetic rainfall series is deterministic (seeded by lat/lon/day) but
varies over time to tell a believable story for a SIH demo:
    low rainfall -> increasing rainfall -> persistent rainfall
    -> high accumulation -> elevated environmental concern

It NEVER claims a landslide will occur - it only produces the same kind of
raw observations a real provider would, so the rest of the pipeline
(features, indicators, quality, API) can be exercised end-to-end.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
from typing import List

from app.models.schemas import (
    CurrentWeather,
    DataSourceType,
    ForecastPoint,
    ForecastResponse,
    HistoricalWeatherPoint,
    HistoricalWeatherResponse,
    Location,
    SourceMetadata,
)
from app.providers.base import WeatherDataProvider


def _seed(latitude: float, longitude: float) -> int:
    key = f"{round(latitude, 3)}:{round(longitude, 3)}".encode()
    return int(hashlib.sha256(key).hexdigest(), 16) % (2**32)


def _hourly_rainfall(hours_from_now: int, seed: int) -> float:
    """
    Deterministic synthetic hourly rainfall (mm) for a given offset from
    "now" (negative = past, positive = future).

    Story arc over a 10-day window:
      day -9..-6 : light/no rain
      day -5..-3 : increasing rainfall
      day -2..0  : persistent, heavy rainfall (demo "high concern" phase)
      day +1..+2 : forecast continues moderate/heavy rain, then tapers
    """
    day_offset = hours_from_now / 24.0
    rng_component = math.sin((hours_from_now + seed % 97) * 0.37) * 0.5 + 0.5  # 0..1 pseudo-noise

    if day_offset < -6:
        base = 0.2
    elif day_offset < -3:
        base = 1.5 + (day_offset + 6) * -0.8  # ramps up
    elif day_offset < 0:
        base = 6.0 + rng_component * 4.0  # persistent heavy phase
    elif day_offset < 2:
        base = 4.0 + rng_component * 3.0  # forecast continues, tapering
    else:
        base = 0.5

    # Only "rains" roughly 55% of hours even in wet phases, for realism.
    is_raining = ((hours_from_now * 31 + seed) % 100) < (80 if 0 <= day_offset < 3 else 55)
    return round(max(base, 0.0) * rng_component, 2) if is_raining else 0.0


class DemoProvider(WeatherDataProvider):
    name = "demo"
    reliability = 0.30  # synthetic - intentionally low reliability score

    async def get_current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        seed = _seed(latitude, longitude)
        now = datetime.now(timezone.utc)
        rainfall = _hourly_rainfall(0, seed)
        temp = 22.0 + 4.0 * math.sin(seed % 360 * math.pi / 180)
        rh = 70.0 + 15.0 * (1 if rainfall > 2 else 0)
        return CurrentWeather(
            location=Location(latitude=latitude, longitude=longitude),
            observation_timestamp=now,
            rainfall_mm_last_hour=rainfall,
            temperature_c=round(temp, 1),
            relative_humidity_pct=round(min(rh, 98.0), 1),
            soil_moisture_m3m3=round(0.25 + min(rainfall / 20.0, 0.25), 3),
            source=SourceMetadata(
                provider=DataSourceType.DEMO,
                reliability=self.reliability,
                is_fallback=True,
                fetched_at=now,
                notes="Synthetic demo data - not a real observation.",
            ),
        )

    async def get_historical_weather(
        self, latitude: float, longitude: float, start: datetime, end: datetime
    ) -> HistoricalWeatherResponse:
        seed = _seed(latitude, longitude)
        now = datetime.now(timezone.utc)
        points: List[HistoricalWeatherPoint] = []
        cursor = start
        while cursor <= end:
            hours_from_now = int((cursor - now).total_seconds() // 3600)
            rainfall = _hourly_rainfall(hours_from_now, seed)
            points.append(
                HistoricalWeatherPoint(
                    timestamp=cursor,
                    rainfall_mm=rainfall,
                    temperature_c=round(22.0 + 4.0 * math.sin((seed + hours_from_now) % 360 * math.pi / 180), 1),
                    relative_humidity_pct=round(min(70.0 + (15.0 if rainfall > 2 else 0.0), 98.0), 1),
                    soil_moisture_m3m3=round(0.25 + min(rainfall / 20.0, 0.25), 3),
                )
            )
            cursor += timedelta(hours=1)

        return HistoricalWeatherResponse(
            location=Location(latitude=latitude, longitude=longitude),
            start=start,
            end=end,
            points=points,
            source=SourceMetadata(
                provider=DataSourceType.DEMO,
                reliability=self.reliability,
                is_fallback=True,
                fetched_at=now,
                notes="Synthetic demo data - not a real observation.",
            ),
        )

    async def get_forecast(self, latitude: float, longitude: float, hours_ahead: int = 48) -> ForecastResponse:
        seed = _seed(latitude, longitude)
        now = datetime.now(timezone.utc)
        points: List[ForecastPoint] = []
        for h in range(1, hours_ahead + 1):
            rainfall = _hourly_rainfall(h, seed)
            points.append(
                ForecastPoint(
                    timestamp=now + timedelta(hours=h),
                    rainfall_mm=rainfall,
                    temperature_c=round(22.0 + 4.0 * math.sin((seed + h) % 360 * math.pi / 180), 1),
                    relative_humidity_pct=round(min(70.0 + (15.0 if rainfall > 2 else 0.0), 98.0), 1),
                )
            )
        return ForecastResponse(
            location=Location(latitude=latitude, longitude=longitude),
            generated_at=now,
            points=points,
            source=SourceMetadata(
                provider=DataSourceType.DEMO,
                reliability=self.reliability,
                is_fallback=True,
                fetched_at=now,
                notes="Synthetic demo data - not a real observation.",
            ),
        )

    async def get_soil_moisture(self, latitude: float, longitude: float) -> float:
        seed = _seed(latitude, longitude)
        rainfall = _hourly_rainfall(0, seed)
        return round(0.25 + min(rainfall / 20.0, 0.25), 3)
