"""
Satellite Risk Indicators stage.

Fuses the outputs of every upstream stage (change detection, segmentation,
spectral indices, SAR/InSAR) into the single standardized feature record
that is handed to the central multimodal AI Risk Engine (see
src/api/schemas.py for the schema, and docs/architecture.md section 9 for
the fusion strategy).

This stage also builds the human-readable `explanation` list, since
explainability is a hard requirement: every high-risk detection must be
traceable to concrete evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List


@dataclass
class SatelliteRiskIndicators:
    aoi_id: str
    latitude: float
    longitude: float
    observation_date: date
    change_score: float
    landslide_cv_probability: float
    vegetation_loss: float
    ndvi_delta: float
    ndwi_delta: float
    surface_displacement_mm: float
    water_accumulation_score: float
    road_disruption_score: float
    confidence: float
    data_sources: List[str]
    explanation: List[str]


def _confidence_from_inputs(
    cv_confidence: float,
    deformation_reliable_fraction: float,
    cloud_free_fraction: float,
) -> float:
    """
    Overall confidence blends: segmentation-model confidence, InSAR
    coherence reliability, and how much of the scene was actually
    cloud-free/usable. A confident-looking CV result on a mostly-cloudy
    scene should not be reported with high confidence.
    """
    weights = [0.5, 0.25, 0.25]
    values = [cv_confidence, deformation_reliable_fraction, cloud_free_fraction]
    return float(sum(w * v for w, v in zip(weights, values)))


def build_explanation(
    vegetation_loss: float,
    surface_displacement_mm: float,
    change_score: float,
    water_accumulation_score: float,
    road_disruption_score: float,
) -> List[str]:
    """
    Build a bullet-point, human-readable explanation list, e.g.:
      "18% vegetation loss detected"
      "32 mm ground displacement detected"
    Only includes an item if it crosses a minimal reporting threshold, so
    the explanation stays concise and meaningful rather than listing every
    near-zero signal.
    """
    explanation: List[str] = []

    if vegetation_loss >= 0.05:
        explanation.append(f"{vegetation_loss * 100:.0f}% vegetation loss detected in AOI")
    if surface_displacement_mm >= 5:
        explanation.append(f"{surface_displacement_mm:.1f} mm ground displacement detected (InSAR proxy)")
    if change_score >= 0.3:
        explanation.append(f"Significant multi-index surface change detected (change score {change_score:.2f})")
    if water_accumulation_score >= 0.2:
        explanation.append("Increased surface water accumulation — possible drainage blockage")
    if road_disruption_score >= 0.2:
        explanation.append("Possible road/debris disruption signature detected near AOI")

    if not explanation:
        explanation.append("No significant satellite-derived disturbance signals detected")

    return explanation


def build_satellite_risk_indicators(
    aoi_id: str,
    latitude: float,
    longitude: float,
    observation_date: date,
    change_score: float,
    landslide_cv_probability: float,
    vegetation_loss: float,
    ndvi_delta: float,
    ndwi_delta: float,
    surface_displacement_mm: float,
    water_accumulation_score: float,
    road_disruption_score: float,
    cv_confidence: float,
    deformation_reliable_fraction: float,
    cloud_free_fraction: float,
    data_sources: List[str],
) -> SatelliteRiskIndicators:
    """Assemble the final standardized record sent to the central AI Risk Engine."""
    confidence = _confidence_from_inputs(cv_confidence, deformation_reliable_fraction, cloud_free_fraction)
    explanation = build_explanation(
        vegetation_loss, surface_displacement_mm, change_score, water_accumulation_score, road_disruption_score
    )

    return SatelliteRiskIndicators(
        aoi_id=aoi_id,
        latitude=latitude,
        longitude=longitude,
        observation_date=observation_date,
        change_score=change_score,
        landslide_cv_probability=landslide_cv_probability,
        vegetation_loss=vegetation_loss,
        ndvi_delta=ndvi_delta,
        ndwi_delta=ndwi_delta,
        surface_displacement_mm=surface_displacement_mm,
        water_accumulation_score=water_accumulation_score,
        road_disruption_score=road_disruption_score,
        confidence=confidence,
        data_sources=data_sources,
        explanation=explanation,
    )
