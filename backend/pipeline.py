"""
pipeline.py
===========
The central orchestration function for the whole backend:

    INPUT (RiskAnalysisRequest)
      -> data validation (handled automatically by Pydantic at the API layer)
      -> data quality assessment
      -> risk calculation (risk_service)
      -> impact assessment (impact_service)
      -> recommended action (decision_service)
      -> FinalRiskIntelligence

This is the ONE place that wires services together. Every service function
called here takes and returns plain schema objects (schemas.py), so any
individual service can be swapped for a teammate's real module later
without touching this file's control flow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from schemas import (
    DataQuality,
    EnvironmentalData,
    FeedbackStatus,
    FinalRiskIntelligence,
    RiskAnalysisRequest,
    SatelliteData,
    TerrainData,
)
from services.decision_service import recommend_actions
from services.impact_service import assess_impact
from services.risk_service import calculate_risk


def _assess_data_quality(
    environmental: EnvironmentalData, terrain: TerrainData, satellite: SatelliteData
) -> DataQuality:
    """Report which optional fields are missing and an overall completeness
    score, so downstream consumers (and the uncertainty model) have a clear,
    inspectable view of data gaps rather than a hidden internal detail."""

    optional_fields = {
        "environmental.rainfall_72h": environmental.rainfall_72h,
        "environmental.forecast_rainfall": environmental.forecast_rainfall,
        "environmental.soil_moisture": environmental.soil_moisture,
        "terrain.elevation": terrain.elevation,
        "terrain.geology": terrain.geology,
        "terrain.historical_landslide_density": terrain.historical_landslide_density,
        "satellite.surface_change_score": satellite.surface_change_score if satellite.satellite_available else None,
    }

    missing_fields: List[str] = [name for name, value in optional_fields.items() if value is None]
    if not satellite.satellite_available and "satellite.surface_change_score" not in missing_fields:
        missing_fields.append("satellite.surface_change_score")

    total_fields = len(optional_fields)
    completeness_score = round((total_fields - len(set(missing_fields))) / total_fields, 4)

    return DataQuality(
        completeness_score=completeness_score,
        missing_fields=sorted(set(missing_fields)),
        satellite_available=satellite.satellite_available,
    )


def run_risk_pipeline(request: RiskAnalysisRequest) -> FinalRiskIntelligence:
    """Run the full Predict -> Explain -> Quantify Uncertainty -> Assess
    Impact -> Recommend Action sequence for a single location.

    `request` has already been validated by Pydantic (FastAPI does this
    automatically when this is called from an endpoint that types its body
    as RiskAnalysisRequest). Any structurally invalid input never reaches
    this function — it is rejected with a 422 at the API boundary.
    """

    data_quality = _assess_data_quality(request.environmental, request.terrain, request.satellite)

    risk = calculate_risk(request.environmental, request.terrain, request.satellite)

    impact = assess_impact(risk, request.location.latitude, request.location.longitude)

    decision = recommend_actions(risk, impact)

    return FinalRiskIntelligence(
        location=request.location,
        input_data=request,
        risk=risk,
        impact=impact,
        decision=decision,
        timestamp=datetime.now(timezone.utc),
        data_quality=data_quality,
        feedback_status=FeedbackStatus.PENDING,
    )