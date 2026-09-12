"""
Repository layer: encapsulates all SQL/ORM access so services never talk
to SQLAlchemy directly. This keeps a future Postgres/PostGIS migration
confined to this file.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.models import Base, EnvironmentalObservation
from app.models.schemas import RiskFeatureResponse


def _make_engine():
    settings = get_settings()
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        # Ensure the directory for the sqlite file exists.
        path_part = url.split("///")[-1]
        directory = os.path.dirname(path_part)
        if directory:
            os.makedirs(directory, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


_engine = _make_engine()
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=_engine)


class ObservationRepository:
    def __init__(self, session: Optional[Session] = None):
        self._own_session = session is None
        self.session: Session = session or SessionLocal()

    def __enter__(self) -> "ObservationRepository":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._own_session:
            self.session.close()

    def save_risk_feature_response(self, response: RiskFeatureResponse) -> EnvironmentalObservation:
        f = response.environmental_features
        record = EnvironmentalObservation(
            latitude=response.location.latitude,
            longitude=response.location.longitude,
            requested_timestamp=response.timestamp.replace(tzinfo=None),
            raw_rainfall_1h_mm=f.rainfall_1h_mm,
            raw_temperature_c=f.temperature_c,
            raw_relative_humidity_pct=f.relative_humidity_pct,
            raw_soil_moisture_m3m3=f.soil_moisture_m3m3,
            rainfall_24h_mm=f.rainfall_24h_mm,
            rainfall_72h_mm=f.rainfall_72h_mm,
            rainfall_7d_mm=f.rainfall_7d_mm,
            antecedent_precipitation_index=f.antecedent_precipitation_index,
            rainfall_anomaly_pct=f.rainfall_anomaly_pct,
            forecast_rainfall_24h_mm=f.forecast_rainfall_24h_mm,
            features_json=response.environmental_features.model_dump_json(),
            indicators_json=response.environmental_indicators.model_dump_json(),
            data_source=response.sources[0].provider.value if response.sources else "unknown",
            data_quality_score=response.data_quality.score,
            quality_flags_json=json.dumps([f.value for f in response.data_quality.flags]),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_recent(self, latitude: float, longitude: float, limit: int = 10) -> List[EnvironmentalObservation]:
        return (
            self.session.query(EnvironmentalObservation)
            .filter(EnvironmentalObservation.latitude == latitude, EnvironmentalObservation.longitude == longitude)
            .order_by(EnvironmentalObservation.created_at.desc())
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        return self.session.query(EnvironmentalObservation).count()
