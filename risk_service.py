"""
services/risk_service.py
=========================
PROTOTYPE / BASELINE risk engine.

This is a transparent, weighted, rule-based model — NOT a scientifically
validated landslide prediction model. It exists so the rest of the pipeline
(impact assessment, decision engine, feedback loop, API, frontend) can be
built, demoed, and tested end-to-end today.

When the team's real ML/statistical risk model is ready, replace the body
of `calculate_risk()` with a call into that model, but keep returning a
`RiskResult` with the same fields so nothing else in the system has to change.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from config import (
    FACTOR_LABELS,
    GEOLOGY_DEFAULT_SCORE,
    GEOLOGY_RISK_MAP,
    NORMALIZATION_RANGES,
    RISK_THRESHOLDS,
    RISK_WEIGHTS,
    BASE_UNCERTAINTY,
    SATELLITE_UNAVAILABLE_PENALTY,
    MISSING_FIELD_PENALTY,
    MAX_UNCERTAINTY,
)
from schemas import EnvironmentalData, RiskLevel, RiskResult, SatelliteData, TerrainData


def _normalize(value: Optional[float], factor_key: str) -> Optional[float]:
    """Linearly scale a raw value onto 0-1 using NORMALIZATION_RANGES.
    Returns None if the input value itself is None (i.e. missing data)."""
    if value is None:
        return None
    low, high = NORMALIZATION_RANGES[factor_key]
    if high == low:
        return 0.0
    scaled = (value - low) / (high - low)
    return max(0.0, min(1.0, scaled))


def _geology_score(geology: Optional[str]) -> Optional[float]:
    """Map a categorical geology label to a 0-1 instability score.
    Returns None if geology is missing entirely (distinct from 'unrecognized
    label', which we treat as a known-but-neutral score)."""
    if geology is None:
        return None
    return GEOLOGY_RISK_MAP.get(geology, GEOLOGY_DEFAULT_SCORE)


def _collect_normalized_factors(
    environmental: EnvironmentalData, terrain: TerrainData, satellite: SatelliteData
) -> Dict[str, Optional[float]]:
    """Return {factor_key: normalized_value_or_None} for every weighted factor."""
    return {
        "rainfall_24h": _normalize(environmental.rainfall_24h, "rainfall_24h"),
        "rainfall_72h": _normalize(environmental.rainfall_72h, "rainfall_72h"),
        "forecast_rainfall": _normalize(environmental.forecast_rainfall, "forecast_rainfall"),
        "soil_moisture": _normalize(environmental.soil_moisture, "soil_moisture"),
        "slope": _normalize(terrain.slope, "slope"),
        "geology": _geology_score(terrain.geology),
        "historical_landslide_density": _normalize(
            terrain.historical_landslide_density, "historical_landslide_density"
        ),
        "satellite_surface_change": (
            satellite.surface_change_score if satellite.satellite_available else None
        ),
    }


def _risk_level_from_score(score: float) -> RiskLevel:
    for level_name, (low, high) in RISK_THRESHOLDS.items():
        if low <= score < high:
            return RiskLevel(level_name)
    return RiskLevel.CRITICAL  # fallback for score == 100 edge case


def calculate_uncertainty(
    normalized_factors: Dict[str, Optional[float]], satellite: SatelliteData
) -> float:
    """
    Transparent prototype uncertainty model.

    Uncertainty grows with:
      - each missing input factor (data completeness)
      - satellite imagery being unavailable specifically (on top of the
        generic missing-factor penalty, since satellite loss also removes an
        independent corroborating signal)

    This is deliberately simple and explainable rather than a black box.
    Confidence is always defined as `1 - uncertainty`, never generated
    independently or at random.
    """
    uncertainty = BASE_UNCERTAINTY

    missing_count = sum(1 for v in normalized_factors.values() if v is None)
    uncertainty += missing_count * MISSING_FIELD_PENALTY

    if not satellite.satellite_available:
        uncertainty += SATELLITE_UNAVAILABLE_PENALTY

    return round(min(uncertainty, MAX_UNCERTAINTY), 4)


def _build_explanation(risk_level: RiskLevel, ranked_factors: List[Tuple[str, float]]) -> str:
    top_labels = [FACTOR_LABELS[key] for key, _ in ranked_factors[:3]]
    if not top_labels:
        return f"Risk is {risk_level.value}, but insufficient data was available to identify contributing factors."
    if len(top_labels) == 1:
        factor_text = top_labels[0]
    elif len(top_labels) == 2:
        factor_text = f"{top_labels[0]} and {top_labels[1]}"
    else:
        factor_text = f"{top_labels[0]}, {top_labels[1]}, and {top_labels[2]}"
    return f"Risk is {risk_level.value} primarily because of {factor_text}."


def calculate_risk(
    environmental: EnvironmentalData, terrain: TerrainData, satellite: SatelliteData
) -> RiskResult:
    """Compute the PROTOTYPE weighted risk score, level, uncertainty,
    confidence, top contributing factors, and a human-readable explanation."""

    normalized_factors = _collect_normalized_factors(environmental, terrain, satellite)

    # Only factors with actual data contribute to the score. We rescale by
    # the weight actually present so that missing data doesn't silently
    # drag the score toward zero — instead, missing data is penalized
    # explicitly and separately via uncertainty.
    weighted_sum = 0.0
    weight_present = 0.0
    contributions: List[Tuple[str, float]] = []  # (factor_key, weight * normalized_value)

    for factor_key, normalized_value in normalized_factors.items():
        weight = RISK_WEIGHTS[factor_key]
        if normalized_value is not None:
            weighted_sum += weight * normalized_value
            weight_present += weight
            contributions.append((factor_key, weight * normalized_value))

    if weight_present == 0.0:
        # No usable data at all — cannot responsibly compute a score.
        risk_score = 50.0  # neutral midpoint, flagged by very high uncertainty below
    else:
        risk_score = round((weighted_sum / weight_present) * 100, 2)

    risk_level = _risk_level_from_score(risk_score)

    # Rank factors by their contribution to the score for explainability.
    ranked = sorted(contributions, key=lambda item: item[1], reverse=True)
    top_factors = [FACTOR_LABELS[key] for key, _ in ranked[:3]]

    uncertainty = calculate_uncertainty(normalized_factors, satellite)
    if weight_present == 0.0:
        uncertainty = min(uncertainty + 0.3, 0.95)  # extra penalty for total data absence
    confidence = round(1 - uncertainty, 4)

    explanation = _build_explanation(risk_level, ranked)

    return RiskResult(
        risk_score=risk_score,
        risk_level=risk_level,
        uncertainty=uncertainty,
        confidence=confidence,
        top_factors=top_factors,
        explanation=explanation,
    )
