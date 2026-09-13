"""
services/impact_service.py
===========================
Impact assessment using real GIS spatial intersection.

Takes the predicted landslide location and risk level, builds a risk-zone
polygon (see GIS/risk_zone.py), and intersects it against real roads/
bridges/settlements data (see GIS/impact_zone.py) to determine actual
affected assets — replacing the earlier placeholder exposure-fraction logic.
"""

from __future__ import annotations

import sys
import os


def _find_project_root(marker_folder="GIS", start_path=None):
    """Walk upward from this file's location until a folder containing
    `marker_folder` is found, and return that parent path."""
    current = os.path.abspath(start_path or os.path.dirname(__file__))
    while True:
        if os.path.isdir(os.path.join(current, marker_folder)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError(f"Could not find a '{marker_folder}' folder above {__file__}")
        current = parent


PROJECT_ROOT = _find_project_root("GIS")
sys.path.append(PROJECT_ROOT)

from schemas import ImpactLevel, ImpactResult, RiskResult
from GIS.risk_zone import create_risk_zone
from GIS.impact_zone import compute_impact as _gis_compute_impact

INFRA_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "infrastructure")


def assess_impact(
    risk: RiskResult,
    latitude: float,
    longitude: float,
    radius_km: float = 1.0,
) -> ImpactResult:
    """
    Builds a risk-zone polygon around (latitude, longitude) and performs
    real spatial intersection against roads/bridges/settlements to produce
    the actual ImpactResult.
    """
    zone = create_risk_zone(
        latitude=latitude,
        longitude=longitude,
        risk_level=risk.risk_level.value,
        radius_km=radius_km,
    )

    gis_result = _gis_compute_impact(zone, INFRA_DATA_DIR)

    return ImpactResult(
        affected_roads=gis_result.affected_roads,
        affected_bridges=gis_result.affected_bridges,
        affected_settlements=gis_result.affected_settlements,
        estimated_population=gis_result.estimated_population,
        impact_level=ImpactLevel(gis_result.impact_level),
    )

if __name__ == "__main__":
    from schemas import RiskLevel

    # Dummy risk result for testing
    test_risk = RiskResult(
        risk_score=70,
        risk_level=RiskLevel.HIGH,
        uncertainty=0.2,
        confidence=0.8,
        top_factors=["steep slope"],
        explanation="Test run"
    )

    test_lat, test_lon = 27.30, 92.40

    result = assess_impact(test_risk, test_lat, test_lon, radius_km=1.0)
    print(result)