"""
Common provider interface.

Every concrete weather/environmental data source (Open-Meteo, IMD, NASA
POWER, a soil-moisture source, or the built-in demo generator) implements
this interface. The rest of the application (processing, services, API)
depends only on this abstraction, so a provider can be swapped or added
without touching downstream code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from app.models.schemas import (
    CurrentWeather,
    ForecastResponse,
    HistoricalWeatherResponse,
)


class ProviderError(Exception):
    """Raised when a provider fails to fetch data (network error, bad response, etc.)."""


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is not configured / not reachable in the current environment."""


class WeatherDataProvider(ABC):
    """Abstract base class for all weather/environmental data providers."""

    #: Human readable identifier, used in source metadata.
    name: str = "base"
    #: Static reliability score (0-1) used as a starting point for confidence calculations.
    reliability: float = 0.5

    @abstractmethod
    async def get_current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        """Return the most recent observation available for the coordinate."""

    @abstractmethod
    async def get_historical_weather(
        self, latitude: float, longitude: float, start: datetime, end: datetime
    ) -> HistoricalWeatherResponse:
        """Return historical hourly/daily observations between start and end (inclusive)."""

    @abstractmethod
    async def get_forecast(self, latitude: float, longitude: float, hours_ahead: int = 48) -> ForecastResponse:
        """Return a forecast for the next `hours_ahead` hours."""

    async def get_soil_moisture(self, latitude: float, longitude: float) -> Optional[float]:
        """
        Return volumetric soil moisture (m3/m3) if this provider supports it.
        Default implementation: not supported.
        """
        return None
