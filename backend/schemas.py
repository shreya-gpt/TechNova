"""
schemas.py
==========
This file is the single "data contract" for the whole platform.

Every teammate's module (weather, GIS, satellite, risk-model, frontend)
should read and write data that matches these Pydantic models. As long as
a teammate's real module produces objects that satisfy these shapes, it can
be swapped in for any of our mock/prototype services without changing
main.py, pipeline.py, or any other service.

Notes on "Optional" fields:
Several fields below are Optional[...] on purpose. In the real system,
weather stations may be down, satellite passes may be unavailable, or a
district may lack historical records. Rather than pretending we always have
perfect data, we model missing data explicitly and let the risk/uncertainty
engine react to it honestly.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UrgencyLevel(str, Enum):
    ROUTINE = "ROUTINE"
    ELEVATED = "ELEVATED"
    URGENT = "URGENT"
    IMMEDIATE = "IMMEDIATE"


class ImpactLevel(str, Enum):
    NEGLIGIBLE = "NEGLIGIBLE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class FeedbackStatus(str, Enum):
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"


# ---------------------------------------------------------------------------
# Input data models (populated by teammates' modules, or mock data for now)
# ---------------------------------------------------------------------------

class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    district: str
    state: str


class EnvironmentalData(BaseModel):
    """Produced by the weather/hydrology teammate's module."""
    rainfall_24h: float = Field(..., ge=0, description="mm of rain in last 24h")
    rainfall_72h: Optional[float] = Field(None, ge=0, description="mm of rain in last 72h")
    forecast_rainfall: Optional[float] = Field(None, ge=0, description="mm of rain forecast next 24h")
    soil_moisture: Optional[float] = Field(None, ge=0, le=100, description="% saturation")


class TerrainData(BaseModel):
    """Produced by the GIS/terrain teammate's module."""
    slope: float = Field(..., ge=0, le=90, description="degrees")
    elevation: Optional[float] = Field(None, description="meters above sea level")
    geology: Optional[str] = Field(
        None,
        description=(
            "Categorical geology descriptor, e.g. 'stable_rock', "
            "'moderately_weathered', 'highly_weathered', "
            "'weak_sedimentary_or_fractured'. Unknown/absent is allowed."
        ),
    )
    historical_landslide_density: Optional[float] = Field(
        None, ge=0, description="past landslide events per sq. km (or equivalent index)"
    )


class SatelliteData(BaseModel):
    """Produced by the satellite/remote-sensing teammate's module."""
    satellite_available: bool = Field(..., description="was a usable satellite pass available")
    surface_change_score: Optional[float] = Field(
        None, ge=0, le=1, description="0-1 normalized surface-change/deformation indicator"
    )
    vegetation_indicator: Optional[float] = Field(
        None, ge=0, le=1, description="0-1 normalized vegetation index (e.g. derived from NDVI)"
    )


class Infrastructure(BaseModel):
    """Produced by the GIS teammate's module (asset inventory near the location)."""
    roads: int = Field(0, ge=0, description="count of road segments in the risk zone")
    bridges: int = Field(0, ge=0)
    settlements: int = Field(0, ge=0)
    hospitals: int = Field(0, ge=0)
    schools: int = Field(0, ge=0)
    estimated_population: int = Field(0, ge=0)


class RiskAnalysisRequest(BaseModel):
    """The full input to POST /risk/analyze — this is the combined payload
    that would eventually be assembled from all teammates' modules."""
    location: Location
    environmental: EnvironmentalData
    terrain: TerrainData
    satellite: SatelliteData
    infrastructure: Infrastructure


# ---------------------------------------------------------------------------
# Output data models (produced by OUR services)
# ---------------------------------------------------------------------------

class RiskResult(BaseModel):
    risk_score: float = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    uncertainty: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    top_factors: List[str]
    explanation: str


class ImpactResult(BaseModel):
    affected_roads: int = Field(..., ge=0)
    affected_bridges: int = Field(..., ge=0)
    affected_settlements: int = Field(..., ge=0)
    estimated_population: int = Field(..., ge=0)
    impact_level: ImpactLevel


class DecisionResult(BaseModel):
    recommended_actions: List[str]
    urgency: UrgencyLevel
    rationale: str


class DataQuality(BaseModel):
    completeness_score: float = Field(..., ge=0, le=1)
    missing_fields: List[str]
    satellite_available: bool


class FinalRiskIntelligence(BaseModel):
    """The single object returned by POST /risk/analyze. Everything
    downstream (frontend, alerts, dashboards) consumes this shape."""
    location: Location
    input_data: RiskAnalysisRequest
    risk: RiskResult
    impact: ImpactResult
    decision: DecisionResult
    timestamp: datetime
    data_quality: DataQuality
    feedback_status: FeedbackStatus = FeedbackStatus.PENDING


# ---------------------------------------------------------------------------
# Feedback / learning loop models
# ---------------------------------------------------------------------------

class FeedbackSubmission(BaseModel):
    """What an authority/field officer submits after a prediction."""
    prediction_id: Optional[str] = Field(
        None, description="optional id linking back to a specific FinalRiskIntelligence output"
    )
    location: Location
    predicted_risk_level: RiskLevel
    observed_condition: str = Field(..., description="free-text field observation")
    landslide_occurred: bool
    notes: Optional[str] = None


class FeedbackRecord(FeedbackSubmission):
    """What gets stored — the submission plus server-assigned metadata."""
    feedback_id: str
    received_at: datetime
