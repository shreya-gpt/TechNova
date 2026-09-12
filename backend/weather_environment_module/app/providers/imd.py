"""
IMD (India Meteorological Department) provider adapter.

IMPORTANT / HONEST LIMITATION:
IMD does not currently publish a stable, publicly documented, free JSON
API for arbitrary lat/lon current+historical rainfall in the way
Open-Meteo does. Operational access typically requires:
  - registration on the IMD data portal, and/or
  - a negotiated data-sharing agreement (e.g. for AWS/ARG station data), and/or
  - use of IMD's gridded rainfall NetCDF products (via NIC/IMD Pune),
    which require manual download and offline processing rather than a
    simple REST call.

Rather than inventing an endpoint that does not exist, this adapter:
  1. Documents exactly what would be required for a production
     integration (see README "Data Sources" section).
  2. Exposes a configurable `IMD_API_KEY` / `IMD_BASE_URL` for teams
     that DO have institutional IMD access to plug in a real integration.
  3. Raises ProviderUnavailableError when no key is configured, so the
     fallback chain (Open-Meteo -> Demo) takes over automatically.

This keeps the provider architecture ready for a real IMD integration
without pretending one exists today.
"""
from __future__ import annotations

from datetime import datetime

from app.config import get_settings
from app.models.schemas import CurrentWeather, ForecastResponse, HistoricalWeatherResponse
from app.providers.base import ProviderUnavailableError, WeatherDataProvider


class IMDProvider(WeatherDataProvider):
    name = "imd"
    reliability = 0.95  # would be the most authoritative source for India, if accessible

    def __init__(self):
        self.settings = get_settings()

    def _check_configured(self) -> None:
        if not self.settings.IMD_API_KEY:
            raise ProviderUnavailableError(
                "IMD provider is not configured. Set IMD_API_KEY (and any additional "
                "institutional access details) in your environment to enable it. "
                "Falling back to the next provider in the chain."
            )

    async def get_current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        self._check_configured()
        # NOTE: Placeholder for a real institutional IMD integration.
        raise ProviderUnavailableError("IMD current-weather integration not implemented in this prototype.")

    async def get_historical_weather(
        self, latitude: float, longitude: float, start: datetime, end: datetime
    ) -> HistoricalWeatherResponse:
        self._check_configured()
        raise ProviderUnavailableError("IMD historical-weather integration not implemented in this prototype.")

    async def get_forecast(self, latitude: float, longitude: float, hours_ahead: int = 48) -> ForecastResponse:
        self._check_configured()
        raise ProviderUnavailableError("IMD forecast integration not implemented in this prototype.")
