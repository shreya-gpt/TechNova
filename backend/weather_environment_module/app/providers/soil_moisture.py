"""
Soil moisture provider.

Real soil-moisture sources for a project like this would typically be:
  - NASA SMAP (via NASA Earthdata; requires an Earthdata login token), or
  - NASA POWER (https://power.larc.nasa.gov), which offers a free, no-key
    daily surface soil-wetness proxy at coarse (~0.5 deg) resolution.

This adapter uses NASA POWER as a realistically-accessible fallback source
for soil moisture, and documents how a team with SMAP/Earthdata access can
extend it. If NASA POWER is unreachable, get_soil_moisture returns None
and the quality layer records a MISSING_SOIL_MOISTURE flag - it never
fabricates a value.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.config import get_settings
from app.providers.base import ProviderError


class SoilMoistureProvider:
    name = "nasa_power"
    reliability = 0.65  # coarse resolution / proxy indicator, not SMAP-grade

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.settings = get_settings()
        self._client = client

    async def get_soil_moisture(self, latitude: float, longitude: float) -> Optional[float]:
        """
        Returns an approximate root-zone soil wetness fraction (0-1) using
        NASA POWER's GWETROOT parameter for the most recent available day,
        or None if unavailable.
        """
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.HTTP_TIMEOUT_SECONDS)

        end = datetime.now(timezone.utc).date() - timedelta(days=2)  # POWER has ~1-2 day latency
        start = end - timedelta(days=1)

        params = {
            "parameters": "GWETROOT",
            "community": "AG",
            "latitude": latitude,
            "longitude": longitude,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }
        try:
            resp = await client.get(f"{self.settings.NASA_POWER_BASE_URL}/daily/point", params=params)
            resp.raise_for_status()
            data = resp.json()
            values = data.get("properties", {}).get("parameter", {}).get("GWETROOT", {})
            if not values:
                return None
            latest_key = sorted(values.keys())[-1]
            val = values[latest_key]
            # NASA POWER uses -999 as a fill/missing value sentinel.
            if val is None or val < -900:
                return None
            return float(val)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ProviderError(f"soil moisture request failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()
