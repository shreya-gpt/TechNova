"""
Landslide-relevant environmental feature engineering.

This module turns raw hourly observation/forecast series into the
deterministic feature set consumed by the Risk Engine: rainfall
accumulations, intensity, Antecedent Precipitation Index (API), rainfall
anomaly/percentile, forecast accumulations, and rule-based indicator flags.

All thresholds are read from app.config.Settings and are explicitly
documented there as prototype defaults requiring local calibration.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Tuple

from app.config import Settings, get_settings
from app.models.schemas import EnvironmentalFeatures, EnvironmentalIndicators
from app.processing.aggregation import (
    rainfall_acceleration,
    rolling_intensity,
    sum_rainfall_last_n_hours,
    longest_persistent_rain_run,
)


def antecedent_precipitation_index(
    timestamps: Sequence[datetime],
    values: Sequence[Optional[float]],
    reference_time: datetime,
    decay_factor: Optional[float] = None,
    lookback_days: Optional[int] = None,
) -> Optional[float]:
    """
    Daily Antecedent Precipitation Index:
        API = sum_{d=0..lookback_days} (decay_factor^d) * rainfall_on_day_(reference-d)

    A higher API means the catchment has been wetter recently, which is a
    classic (if simplified) proxy for landslide-predisposing soil wetness.
    """
    settings = get_settings()
    k = decay_factor if decay_factor is not None else settings.API_DECAY_FACTOR
    n_days = lookback_days if lookback_days is not None else settings.API_LOOKBACK_DAYS

    # Bucket hourly values into daily totals first.
    daily_totals = {}
    for t, v in zip(timestamps, values):
        if v is None:
            continue
        day_key = (reference_time.date() - t.date()).days
        if 0 <= day_key < n_days:
            daily_totals[day_key] = daily_totals.get(day_key, 0.0) + v

    if not daily_totals:
        return None

    api_value = 0.0
    for day_key, total in daily_totals.items():
        api_value += (k ** day_key) * total
    return round(api_value, 2)


def rainfall_anomaly_and_percentile(
    current_24h_mm: Optional[float], historical_24h_totals: Sequence[float]
) -> Tuple[Optional[float], Optional[float]]:
    """
    Compares current_24h_mm against a distribution of historical 24h totals
    (e.g. same calendar window in prior years, or a trailing multi-year
    sample) to produce:
      - anomaly_pct: percent deviation from the historical mean
      - percentile: where current value ranks in the historical distribution (0-100)

    Returns (None, None) if there isn't enough historical data (need >= 5
    points) to make a statistically meaningful comparison.
    """
    if current_24h_mm is None or len(historical_24h_totals) < 5:
        return None, None

    mean = statistics.mean(historical_24h_totals)
    anomaly_pct = None
    if mean > 0:
        anomaly_pct = round(((current_24h_mm - mean) / mean) * 100.0, 1)
    elif current_24h_mm > 0:
        anomaly_pct = 100.0

    sorted_hist = sorted(historical_24h_totals)
    rank = sum(1 for v in sorted_hist if v <= current_24h_mm)
    percentile = round((rank / len(sorted_hist)) * 100.0, 1)

    return anomaly_pct, percentile


def build_environmental_features(
    reference_time: datetime,
    hist_timestamps: Sequence[datetime],
    hist_rainfall: Sequence[Optional[float]],
    forecast_timestamps: Sequence[datetime],
    forecast_rainfall: Sequence[Optional[float]],
    soil_moisture: Optional[float],
    temperature_c: Optional[float],
    relative_humidity_pct: Optional[float],
    historical_24h_totals_for_anomaly: Sequence[float] = (),
    settings: Optional[Settings] = None,
) -> EnvironmentalFeatures:
    settings = settings or get_settings()

    rainfall_1h = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 1)
    rainfall_3h = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 3)
    rainfall_6h = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 6)
    rainfall_12h = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 12)
    rainfall_24h = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 24)
    rainfall_48h = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 48)
    rainfall_72h = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 72)
    rainfall_7d = sum_rainfall_last_n_hours(hist_timestamps, hist_rainfall, reference_time, 24 * 7)

    intensity = rolling_intensity(hist_timestamps, hist_rainfall, reference_time, 3)
    rolling_int = rolling_intensity(hist_timestamps, hist_rainfall, reference_time, 6)
    accel = rainfall_acceleration(hist_timestamps, hist_rainfall, reference_time, 3, 12)

    api_value = antecedent_precipitation_index(hist_timestamps, hist_rainfall, reference_time)
    anomaly_pct, percentile = rainfall_anomaly_and_percentile(rainfall_24h, historical_24h_totals_for_anomaly)

    fc_3h = _forecast_sum(forecast_timestamps, forecast_rainfall, reference_time, 3)
    fc_6h = _forecast_sum(forecast_timestamps, forecast_rainfall, reference_time, 6)
    fc_12h = _forecast_sum(forecast_timestamps, forecast_rainfall, reference_time, 12)
    fc_24h = _forecast_sum(forecast_timestamps, forecast_rainfall, reference_time, 24)
    fc_48h = _forecast_sum(forecast_timestamps, forecast_rainfall, reference_time, 48)

    return EnvironmentalFeatures(
        rainfall_1h_mm=rainfall_1h,
        rainfall_3h_mm=rainfall_3h,
        rainfall_6h_mm=rainfall_6h,
        rainfall_12h_mm=rainfall_12h,
        rainfall_24h_mm=rainfall_24h,
        rainfall_48h_mm=rainfall_48h,
        rainfall_72h_mm=rainfall_72h,
        rainfall_7d_mm=rainfall_7d,
        rainfall_intensity_mm_per_hr=intensity,
        rolling_rainfall_intensity_mm_per_hr=rolling_int,
        antecedent_precipitation_index=api_value,
        rainfall_anomaly_pct=anomaly_pct,
        rainfall_percentile=percentile,
        forecast_rainfall_3h_mm=fc_3h,
        forecast_rainfall_6h_mm=fc_6h,
        forecast_rainfall_12h_mm=fc_12h,
        forecast_rainfall_24h_mm=fc_24h,
        forecast_rainfall_48h_mm=fc_48h,
        soil_moisture_m3m3=soil_moisture,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        rainfall_acceleration_mm_per_hr2=accel,
    )


def _forecast_sum(
    forecast_timestamps: Sequence[datetime], forecast_rainfall: Sequence[Optional[float]],
    reference_time: datetime, hours: int,
) -> Optional[float]:
    if not forecast_timestamps:
        return None
    window_end = reference_time + timedelta(hours=hours)
    total = 0.0
    found = False
    for t, v in zip(forecast_timestamps, forecast_rainfall):
        if reference_time < t <= window_end and v is not None:
            total += v
            found = True
    return round(total, 2) if found else None


def build_environmental_indicators(
    features: EnvironmentalFeatures,
    persistent_run_hours: int,
    settings: Optional[Settings] = None,
) -> EnvironmentalIndicators:
    settings = settings or get_settings()
    notes: List[str] = []

    heavy = bool(features.rainfall_24h_mm is not None and features.rainfall_24h_mm >= settings.HEAVY_RAINFALL_MM_24H)
    extreme = bool(features.rainfall_24h_mm is not None and features.rainfall_24h_mm >= settings.EXTREME_RAINFALL_MM_24H)
    persistent = persistent_run_hours >= settings.PERSISTENT_RAINFALL_HOURS
    high_soil = bool(
        features.soil_moisture_m3m3 is not None and features.soil_moisture_m3m3 >= settings.HIGH_SOIL_MOISTURE_FRACTION
    )
    forecast_heavy = bool(
        features.forecast_rainfall_24h_mm is not None
        and features.forecast_rainfall_24h_mm >= settings.FORECAST_HEAVY_RAINFALL_MM_24H
    )

    api_val = features.antecedent_precipitation_index
    if api_val is None:
        wetness_level = "unknown"
    elif api_val < 20:
        wetness_level = "low"
    elif api_val < 60:
        wetness_level = "moderate"
    elif api_val < 120:
        wetness_level = "high"
    else:
        wetness_level = "very_high"

    if extreme:
        notes.append(
            "24h rainfall exceeds the prototype EXTREME threshold; this is an environmental "
            "signal for the Risk Engine, not a standalone landslide prediction."
        )
    if persistent:
        notes.append(f"Rainfall has persisted at or above threshold intensity for ~{persistent_run_hours}h.")
    if heavy and not extreme:
        notes.append("24h rainfall exceeds the prototype HEAVY threshold.")

    return EnvironmentalIndicators(
        heavy_rainfall_flag=heavy,
        extreme_accumulation_flag=extreme,
        persistent_rainfall_flag=persistent,
        high_soil_moisture_flag=high_soil,
        forecast_heavy_rainfall_flag=forecast_heavy,
        antecedent_wetness_level=wetness_level,
        notes=notes,
    )
