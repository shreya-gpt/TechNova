"""
mock_data.py
============
Realistic mock/sample data standing in for teammates' modules until they are
ready. `get_example_ner_request()` is used by GET /risk/example and by tests.

The example location is modeled loosely on the Sohra (Cherrapunji) area of
East Khasi Hills, Meghalaya — one of the wettest places on Earth and a
region with documented landslide activity along steep, geologically weak
terrain during the monsoon. Values are illustrative, not sourced from a
live feed.
"""

from schemas import (
    EnvironmentalData,
    Infrastructure,
    Location,
    RiskAnalysisRequest,
    SatelliteData,
    TerrainData,
)


def get_example_ner_request() -> RiskAnalysisRequest:
    """A single realistic NER location with high rainfall, high soil
    moisture, steep slope, weak geology, past landslide activity, and
    detected satellite surface change — engineered to produce a HIGH or
    CRITICAL risk score for demo purposes."""

    location = Location(
        latitude=25.2840,
        longitude=91.7273,
        district="East Khasi Hills",
        state="Meghalaya",
    )

    environmental = EnvironmentalData(
        rainfall_24h=220.0,      # very heavy monsoon rainfall
        rainfall_72h=430.0,
        forecast_rainfall=150.0,  # more heavy rain expected
        soil_moisture=88.0,       # near saturation
    )

    terrain = TerrainData(
        slope=42.0,               # steep
        elevation=1450.0,
        geology="weak_sedimentary_or_fractured",
        historical_landslide_density=8.0,  # high past activity
    )

    satellite = SatelliteData(
        satellite_available=True,
        surface_change_score=0.82,   # significant detected surface change
        vegetation_indicator=0.30,   # sparse vegetation, less root stabilization
    )

    infrastructure = Infrastructure(
        roads=12,
        bridges=3,
        settlements=6,
        hospitals=1,
        schools=2,
        estimated_population=4500,
    )

    return RiskAnalysisRequest(
        location=location,
        environmental=environmental,
        terrain=terrain,
        satellite=satellite,
        infrastructure=infrastructure,
    )
