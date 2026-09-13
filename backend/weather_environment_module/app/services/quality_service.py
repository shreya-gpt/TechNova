"""
Data quality service.

Combines validation-layer checks into a single 0-1 `data_quality_score`
plus a list of machine-readable `quality_flags`, and derives an
`environmental_confidence` score that downstream consumers can use to
weight this module's output. This confidence is explicitly NOT a
landslide probability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from app.models.schemas import DataQuality, QualityFlag
from app.processing.validation import (
    data_age_minutes,
    is_stale,
    is_valid_coordinate,
    is_within_ner_bbox,
)


@dataclass
class QualityInputs:
    latitude: float
    longitude: float
    observation_timestamp: Optional[datetime]
    rainfall_available: bool
    soil_moisture_available: bool
    temperature_available: bool
    humidity_available: bool
    forecast_available: bool
    used_fallback_or_demo: bool
    provider_reliability: float
    spike_detected: bool = False
    duplicate_timestamps_removed: int = 0
    temporal_gaps_detected: int = 0
    insufficient_history_for_anomaly: bool = False
    api_failure: bool = False


def compute_data_quality(inputs: QualityInputs) -> DataQuality:
    flags: List[QualityFlag] = []
    penalty = 0.0

    if not is_valid_coordinate(inputs.latitude, inputs.longitude):
        flags.append(QualityFlag.INVALID_COORDINATES)
        penalty += 0.5
    elif not is_within_ner_bbox(inputs.latitude, inputs.longitude):
        flags.append(QualityFlag.OUTSIDE_NER_REGION)
        penalty += 0.1

    if not inputs.rainfall_available:
        flags.append(QualityFlag.MISSING_RAINFALL)
        penalty += 0.25
    if not inputs.soil_moisture_available:
        flags.append(QualityFlag.MISSING_SOIL_MOISTURE)
        penalty += 0.1
    if not inputs.temperature_available:
        flags.append(QualityFlag.MISSING_TEMPERATURE)
        penalty += 0.05
    if not inputs.humidity_available:
        flags.append(QualityFlag.MISSING_HUMIDITY)
        penalty += 0.05
    if not inputs.forecast_available:
        flags.append(QualityFlag.MISSING_FORECAST)
        flags.append(QualityFlag.FORECAST_SOURCE_UNAVAILABLE)
        penalty += 0.1

    age_minutes = None
    if inputs.observation_timestamp is not None:
        age_minutes = data_age_minutes(inputs.observation_timestamp)
        if is_stale(inputs.observation_timestamp):
            flags.append(QualityFlag.STALE_OBSERVATION)
            flags.append(QualityFlag.STALE_RAINFALL)
            penalty += 0.15

    if inputs.spike_detected:
        flags.append(QualityFlag.SUSPICIOUS_SPIKE)
        penalty += 0.1

    if inputs.duplicate_timestamps_removed > 0:
        flags.append(QualityFlag.DUPLICATE_TIMESTAMPS)
        penalty += 0.05

    if inputs.temporal_gaps_detected > 0:
        flags.append(QualityFlag.TEMPORAL_GAP)
        penalty += 0.1

    if inputs.insufficient_history_for_anomaly:
        flags.append(QualityFlag.INSUFFICIENT_HISTORY_FOR_ANOMALY)
        penalty += 0.05

    if inputs.api_failure:
        flags.append(QualityFlag.API_FAILURE)
        penalty += 0.2

    if inputs.used_fallback_or_demo:
        flags.append(QualityFlag.FALLBACK_SOURCE_USED)
        penalty += 0.15

    score = max(0.0, min(1.0, 1.0 - penalty))

    # Environmental confidence blends the quality score with the provider's
    # intrinsic reliability. This is a heuristic combination, deliberately
    # kept simple and transparent for a prototype.
    confidence = max(0.0, min(1.0, 0.6 * score + 0.4 * inputs.provider_reliability))

    return DataQuality(
        score=round(score, 3),
        flags=flags,
        data_age_minutes=round(age_minutes, 1) if age_minutes is not None else None,
        environmental_confidence=round(confidence, 3),
    )
