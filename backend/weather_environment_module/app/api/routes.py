"""
FastAPI routes for the Weather & Environmental Data Module.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.database.repository import ObservationRepository, init_db
from app.models.schemas import (
    BatchRequest,
    BatchResponse,
    CurrentWeather,
    ForecastResponse,
    HistoricalWeatherResponse,
    RiskFeatureResponse,
)
from app.services.environmental_service import EnvironmentalService, InvalidCoordinateError
from app.services.weather_service import WeatherService

logger = logging.getLogger("api")
router = APIRouter()

_weather_service = WeatherService()
_environmental_service = EnvironmentalService(_weather_service)


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "demo_mode": settings.DEMO_MODE,
        "version": "0.1.0",
    }


@router.get("/weather/current", response_model=CurrentWeather)
async def weather_current(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
):
    result, _, _ = await _weather_service.get_current_weather(latitude, longitude)
    return result


@router.get("/weather/forecast", response_model=ForecastResponse)
async def weather_forecast(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    hours_ahead: int = Query(48, ge=1, le=168),
):
    result, _, _ = await _weather_service.get_forecast(latitude, longitude, hours_ahead)
    return result


@router.get("/weather/historical", response_model=HistoricalWeatherResponse)
async def weather_historical(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start: datetime = Query(..., description="ISO8601 start timestamp (UTC)"),
    end: datetime = Query(..., description="ISO8601 end timestamp (UTC)"),
):
    if end <= start:
        raise HTTPException(status_code=400, detail="`end` must be after `start`")
    result, _, _ = await _weather_service.get_historical_weather(latitude, longitude, start, end)
    return result


@router.get("/environment/features", response_model=RiskFeatureResponse)
async def environment_features(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    timestamp: Optional[datetime] = Query(None, description="ISO8601 timestamp (UTC); defaults to now"),
):
    """Alias of /environment/risk-features kept for readability / discoverability."""
    return await _get_risk_features(latitude, longitude, timestamp)


@router.get("/environment/risk-features", response_model=RiskFeatureResponse)
async def environment_risk_features(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    timestamp: Optional[datetime] = Query(None, description="ISO8601 timestamp (UTC); defaults to now"),
):
    """
    Primary contract endpoint consumed by the AI / Risk Engine.
    Returns environmental features + indicators + data quality for the
    given coordinate and timestamp. Persists the response for auditability.
    """
    return await _get_risk_features(latitude, longitude, timestamp)


async def _get_risk_features(latitude: float, longitude: float, timestamp: Optional[datetime]) -> RiskFeatureResponse:
    try:
        response = await _environmental_service.get_risk_features(latitude, longitude, timestamp)
    except InvalidCoordinateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        with ObservationRepository() as repo:
            repo.save_risk_feature_response(response)
    except Exception as exc:  # pragma: no cover - persistence must never break the API response
        logger.warning("Failed to persist observation: %s", exc)

    return response


@router.post("/environment/batch", response_model=BatchResponse)
async def environment_batch(request: BatchRequest):
    settings = get_settings()
    if len(request.items) > settings.BATCH_MAX_ITEMS:
        raise HTTPException(
            status_code=400,
            detail=f"Batch too large: {len(request.items)} items (max {settings.BATCH_MAX_ITEMS})",
        )

    semaphore = asyncio.Semaphore(settings.BATCH_CONCURRENCY)
    results = []
    errors = []

    async def _process(item):
        async with semaphore:
            try:
                response = await _get_risk_features(item.latitude, item.longitude, item.timestamp)
                results.append(response)
            except HTTPException as exc:
                errors.append({"latitude": str(item.latitude), "longitude": str(item.longitude), "error": exc.detail})
            except Exception as exc:  # noqa: BLE001
                errors.append({"latitude": str(item.latitude), "longitude": str(item.longitude), "error": str(exc)})

    await asyncio.gather(*(_process(item) for item in request.items))
    return BatchResponse(results=results, errors=errors)
