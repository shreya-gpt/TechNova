"""
Open-Meteo provider.

Open-Meteo (https://open-meteo.com) offers free, no-API-key weather
forecast and historical (ERA5-based) endpoints. It is used here as the
primary reliably-reachable provider for current weather, forecasts and
historical rainfall/temperature/humidity.

Endpoints used (documented at https://open-meteo.com/en/docs):
  - Forecast + current:  {OPEN_METEO_BASE_URL}/forecast
  - Historical (ERA5):   {OPEN_METEO_HISTORICAL_URL}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
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
from app.providers.base import ProviderError, WeatherDataProvider


class OpenMeteoProvider(WeatherDataProvider):
    name = "open_meteo"
    reliability = 0.85

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.settings = get_settings()
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self.settings.HTTP_TIMEOUT_SECONDS)

    async def _request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        owns_client = self._client is None
        client = await self._get_client()
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"open_meteo request failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def get_current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation",
            "timezone": "UTC",
        }
        data = await self._request(f"{self.settings.OPEN_METEO_BASE_URL}/forecast", params)
        current = data.get("current", {})
        ts_raw = current.get("time")
        ts = datetime.fromisoformat(ts_raw).replace(tzinfo=timezone.utc) if ts_raw else datetime.now(timezone.utc)

        return CurrentWeather(
            location=Location(latitude=latitude, longitude=longitude),
            observation_timestamp=ts,
            rainfall_mm_last_hour=current.get("precipitation"),
            temperature_c=current.get("temperature_2m"),
            relative_humidity_pct=current.get("relative_humidity_2m"),
            soil_moisture_m3m3=None,
            source=SourceMetadata(
                provider=DataSourceType.OPEN_METEO,
                reliability=self.reliability,
                fetched_at=datetime.now(timezone.utc),
            ),
        )

    async def get_historical_weather(
        self, latitude: float, longitude: float, start: datetime, end: datetime
    ) -> HistoricalWeatherResponse:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "hourly": "precipitation,temperature_2m,relative_humidity_2m,soil_moisture_0_to_7cm",
            "timezone": "UTC",
        }
        data = await self._request(self.settings.OPEN_METEO_HISTORICAL_URL, params)
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip = hourly.get("precipitation", [])
        temp = hourly.get("temperature_2m", [])
        rh = hourly.get("relative_humidity_2m", [])
        soil = hourly.get("soil_moisture_0_to_7cm", [])

        points: List[HistoricalWeatherPoint] = []
        for i, t in enumerate(times):
            points.append(
                HistoricalWeatherPoint(
                    timestamp=datetime.fromisoformat(t).replace(tzinfo=timezone.utc),
                    rainfall_mm=precip[i] if i < len(precip) else None,
                    temperature_c=temp[i] if i < len(temp) else None,
                    relative_humidity_pct=rh[i] if i < len(rh) else None,
                    soil_moisture_m3m3=soil[i] if i < len(soil) else None,
                )
            )

        return HistoricalWeatherResponse(
            location=Location(latitude=latitude, longitude=longitude),
            start=start,
            end=end,
            points=points,
            source=SourceMetadata(
                provider=DataSourceType.OPEN_METEO,
                reliability=self.reliability,
                fetched_at=datetime.now(timezone.utc),
            ),
        )

    async def get_forecast(self, latitude: float, longitude: float, hours_ahead: int = 48) -> ForecastResponse:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "precipitation,temperature_2m,relative_humidity_2m",
            "forecast_hours": min(max(hours_ahead, 1), 168),
            "timezone": "UTC",
        }
        data = await self._request(f"{self.settings.OPEN_METEO_BASE_URL}/forecast", params)
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip = hourly.get("precipitation", [])
        temp = hourly.get("temperature_2m", [])
        rh = hourly.get("relative_humidity_2m", [])

        points: List[ForecastPoint] = []
        for i, t in enumerate(times):
            points.append(
                ForecastPoint(
                    timestamp=datetime.fromisoformat(t).replace(tzinfo=timezone.utc),
                    rainfall_mm=precip[i] if i < len(precip) else None,
                    temperature_c=temp[i] if i < len(temp) else None,
                    relative_humidity_pct=rh[i] if i < len(rh) else None,
                )
            )

        return ForecastResponse(
            location=Location(latitude=latitude, longitude=longitude),
            generated_at=datetime.now(timezone.utc),
            points=points,
            source=SourceMetadata(
                provider=DataSourceType.OPEN_METEO,
                reliability=self.reliability,
                fetched_at=datetime.now(timezone.utc),
            ),
        )

    async def get_soil_moisture(self, latitude: float, longitude: float) -> Optional[float]:
        # Open-Meteo also exposes near-surface soil moisture via the forecast endpoint.
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "soil_moisture_0_to_7cm",
            "forecast_hours": 1,
            "timezone": "UTC",
        }
        try:
            data = await self._request(f"{self.settings.OPEN_METEO_BASE_URL}/forecast", params)
        except ProviderError:
            return None
        values = data.get("hourly", {}).get("soil_moisture_0_to_7cm", [])
        return values[0] if values else None
