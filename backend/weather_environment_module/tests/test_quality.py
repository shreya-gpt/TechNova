from datetime import datetime, timedelta, timezone

from app.models.schemas import QualityFlag
from app.services.quality_service import QualityInputs, compute_data_quality


def _base_inputs(**overrides) -> QualityInputs:
    defaults = dict(
        latitude=27.3,
        longitude=88.6,
        observation_timestamp=datetime.now(timezone.utc),
        rainfall_available=True,
        soil_moisture_available=True,
        temperature_available=True,
        humidity_available=True,
        forecast_available=True,
        used_fallback_or_demo=False,
        provider_reliability=0.85,
    )
    defaults.update(overrides)
    return QualityInputs(**defaults)


def test_perfect_quality_scores_high():
    quality = compute_data_quality(_base_inputs())
    assert quality.score >= 0.95
    assert quality.flags == []


def test_missing_rainfall_flagged_and_penalized():
    quality = compute_data_quality(_base_inputs(rainfall_available=False))
    assert QualityFlag.MISSING_RAINFALL in quality.flags
    assert quality.score < 1.0


def test_stale_observation_flagged():
    stale_ts = datetime.now(timezone.utc) - timedelta(hours=6)
    quality = compute_data_quality(_base_inputs(observation_timestamp=stale_ts))
    assert QualityFlag.STALE_OBSERVATION in quality.flags
    assert QualityFlag.STALE_RAINFALL in quality.flags


def test_invalid_coordinates_heavily_penalized():
    quality = compute_data_quality(_base_inputs(latitude=999.0))
    assert QualityFlag.INVALID_COORDINATES in quality.flags
    assert quality.score < 0.6


def test_fallback_usage_flagged_and_lowers_confidence():
    normal = compute_data_quality(_base_inputs())
    fallback = compute_data_quality(_base_inputs(used_fallback_or_demo=True, provider_reliability=0.3))
    assert QualityFlag.FALLBACK_SOURCE_USED in fallback.flags
    assert fallback.environmental_confidence < normal.environmental_confidence


def test_score_never_below_zero_or_above_one():
    quality = compute_data_quality(
        _base_inputs(
            latitude=999.0,
            rainfall_available=False,
            soil_moisture_available=False,
            temperature_available=False,
            humidity_available=False,
            forecast_available=False,
            used_fallback_or_demo=True,
            spike_detected=True,
            duplicate_timestamps_removed=5,
            temporal_gaps_detected=3,
            insufficient_history_for_anomaly=True,
            api_failure=True,
            provider_reliability=0.0,
        )
    )
    assert 0.0 <= quality.score <= 1.0
    assert 0.0 <= quality.environmental_confidence <= 1.0
