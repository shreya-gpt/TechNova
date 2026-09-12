from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.providers.demo import DemoProvider
from app.providers.imd import IMDProvider
from app.providers.open_meteo import OpenMeteoProvider
from app.providers.base import ProviderUnavailableError
from app.services.weather_service import WeatherService


@pytest.mark.asyncio
async def test_demo_provider_current_weather_is_plausible():
    provider = DemoProvider()
    result = await provider.get_current_weather(27.3, 88.6)
    assert result.rainfall_mm_last_hour is not None
    assert result.rainfall_mm_last_hour >= 0
    assert result.source.provider.value == "demo"
    assert result.source.is_fallback is True


@pytest.mark.asyncio
async def test_demo_provider_historical_series_covers_full_range():
    provider = DemoProvider()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=2)
    result = await provider.get_historical_weather(27.3, 88.6, start, now)
    assert len(result.points) >= 40  # roughly 48 hourly points expected


@pytest.mark.asyncio
async def test_demo_provider_forecast_length():
    provider = DemoProvider()
    result = await provider.get_forecast(27.3, 88.6, hours_ahead=24)
    assert len(result.points) == 24


@pytest.mark.asyncio
async def test_imd_provider_unavailable_without_key():
    provider = IMDProvider()
    with pytest.raises(ProviderUnavailableError):
        await provider.get_current_weather(27.3, 88.6)


@pytest.mark.asyncio
@respx.mock
async def test_open_meteo_current_weather_parses_response():
    route = respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(
            200,
            json={
                "current": {
                    "time": "2026-06-15T10:00",
                    "temperature_2m": 24.5,
                    "relative_humidity_2m": 88.0,
                    "precipitation": 3.2,
                }
            },
        )
    )
    provider = OpenMeteoProvider()
    result = await provider.get_current_weather(27.3, 88.6)
    assert route.called
    assert result.temperature_c == 24.5
    assert result.rainfall_mm_last_hour == 3.2


@pytest.mark.asyncio
@respx.mock
async def test_open_meteo_failure_raises_provider_error():
    respx.get("https://api.open-meteo.com/v1/forecast").mock(return_value=httpx.Response(500))
    provider = OpenMeteoProvider()
    with pytest.raises(Exception):
        await provider.get_current_weather(27.3, 88.6)


@pytest.mark.asyncio
async def test_weather_service_falls_back_to_demo_when_providers_fail():
    class AlwaysFailsProvider:
        name = "always_fails"
        reliability = 0.9

        async def get_current_weather(self, latitude, longitude):
            raise ProviderUnavailableError("simulated failure")

        async def get_historical_weather(self, latitude, longitude, start, end):
            raise ProviderUnavailableError("simulated failure")

        async def get_forecast(self, latitude, longitude, hours_ahead=48):
            raise ProviderUnavailableError("simulated failure")

        async def get_soil_moisture(self, latitude, longitude):
            raise ProviderUnavailableError("simulated failure")

    service = WeatherService(providers=[AlwaysFailsProvider()])
    service.settings.DEMO_MODE = False  # force it through the real-provider path first

    result, used_fallback, failures = await service.get_current_weather(27.3, 88.6)
    assert used_fallback is True
    assert result.source.provider.value == "demo"
    assert len(failures) == 1
