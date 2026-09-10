"""
tests/test_pipeline.py
=======================
Integration-level tests for pipeline.run_risk_pipeline and the FastAPI app.
"""

import pytest
from pydantic import ValidationError

from mock_data import get_example_ner_request
from pipeline import run_risk_pipeline
from schemas import (
    EnvironmentalData,
    Infrastructure,
    Location,
    RiskAnalysisRequest,
    SatelliteData,
    TerrainData,
)


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

def test_valid_pipeline_end_to_end():
    request = get_example_ner_request()
    result = run_risk_pipeline(request)

    assert result.location.district == "East Khasi Hills"
    assert result.risk.risk_level.value in {"HIGH", "CRITICAL"}
    assert result.impact.estimated_population >= 0
    assert len(result.decision.recommended_actions) > 0
    assert result.data_quality.completeness_score > 0
    assert result.feedback_status.value == "PENDING"


def test_invalid_input_raises_validation_error():
    """Missing required fields (e.g. rainfall_24h, slope) must be rejected
    by Pydantic before the pipeline ever runs."""
    with pytest.raises(ValidationError):
        EnvironmentalData()  # rainfall_24h is required

    with pytest.raises(ValidationError):
        TerrainData()  # slope is required

    with pytest.raises(ValidationError):
        Location(latitude=200.0, longitude=91.0, district="X", state="Y")  # out of range


def test_risk_levels_vary_with_input_severity():
    low_request = RiskAnalysisRequest(
        location=Location(latitude=25.0, longitude=91.0, district="D", state="S"),
        environmental=EnvironmentalData(
            rainfall_24h=5.0, rainfall_72h=8.0, forecast_rainfall=0.0, soil_moisture=15.0
        ),
        terrain=TerrainData(slope=4.0, elevation=100.0, geology="stable_rock", historical_landslide_density=0.0),
        satellite=SatelliteData(satellite_available=True, surface_change_score=0.01, vegetation_indicator=0.9),
        infrastructure=Infrastructure(roads=5, bridges=1, settlements=2, estimated_population=1000),
    )
    critical_request = get_example_ner_request()

    low_result = run_risk_pipeline(low_request)
    critical_result = run_risk_pipeline(critical_request)

    assert low_result.risk.risk_score < critical_result.risk.risk_score
    assert low_result.risk.risk_level.value == "LOW"
    assert critical_result.risk.risk_level.value in {"HIGH", "CRITICAL"}


def test_missing_satellite_data_increases_pipeline_uncertainty():
    base_kwargs = dict(
        location=Location(latitude=25.0, longitude=91.0, district="D", state="S"),
        environmental=EnvironmentalData(
            rainfall_24h=100.0, rainfall_72h=200.0, forecast_rainfall=50.0, soil_moisture=60.0
        ),
        terrain=TerrainData(
            slope=30.0, elevation=800.0, geology="moderately_weathered", historical_landslide_density=3.0
        ),
        infrastructure=Infrastructure(roads=10, bridges=2, settlements=4, estimated_population=2000),
    )

    with_satellite = RiskAnalysisRequest(
        satellite=SatelliteData(satellite_available=True, surface_change_score=0.5, vegetation_indicator=0.5),
        **base_kwargs,
    )
    without_satellite = RiskAnalysisRequest(
        satellite=SatelliteData(satellite_available=False),
        **base_kwargs,
    )

    result_with = run_risk_pipeline(with_satellite)
    result_without = run_risk_pipeline(without_satellite)

    assert result_without.risk.uncertainty > result_with.risk.uncertainty
    assert "satellite.surface_change_score" in result_without.data_quality.missing_fields


def test_impact_assessment_scales_with_risk_level():
    request = get_example_ner_request()
    result = run_risk_pipeline(request)

    # CRITICAL/HIGH risk with nonzero infrastructure should produce nonzero impact
    assert result.impact.affected_settlements > 0
    assert result.impact.estimated_population > 0


def test_decision_recommendations_match_risk_level():
    request = get_example_ner_request()
    result = run_risk_pipeline(request)

    if result.risk.risk_level.value == "CRITICAL":
        assert any("emergency" in action.lower() for action in result.decision.recommended_actions)
    elif result.risk.risk_level.value == "HIGH":
        assert any("field" in action.lower() or "inspection" in action.lower() for action in result.decision.recommended_actions)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with feedback storage redirected to a temp file so tests
    never touch the real backend/data/feedback.json."""
    import config
    from fastapi.testclient import TestClient
    import services.feedback_service as feedback_service

    temp_feedback_file = tmp_path / "feedback.json"
    monkeypatch.setattr(config, "FEEDBACK_FILE", temp_feedback_file)
    monkeypatch.setattr(feedback_service, "FEEDBACK_FILE", temp_feedback_file)

    import main
    return TestClient(main.app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_risk_example_endpoint(client):
    response = client.get("/risk/example")
    assert response.status_code == 200
    body = response.json()
    assert body["risk"]["risk_level"] in {"HIGH", "CRITICAL"}
    assert body["location"]["state"] == "Meghalaya"


def test_risk_analyze_endpoint_valid_payload(client):
    payload = get_example_ner_request().model_dump()
    response = client.post("/risk/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["risk"]["risk_score"] > 0


def test_risk_analyze_endpoint_invalid_payload(client):
    response = client.post("/risk/analyze", json={"location": {"latitude": 999}})
    assert response.status_code == 422


def test_feedback_post_and_get_endpoints(client):
    submission = {
        "prediction_id": "test-123",
        "location": {"latitude": 25.28, "longitude": 91.72, "district": "East Khasi Hills", "state": "Meghalaya"},
        "predicted_risk_level": "HIGH",
        "observed_condition": "Minor surface cracking observed, no slope failure yet.",
        "landslide_occurred": False,
        "notes": "Follow-up inspection scheduled next week.",
    }
    post_response = client.post("/feedback", json=submission)
    assert post_response.status_code == 200
    assert post_response.json()["prediction_id"] == "test-123"

    get_response = client.get("/feedback")
    assert get_response.status_code == 200
    records = get_response.json()
    assert len(records) == 1
    assert records[0]["observed_condition"].startswith("Minor surface cracking")
