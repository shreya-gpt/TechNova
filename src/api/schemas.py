"""
Pydantic schemas for the module's public API — this is the authoritative
contract for the data handed to the central AI Risk Engine and GIS dashboard.

Design choice — why engineered features + a probability + confidence, rather
than raw imagery or a raw embedding:
  - Raw imagery: far too large to fuse cheaply/repeatedly with tabular
    rainfall/soil/slope data, and not directly interpretable by a fusion model.
  - Raw embeddings: powerful, but opaque — fails the explainability
    requirement, and couples the risk engine tightly to this module's
    specific CV architecture.
  - Engineered features + probability + confidence (what is used here):
    compact, directly interpretable, easy to fuse (simple concatenation or
    weighted scoring in the central engine), and stable even if the
    underlying CV model changes.
  An optional `embedding` field is included for a later fusion upgrade path
  (e.g. feeding a learned multimodal fusion model) without breaking the v1
  contract for teams that only consume the interpretable fields.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class SceneAnalysisRequest(BaseModel):
    aoi_id: str = Field(..., description="Unique identifier for the area of interest")
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    pre_date: date = Field(..., description="Date of the 'before' scene")
    post_date: date = Field(..., description="Date of the 'after' scene")
    use_sar_fallback: bool = Field(
        True, description="If optical is too cloudy, fall back to Sentinel-1 SAR change/coherence"
    )


class SatelliteRiskIndicatorsResponse(BaseModel):
    aoi_id: str
    latitude: float
    longitude: float
    observation_date: date

    change_score: float = Field(..., ge=0, le=1, description="Multi-index change-vector magnitude, normalized 0-1")
    landslide_cv_probability: float = Field(..., ge=0, le=1, description="U-Net segmentation mean probability over AOI")
    vegetation_loss: float = Field(..., ge=0, le=1, description="Fraction of AOI with significant NDVI drop")
    ndvi_delta: float = Field(..., description="Mean NDVI(post) - NDVI(pre) over AOI")
    ndwi_delta: float = Field(..., description="Mean NDWI(post) - NDWI(pre) over AOI")
    surface_displacement_mm: float = Field(..., description="Mean InSAR-proxy line-of-sight displacement, mm")
    water_accumulation_score: float = Field(..., ge=0, le=1, description="Normalized increase in surface water/pooling")
    road_disruption_score: float = Field(..., ge=0, le=1, description="Heuristic road/debris blockage signature score")

    confidence: float = Field(..., ge=0, le=1, description="Overall confidence blending CV, InSAR coherence and cloud cover")
    data_sources: List[str] = Field(..., description="Which satellite sources contributed, e.g. ['sentinel-2','sentinel-1']")
    explanation: List[str] = Field(..., description="Human-readable evidence bullets for this detection")

    embedding: Optional[List[float]] = Field(
        None, description="Optional learned feature embedding for advanced fusion models (v2 upgrade path)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "aoi_id": "NER-MEG-0142",
                "latitude": 25.5788,
                "longitude": 91.8933,
                "observation_date": "2026-09-10",
                "change_score": 0.71,
                "landslide_cv_probability": 0.63,
                "vegetation_loss": 0.24,
                "ndvi_delta": -0.31,
                "ndwi_delta": 0.05,
                "surface_displacement_mm": 18.4,
                "water_accumulation_score": 0.42,
                "road_disruption_score": 0.10,
                "confidence": 0.78,
                "data_sources": ["sentinel-2", "sentinel-1"],
                "explanation": [
                    "24% vegetation loss detected in AOI",
                    "18.4 mm ground displacement detected (InSAR proxy)",
                    "Significant multi-index surface change detected (change score 0.71)",
                ],
            }
        }


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
