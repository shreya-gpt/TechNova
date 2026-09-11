"""
tests/test_pipeline.py
========================
Integration-level tests for backend.pipeline.run_risk_pipeline and the
FastAPI app, plus a check that everything is importable from the
repository root the way `python -m pytest` and `uvicorn backend.main:app`
both require.
"""

import pytest
from pydantic import ValidationError

from backend.mock_data import get_example_ner_request
from backend.pipeline import run_risk_pipeline
from backend.schemas import (
    EnvironmentalData,
    Infrastructure,
    Location,
    RiskAnalysisRequest,
    SatelliteData,
    TerrainData,
)


# ---------------------------------------------------------------------------
# Repository-root import sanity check
# ---------------------------------------------------------------------------

def test_backend_package_imports_from_repository_root():
    """These imports only succeed if the repository root (not backend/) is
    on sys.path — exactly the setup `python -m pytest` and
    `uvicorn backend.main:app --reload` both rely on. If this test file's
    top-level imports above worked at all, this is already proven; this
    test just makes that guarantee explicit and checks a few submodules
    directly, including ones several import-levels deep."""
    import backend
    import backend.main
    import backend.pipeline
    import backend.schemas
    import backend.config
    import backend.providers
    import backend.adapters.base
    import backend.adapters.mock_providers
    import backend.services.risk_service
    import backend.services.feedback_service
    import backend.services.prediction_store

    assert hasattr(backend.main, "app")
    assert hasattr(backend.pipeline, "run_risk_pipeline")


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
    assert result.data_quality.status.value in {"GOOD", "DEGRADED", "POOR"}
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
    assert result_without.data_quality.satellite_available is False


def test_missing_optional_environmental_data_reflected_in_data_quality():
    request = RiskAnalysisRequest(
        location=Location(latitude=25.0, longitude=91.0, district="D", state="S"),
        environmental=EnvironmentalData(rainfall_24h=80.0),  # everything else optional omitted
        terrain=TerrainData(slope=15.0),
        satellite=SatelliteData(satellite_available=True, surface_change_score=0.4),
        infrastructure=Infrastructure(roads=4, bridges=1, settlements=1, estimated_population=500),
    )

    result = run_risk_pipeline(request)

    assert "environmental.rainfall_72h" in result.data_quality.missing_fields
    assert "environmental.forecast_rainfall" in result.data_quality.missing_fields
    assert "environmental.soil_moisture" in result.data_quality.missing_fields
    assert result.data_quality.completeness_score < 1.0


def test_impact_assessment_scales_with_risk_level():
    request = get_example_ner_request()
    result = run_risk_pipeline(request)

    assert result.impact.affected_settlements > 0
    assert result.impact.estimated_population > 0


def test_decision_recommendations_match_risk_level():
    request = get_example_ner_request()
    result = run_risk_pipeline(request)

    if result.risk.risk_level.value == "CRITICAL":
        assert any("emergency" in action.lower() for action in result.decision.recommended_actions)
    elif result.risk.risk_level.value == "HIGH":
        assert any(
            "field" in action.lower() or "inspection" in action.lower()
            for action in result.decision.recommended_actions
        )


# ---------------------------------------------------------------------------
# prediction_id tests
# ---------------------------------------------------------------------------

def test_prediction_id_is_present_and_unique():
    request = get_example_ner_request()

    result_1 = run_risk_pipeline(request)
    result_2 = run_risk_pipeline(request)

    assert result_1.prediction_id
    assert result_2.prediction_id
    assert result_1.prediction_id != result_2.prediction_id


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with prediction/feedback storage redirected to temp files
    so tests never touch the real backend/data/*.json."""
    from fastapi.testclient import TestClient

    import backend.config as config
    import backend.services.feedback_service as feedback_service
    import backend.services.prediction_store as prediction_store

    temp_feedback_file = tmp_path / "feedback.json"
    temp_predictions_file = tmp_path / "predictions.json"

    monkeypatch.setattr(config, "FEEDBACK_FILE", temp_feedback_file)
    monkeypatch.setattr(config, "PREDICTIONS_FILE", temp_predictions_file)
    monkeypatch.setattr(feedback_service, "FEEDBACK_FILE", temp_feedback_file)
    monkeypatch.setattr(feedback_service, "PREDICTIONS_FILE", temp_predictions_file)
    monkeypatch.setattr(prediction_store, "PREDICTIONS_FILE", temp_predictions_file)

    import backend.main as main

    # main.py's endpoints call save_prediction/submit_feedback with default
    # argument values captured at import time, so patch the bound names
    # main actually calls, not just the source modules.
    monkeypatch.setattr(main, "save_prediction", lambda result: prediction_store.save_prediction(
        result, predictions_file=temp_predictions_file
    ))

    def _submit_feedback_with_temp_files(submission):
        return feedback_service.submit_feedback(
            submission, feedback_file=temp_feedback_file, predictions_file=temp_predictions_file
        )

    monkeypatch.setattr(main, "submit_feedback", _submit_feedback_with_temp_files)
    monkeypatch.setattr(
        main, "get_all_feedback", lambda: feedback_service.get_all_feedback(feedback_file=temp_feedback_file)
    )

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
    assert body["prediction_id"]


def test_risk_analyze_endpoint_valid_payload(client):
    payload = get_example_ner_request().model_dump()
    response = client.post("/risk/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["risk"]["risk_score"] > 0
    assert body["prediction_id"]
    assert len(body["risk"]["factor_contributions"]) > 0


def test_risk_analyze_endpoint_invalid_payload(client):
    response = client.post("/risk/analyze", json={"location": {"latitude": 999}})
    assert response.status_code == 422


def test_feedback_linked_to_prediction_end_to_end(client):
    """Full loop: analyze -> get prediction_id -> submit feedback referencing
    it -> feedback record carries the correct location/predicted_risk_level
    looked up from that exact prediction."""
    analyze_response = client.post("/risk/analyze", json=get_example_ner_request().model_dump())
    assert analyze_response.status_code == 200
    prediction = analyze_response.json()
    prediction_id = prediction["prediction_id"]

    feedback_payload = {
        "prediction_id": prediction_id,
        "observed_condition": "Minor surface cracking observed, no slope failure yet.",
        "landslide_occurred": False,
        "notes": "Follow-up inspection scheduled next week.",
    }
    feedback_response = client.post("/feedback", json=feedback_payload)
    assert feedback_response.status_code == 200
    feedback_body = feedback_response.json()

    assert feedback_body["prediction_id"] == prediction_id
    assert feedback_body["predicted_risk_level"] == prediction["risk"]["risk_level"]
    assert feedback_body["location"]["district"] == prediction["location"]["district"]

    get_response = client.get("/feedback")
    assert get_response.status_code == 200
    records = get_response.json()
    assert len(records) == 1
    assert records[0]["prediction_id"] == prediction_id


def test_feedback_with_unknown_prediction_id_returns_404(client):
    feedback_payload = {
        "prediction_id": "does-not-exist",
        "observed_condition": "N/A",
        "landslide_occurred": False,
    }
    response = client.post("/feedback", json=feedback_payload)
    assert response.status_code == 404
