"""
Weather service.

Orchestrates the provider fallback chain:

    Primary (Open-Meteo) -> Secondary (IMD, if configured) -> Demo data

and applies caching so repeated requests for the same location within a
TTL window don't hit external APIs unnecessarily.

The rest of the application (API routes, environmental_service) depends
only on this service, never on a specific provider - so providers can be
added, removed, or reordered here without touching anything else.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from app.config import get_settings
from app.models.schemas import CurrentWeather, ForecastResponse, HistoricalWeatherResponse
from app.providers.base import ProviderError, ProviderUnavailableError, WeatherDataProvider
from app.providers.demo import DemoProvider
from app.providers.imd import IMDProvider
from app.providers.open_meteo import OpenMeteoProvider
from app.providers.soil_moisture import SoilMoistureProvider
from app.services.cache import current_weather_cache, forecast_cache, historical_cache, soil_moisture_cache

logger = logging.getLogger("weather_service")


class WeatherService:
    def __init__(self, providers: Optional[List[WeatherDataProvider]] = None):
        self.settings = get_settings()
        if providers is not None:
            self.providers = providers
        else:
            self.providers = [OpenMeteoProvider(), IMDProvider()]
        self.demo_provider = DemoProvider()
        self.soil_moisture_provider = SoilMoistureProvider()

    # ------------------------------------------------------------------
    # Current weather
    # ------------------------------------------------------------------
    async def get_current_weather(self, latitude: float, longitude: float) -> Tuple[CurrentWeather, bool, List[str]]:
        """Returns (result, used_fallback_or_demo, failure_log)."""
        cache_key = f"current:{round(latitude, 4)}:{round(longitude, 4)}"
        failures: List[str] = []

        if not self.settings.DEMO_MODE:
            cached = current_weather_cache.get(cache_key)
            if cached is not None:
                return cached, False, failures

            for provider in self.providers:
                try:
                    result = await provider.get_current_weather(latitude, longitude)
                    current_weather_cache.set(cache_key, result, self.settings.CACHE_TTL_CURRENT_WEATHER)
                    return result, False, failures
                except (ProviderError, ProviderUnavailableError) as exc:
                    logger.warning("Provider %s failed for current weather: %s", provider.name, exc)
                    failures.append(f"{provider.name}: {exc}")

        # DEMO_MODE or all real providers failed -> demo fallback.
        result = await self.demo_provider.get_current_weather(latitude, longitude)
        return result, True, failures

    # ------------------------------------------------------------------
    # Historical weather
    # ------------------------------------------------------------------
    async def get_historical_weather(
        self, latitude: float, longitude: float, start: datetime, end: datetime
    ) -> Tuple[HistoricalWeatherResponse, bool, List[str]]:
        cache_key = f"hist:{round(latitude, 4)}:{round(longitude, 4)}:{start.isoformat()}:{end.isoformat()}"
        failures: List[str] = []

        if not self.settings.DEMO_MODE:
            cached = historical_cache.get(cache_key)
            if cached is not None:
                return cached, False, failures

            for provider in self.providers:
                try:
                    result = await provider.get_historical_weather(latitude, longitude, start, end)
                    historical_cache.set(cache_key, result, self.settings.CACHE_TTL_HISTORICAL)
                    return result, False, failures
                except (ProviderError, ProviderUnavailableError) as exc:
                    logger.warning("Provider %s failed for historical weather: %s", provider.name, exc)
                    failures.append(f"{provider.name}: {exc}")

        result = await self.demo_provider.get_historical_weather(latitude, longitude, start, end)
        return result, True, failures

    # ------------------------------------------------------------------
    # Forecast
    # ------------------------------------------------------------------
    async def get_forecast(
        self, latitude: float, longitude: float, hours_ahead: int = 48
    ) -> Tuple[ForecastResponse, bool, List[str]]:
        cache_key = f"fc:{round(latitude, 4)}:{round(longitude, 4)}:{hours_ahead}"
        failures: List[str] = []

        if not self.settings.DEMO_MODE:
            cached = forecast_cache.get(cache_key)
            if cached is not None:
                return cached, False, failures

            for provider in self.providers:
                try:
                    result = await provider.get_forecast(latitude, longitude, hours_ahead)
                    forecast_cache.set(cache_key, result, self.settings.CACHE_TTL_FORECAST)
                    return result, False, failures
                except (ProviderError, ProviderUnavailableError) as exc:
                    logger.warning("Provider %s failed for forecast: %s", provider.name, exc)
                    failures.append(f"{provider.name}: {exc}")

        result = await self.demo_provider.get_forecast(latitude, longitude, hours_ahead)
        return result, True, failures

    # ------------------------------------------------------------------
    # Soil moisture
    # ------------------------------------------------------------------
    async def get_soil_moisture(self, latitude: float, longitude: float) -> Tuple[Optional[float], bool, List[str]]:
        cache_key = f"soil:{round(latitude, 4)}:{round(longitude, 4)}"
        failures: List[str] = []

        if not self.settings.DEMO_MODE:
            cached = soil_moisture_cache.get(cache_key)
            if cached is not None:
                return cached, False, failures

            try:
                value = await self.soil_moisture_provider.get_soil_moisture(latitude, longitude)
                if value is not None:
                    soil_moisture_cache.set(cache_key, value, self.settings.CACHE_TTL_SOIL_MOISTURE)
                    return value, False, failures
            except ProviderError as exc:
                logger.warning("Soil moisture provider failed: %s", exc)
                failures.append(f"soil_moisture_provider: {exc}")

        value = await self.demo_provider.get_soil_moisture(latitude, longitude)
        return value, True, failures
