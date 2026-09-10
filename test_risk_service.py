"""
tests/test_risk_service.py
===========================
Unit tests for the baseline risk engine in services/risk_service.py.
"""

from config import RISK_WEIGHTS
from schemas import EnvironmentalData, SatelliteData, TerrainData
from services.risk_service import calculate_risk


def test_weights_sum_to_one():
    """The risk-weight config must sum to 1.0, or the weighted-average math
    in calculate_risk breaks its own assumptions."""
    assert abs(sum(RISK_WEIGHTS.values()) - 1.0) < 1e-9


def test_high_risk_scenario_produces_high_or_critical():
    environmental = EnvironmentalData(
        rainfall_24h=220.0, rainfall_72h=430.0, forecast_rainfall=150.0, soil_moisture=88.0
    )
    terrain = TerrainData(
        slope=42.0, elevation=1450.0, geology="weak_sedimentary_or_fractured",
        historical_landslide_density=8.0,
    )
    satellite = SatelliteData(satellite_available=True, surface_change_score=0.82, vegetation_indicator=0.3)

    result = calculate_risk(environmental, terrain, satellite)

    assert result.risk_level.value in {"HIGH", "CRITICAL"}
    assert 0 <= result.risk_score <= 100
    assert len(result.top_factors) > 0
    assert "Risk is" in result.explanation


def test_low_risk_scenario_produces_low():
    environmental = EnvironmentalData(
        rainfall_24h=5.0, rainfall_72h=10.0, forecast_rainfall=0.0, soil_moisture=20.0
    )
    terrain = TerrainData(
        slope=5.0, elevation=200.0, geology="stable_rock", historical_landslide_density=0.0
    )
    satellite = SatelliteData(satellite_available=True, surface_change_score=0.02, vegetation_indicator=0.9)

    result = calculate_risk(environmental, terrain, satellite)

    assert result.risk_level.value == "LOW"


def test_confidence_is_exactly_one_minus_uncertainty():
    environmental = EnvironmentalData(rainfall_24h=50.0)
    terrain = TerrainData(slope=20.0)
    satellite = SatelliteData(satellite_available=True)

    result = calculate_risk(environmental, terrain, satellite)

    assert result.confidence == round(1 - result.uncertainty, 4)


def test_missing_satellite_data_increases_uncertainty():
    environmental = EnvironmentalData(
        rainfall_24h=100.0, rainfall_72h=200.0, forecast_rainfall=50.0, soil_moisture=60.0
    )
    terrain = TerrainData(
        slope=30.0, elevation=800.0, geology="moderately_weathered", historical_landslide_density=3.0
    )

    satellite_available = SatelliteData(satellite_available=True, surface_change_score=0.5, vegetation_indicator=0.5)
    satellite_unavailable = SatelliteData(satellite_available=False)

    result_with_satellite = calculate_risk(environmental, terrain, satellite_available)
    result_without_satellite = calculate_risk(environmental, terrain, satellite_unavailable)

    assert result_without_satellite.uncertainty > result_with_satellite.uncertainty
    assert result_without_satellite.confidence < result_with_satellite.confidence


def test_missing_optional_fields_do_not_crash_and_still_produce_top_factors():
    """Only rainfall_24h and slope are required; everything else is Optional."""
    environmental = EnvironmentalData(rainfall_24h=150.0)
    terrain = TerrainData(slope=35.0)
    satellite = SatelliteData(satellite_available=False)

    result = calculate_risk(environmental, terrain, satellite)

    assert 0 <= result.risk_score <= 100
    assert result.risk_level.value in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert isinstance(result.top_factors, list)
