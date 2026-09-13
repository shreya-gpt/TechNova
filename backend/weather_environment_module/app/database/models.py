"""
SQLAlchemy ORM models.

Prototype persistence uses SQLite (file-based, zero setup - ideal for a
SIH demo). The schema is intentionally simple and free of SQLite-specific
types so migrating to PostgreSQL/PostGIS later mainly means changing
DATABASE_URL and adding a geometry column for coordinates.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class EnvironmentalObservation(Base):
    """
    Stores one processed environmental-feature snapshot for a location and
    timestamp, including provenance (source, quality) so the platform has
    an auditable history of what was served to the Risk Engine.
    """

    __tablename__ = "environmental_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    requested_timestamp = Column(DateTime, nullable=False, index=True)

    # Raw-ish inputs (for traceability)
    raw_rainfall_1h_mm = Column(Float, nullable=True)
    raw_temperature_c = Column(Float, nullable=True)
    raw_relative_humidity_pct = Column(Float, nullable=True)
    raw_soil_moisture_m3m3 = Column(Float, nullable=True)

    # Processed features (subset persisted for querying/analytics)
    rainfall_24h_mm = Column(Float, nullable=True)
    rainfall_72h_mm = Column(Float, nullable=True)
    rainfall_7d_mm = Column(Float, nullable=True)
    antecedent_precipitation_index = Column(Float, nullable=True)
    rainfall_anomaly_pct = Column(Float, nullable=True)
    forecast_rainfall_24h_mm = Column(Float, nullable=True)

    # Full feature/indicator/quality payloads, stored as JSON text for
    # flexibility while the schema is still evolving during the hackathon.
    features_json = Column(Text, nullable=True)
    indicators_json = Column(Text, nullable=True)

    data_source = Column(String(64), nullable=False)
    data_quality_score = Column(Float, nullable=False)
    quality_flags_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
