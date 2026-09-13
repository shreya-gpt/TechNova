"""
Pydantic data models.

These define the JSON contract exposed to the rest of the platform,
in particular the AI / Risk Engine. Keeping these in one place makes the
contract easy to review and version.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------
class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    @field_validator("latitude", "longitude")
    @classmethod
    def finite(cls, v: float) -> float:
        if v != v:  # NaN check
            raise ValueError("coordinate must be a finite number")
        return v


class DataSourceType(str, Enum):
    OPEN_METEO = "open_meteo"
    IMD = "imd"
    NASA_POWER = "nasa_power"
    SOIL_MOISTURE_PROVIDER = "soil_moisture_provider"
    DEMO = "demo"
    FALLBACK_CACHE = "fallback_cache"
    UNAVAILABLE = "unavailable"


class SourceMetadata(BaseModel):
    provider: DataSourceType
    reliability: float = Field(..., ge=0, le=1, description="Provider reliability score (0-1)")
    is_fallback: bool = False
    fetched_at: datetime
    notes: Optional[str] = None


# ---------------------------------------------------------------------
# Raw observation / weather responses
# ---------------------------------------------------------------------
class CurrentWeather(BaseModel):
    location: Location
    observation_timestamp: datetime
    rainfall_mm_last_hour: Optional[float] = None
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    soil_moisture_m3m3: Optional[float] = None
    source: SourceMetadata


class HistoricalWeatherPoint(BaseModel):
    timestamp: datetime
    rainfall_mm: Optional[float] = None
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    soil_moisture_m3m3: Optional[float] = None


class HistoricalWeatherResponse(BaseModel):
    location: Location
    start: datetime
    end: datetime
    points: List[HistoricalWeatherPoint]
    source: SourceMetadata


class ForecastPoint(BaseModel):
    timestamp: datetime
    rainfall_mm: Optional[float] = None
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None


class ForecastResponse(BaseModel):
    location: Location
    generated_at: datetime
    points: List[ForecastPoint]
    source: SourceMetadata


# ---------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------
class QualityFlag(str, Enum):
    MISSING_RAINFALL = "MISSING_RAINFALL"
    MISSING_SOIL_MOISTURE = "MISSING_SOIL_MOISTURE"
    MISSING_TEMPERATURE = "MISSING_TEMPERATURE"
    MISSING_HUMIDITY = "MISSING_HUMIDITY"
    MISSING_FORECAST = "MISSING_FORECAST"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    STALE_RAINFALL = "STALE_RAINFALL"
    DUPLICATE_TIMESTAMPS = "DUPLICATE_TIMESTAMPS"
    INVALID_COORDINATES = "INVALID_COORDINATES"
    OUTSIDE_NER_REGION = "OUTSIDE_NER_REGION"
    IMPOSSIBLE_MEASUREMENT = "IMPOSSIBLE_MEASUREMENT"
    SUSPICIOUS_SPIKE = "SUSPICIOUS_SPIKE"
    TEMPORAL_GAP = "TEMPORAL_GAP"
    API_FAILURE = "API_FAILURE"
    FORECAST_SOURCE_UNAVAILABLE = "FORECAST_SOURCE_UNAVAILABLE"
    INCONSISTENT_UNITS = "INCONSISTENT_UNITS"
    DEMO_DATA = "DEMO_DATA"
    FALLBACK_SOURCE_USED = "FALLBACK_SOURCE_USED"
    INSUFFICIENT_HISTORY_FOR_ANOMALY = "INSUFFICIENT_HISTORY_FOR_ANOMALY"


class DataQuality(BaseModel):
    score: float = Field(..., ge=0, le=1, description="Overall environmental data quality score (0=unusable, 1=excellent)")
    flags: List[QualityFlag] = Field(default_factory=list)
    data_age_minutes: Optional[float] = None
    environmental_confidence: float = Field(
        ..., ge=0, le=1,
        description="Confidence in the environmental feature vector itself. "
                    "NOT the final landslide probability, which is produced by the Risk Engine.",
    )


# ---------------------------------------------------------------------
# Environmental features / indicators (the core contract)
# ---------------------------------------------------------------------
class EnvironmentalFeatures(BaseModel):
    rainfall_1h_mm: Optional[float] = None
    rainfall_3h_mm: Optional[float] = None
    rainfall_6h_mm: Optional[float] = None
    rainfall_12h_mm: Optional[float] = None
    rainfall_24h_mm: Optional[float] = None
    rainfall_48h_mm: Optional[float] = None
    rainfall_72h_mm: Optional[float] = None
    rainfall_7d_mm: Optional[float] = None

    rainfall_intensity_mm_per_hr: Optional[float] = None
    rolling_rainfall_intensity_mm_per_hr: Optional[float] = None

    antecedent_precipitation_index: Optional[float] = None
    rainfall_anomaly_pct: Optional[float] = Field(
        default=None, description="Percent deviation from historical mean for same period, if history available"
    )
    rainfall_percentile: Optional[float] = Field(
        default=None, description="Percentile of rainfall_24h_mm vs. historical distribution (0-100)"
    )

    forecast_rainfall_3h_mm: Optional[float] = None
    forecast_rainfall_6h_mm: Optional[float] = None
    forecast_rainfall_12h_mm: Optional[float] = None
    forecast_rainfall_24h_mm: Optional[float] = None
    forecast_rainfall_48h_mm: Optional[float] = None

    soil_moisture_m3m3: Optional[float] = None
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None

    rainfall_acceleration_mm_per_hr2: Optional[float] = Field(
        default=None, description="Change in rainfall intensity over recent windows"
    )


class EnvironmentalIndicators(BaseModel):
    heavy_rainfall_flag: bool = False
    extreme_accumulation_flag: bool = False
    persistent_rainfall_flag: bool = False
    high_soil_moisture_flag: bool = False
    forecast_heavy_rainfall_flag: bool = False
    antecedent_wetness_level: str = Field(default="unknown", description="one of: low, moderate, high, very_high, unknown")
    notes: List[str] = Field(default_factory=list)


class RiskFeatureResponse(BaseModel):
    """
    Primary contract consumed by the downstream AI / Risk Engine.
    This module reports ENVIRONMENTAL EVIDENCE ONLY.
    It never outputs a landslide probability.
    """
    location: Location
    timestamp: datetime
    environmental_features: EnvironmentalFeatures
    environmental_indicators: EnvironmentalIndicators
    data_quality: DataQuality
    sources: List[SourceMetadata]
    disclaimer: str = Field(
        default=(
            "This response contains environmental observations/features only. "
            "It is NOT a landslide prediction or probability. Thresholds used for "
            "indicator flags are prototype defaults requiring local calibration. "
            "Final risk assessment is produced by a separate Risk Engine that fuses "
            "this data with terrain, geology, satellite imagery, historical landslide "
            "records and infrastructure exposure."
        )
    )


class BatchRequestItem(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: Optional[datetime] = None


class BatchRequest(BaseModel):
    items: List[BatchRequestItem] = Field(..., min_length=1)


class BatchResponse(BaseModel):
    results: List[RiskFeatureResponse]
    errors: List[Dict[str, str]] = Field(default_factory=list)
