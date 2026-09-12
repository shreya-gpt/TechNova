"""
Environmental service.

This is the orchestration layer behind the module's most important
endpoint, GET /environment/risk-features. It:

  1. Validates the request (coordinates).
  2. Fetches current, historical and forecast weather + soil moisture via
     WeatherService (which already handles provider fallback + caching).
  3. Cleans the historical series (dedup, spike detection).
  4. Builds the environmental feature vector and rule-based indicators.
  5. Scores data quality / environmental confidence.
  6. Returns the RiskFeatureResponse contract for the AI / Risk Engine.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.config import get_settings
from app.models.schemas import (
    DataSourceType,
    EnvironmentalFeatures,
    Location,
    QualityFlag,
    RiskFeatureResponse,
    SourceMetadata,
)
from app.processing.aggregation import longest_persistent_rain_run
from app.processing.cleaning import clean_series
from app.processing.features import build_environmental_features, build_environmental_indicators
from app.processing.validation import is_valid_coordinate, is_within_ner_bbox
from app.services.quality_service import QualityInputs, compute_data_quality
from app.services.weather_service import WeatherService

logger = logging.getLogger("environmental_service")


class InvalidCoordinateError(ValueError):
    pass


class EnvironmentalService:
    def __init__(self, weather_service: Optional[WeatherService] = None):
        self.settings = get_settings()
        self.weather_service = weather_service or WeatherService()

    async def get_risk_features(
        self, latitude: float, longitude: float, timestamp: Optional[datetime] = None
    ) -> RiskFeatureResponse:
        if not is_valid_coordinate(latitude, longitude):
            raise InvalidCoordinateError(f"Invalid coordinates: ({latitude}, {longitude})")

        reference_time = timestamp or datetime.now(timezone.utc)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        outside_ner = not is_within_ner_bbox(latitude, longitude)
        if outside_ner:
            logger.info("Coordinates (%s, %s) are outside the approximate NER bounding box.", latitude, longitude)

        history_start = reference_time - timedelta(days=self.settings.API_LOOKBACK_DAYS + 15)

        current, current_fallback, current_failures = await self.weather_service.get_current_weather(latitude, longitude)
        historical, hist_fallback, hist_failures = await self.weather_service.get_historical_weather(
            latitude, longitude, history_start, reference_time
        )
        forecast, forecast_fallback, forecast_failures = await self.weather_service.get_forecast(
            latitude, longitude, hours_ahead=48
        )
        soil_moisture, soil_fallback, soil_failures = await self.weather_service.get_soil_moisture(latitude, longitude)

        used_fallback = any([current_fallback, hist_fallback, forecast_fallback, soil_fallback])
        api_failure = bool(current_failures or hist_failures or forecast_failures or soil_failures)

        # ---- clean historical series -------------------------------------------------
        hist_timestamps = [p.timestamp for p in historical.points]
        hist_values = [p.rainfall_mm for p in historical.points]
        cleaned = clean_series(hist_timestamps, hist_values)

        gaps = 0
        if len(cleaned.timestamps) > 1:
            ordered = sorted(cleaned.timestamps)
            for prev, curr in zip(ordered, ordered[1:]):
                if (curr - prev).total_seconds() / 3600.0 > 1.5:
                    gaps += 1

        # ---- historical daily totals (for anomaly/percentile) ------------------------
        daily_totals: dict = defaultdict(float)
        for t, v in zip(cleaned.timestamps, cleaned.values):
            if v is None:
                continue
            day_offset = (reference_time.date() - t.date()).days
            if 1 <= day_offset <= (self.settings.API_LOOKBACK_DAYS + 14):  # exclude "today"
                daily_totals[day_offset] += v
        historical_24h_totals = list(daily_totals.values())
        insufficient_history = len(historical_24h_totals) < 5

        # ---- forecast series -----------------------------------------------------------
        forecast_timestamps = [p.timestamp for p in forecast.points]
        forecast_values = [p.rainfall_mm for p in forecast.points]

        features: EnvironmentalFeatures = build_environmental_features(
            reference_time=reference_time,
            hist_timestamps=cleaned.timestamps,
            hist_rainfall=cleaned.values,
            forecast_timestamps=forecast_timestamps,
            forecast_rainfall=forecast_values,
            soil_moisture=soil_moisture if soil_moisture is not None else current.soil_moisture_m3m3,
            temperature_c=current.temperature_c,
            relative_humidity_pct=current.relative_humidity_pct,
            historical_24h_totals_for_anomaly=historical_24h_totals,
        )

        persistent_run_hours = longest_persistent_rain_run(
            cleaned.timestamps, cleaned.values, self.settings.PERSISTENT_RAINFALL_MIN_MM_PER_HOUR
        )
        indicators = build_environmental_indicators(features, persistent_run_hours)

        quality_inputs = QualityInputs(
            latitude=latitude,
            longitude=longitude,
            observation_timestamp=current.observation_timestamp,
            rainfall_available=features.rainfall_24h_mm is not None,
            soil_moisture_available=features.soil_moisture_m3m3 is not None,
            temperature_available=features.temperature_c is not None,
            humidity_available=features.relative_humidity_pct is not None,
            forecast_available=bool(forecast.points),
            used_fallback_or_demo=used_fallback,
            provider_reliability=current.source.reliability,
            spike_detected=bool(cleaned.spike_indices),
            duplicate_timestamps_removed=cleaned.removed_duplicates,
            temporal_gaps_detected=gaps,
            insufficient_history_for_anomaly=insufficient_history,
            api_failure=api_failure,
        )
        quality = compute_data_quality(quality_inputs)
        if outside_ner and QualityFlag.OUTSIDE_NER_REGION not in quality.flags:
            quality.flags.append(QualityFlag.OUTSIDE_NER_REGION)
        if (self.settings.DEMO_MODE or current.source.provider == DataSourceType.DEMO) and QualityFlag.DEMO_DATA not in quality.flags:
            quality.flags.append(QualityFlag.DEMO_DATA)

        sources: List[SourceMetadata] = []
        for src in (current.source, historical.source, forecast.source):
            if src not in sources:
                sources.append(src)

        return RiskFeatureResponse(
            location=Location(latitude=latitude, longitude=longitude),
            timestamp=reference_time,
            environmental_features=features,
            environmental_indicators=indicators,
            data_quality=quality,
            sources=sources,
        )
