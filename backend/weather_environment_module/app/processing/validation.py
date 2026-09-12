"""
Validation utilities: coordinate validity, NER-region membership,
physically-plausible value ranges, and timestamp sanity checks.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence

from app.config import get_settings


def is_valid_coordinate(latitude: float, longitude: float) -> bool:
    """Basic sanity check: finite numbers within global lat/lon ranges."""
    if latitude is None or longitude is None:
        return False
    if any(math.isnan(v) or math.isinf(v) for v in (latitude, longitude)):
        return False
    return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0


def is_within_ner_bbox(latitude: float, longitude: float) -> bool:
    """
    Checks whether a coordinate falls within an APPROXIMATE bounding box for
    India's North Eastern Region (Arunachal Pradesh, Assam, Manipur,
    Meghalaya, Mizoram, Nagaland, Sikkim, Tripura).

    This is NOT an authoritative administrative boundary check. It is a
    coarse rectangular filter intended to catch obviously out-of-region
    requests. The module is structured so that a proper GeoJSON polygon
    boundary (e.g. from Survey of India / state shapefiles) can later
    replace this bounding-box check inside this same function, without
    changing any caller.
    """
    settings = get_settings()
    min_lat, min_lon, max_lat, max_lon = settings.NER_BOUNDING_BOX
    return min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon


def is_physically_plausible_rainfall(value_mm: Optional[float], window_hours: float = 1.0) -> bool:
    """
    Flags physically implausible rainfall values (e.g. negative rainfall,
    or an hourly rate implying more than MAX_REASONABLE_HOURLY_RAINFALL_MM/hr).
    """
    if value_mm is None:
        return True  # missing is a different concern (handled by quality layer)
    if value_mm < 0:
        return False
    settings = get_settings()
    max_allowed = settings.MAX_REASONABLE_HOURLY_RAINFALL_MM * max(window_hours, 1e-6)
    return value_mm <= max_allowed


def is_plausible_temperature(value_c: Optional[float]) -> bool:
    if value_c is None:
        return True
    return -40.0 <= value_c <= 55.0


def is_plausible_humidity(value_pct: Optional[float]) -> bool:
    if value_pct is None:
        return True
    return 0.0 <= value_pct <= 100.0


def is_plausible_soil_moisture(value_m3m3: Optional[float]) -> bool:
    if value_m3m3 is None:
        return True
    return 0.0 <= value_m3m3 <= 1.0


def find_duplicate_timestamps(timestamps: Sequence[datetime]) -> List[datetime]:
    seen = set()
    dupes = set()
    for t in timestamps:
        if t in seen:
            dupes.add(t)
        seen.add(t)
    return sorted(dupes)


def find_temporal_gaps(timestamps: Sequence[datetime], expected_interval_hours: float = 1.0, tolerance: float = 1.5):
    """Returns list of (start, end) gaps larger than expected_interval_hours * tolerance."""
    gaps = []
    ordered = sorted(timestamps)
    for prev, curr in zip(ordered, ordered[1:]):
        delta_hours = (curr - prev).total_seconds() / 3600.0
        if delta_hours > expected_interval_hours * tolerance:
            gaps.append((prev, curr))
    return gaps


def data_age_minutes(observation_timestamp: datetime, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    if observation_timestamp.tzinfo is None:
        observation_timestamp = observation_timestamp.replace(tzinfo=timezone.utc)
    return max((now - observation_timestamp).total_seconds() / 60.0, 0.0)


def is_stale(observation_timestamp: datetime, now: Optional[datetime] = None) -> bool:
    settings = get_settings()
    return data_age_minutes(observation_timestamp, now) > settings.STALE_OBSERVATION_MINUTES
