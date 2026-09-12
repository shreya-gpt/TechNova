from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "endpoints" in body


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")


def test_analyze_endpoint_returns_expected_schema():
    payload = {
        "aoi_id": "NER-TEST-AOI",
        "min_lat": 25.55,
        "min_lon": 91.85,
        "max_lat": 25.60,
        "max_lon": 91.90,
        "pre_date": "2026-08-01",
        "post_date": "2026-09-01",
        "use_sar_fallback": True,
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["aoi_id"] == "NER-TEST-AOI"
    for field in (
        "change_score", "landslide_cv_probability", "vegetation_loss",
        "surface_displacement_mm", "water_accumulation_score",
        "confidence", "data_sources", "explanation",
    ):
        assert field in body

    assert 0.0 <= body["change_score"] <= 1.0
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["explanation"], list)


def test_analyze_endpoint_invalid_payload_returns_422():
    response = client.post("/analyze", json={"aoi_id": "missing-fields-only"})
    assert response.status_code == 422
