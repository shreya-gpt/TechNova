import os

os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Gangtok, Sikkim - inside the NER approximate bounding box.
NER_LAT, NER_LON = 27.33, 88.61


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "demo_mode" in body


def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["primary_endpoint"] == "/environment/risk-features"


def test_weather_current_endpoint():
    resp = client.get("/weather/current", params={"latitude": NER_LAT, "longitude": NER_LON})
    assert resp.status_code == 200
    body = resp.json()
    assert "rainfall_mm_last_hour" in body


def test_weather_forecast_endpoint():
    resp = client.get(
        "/weather/forecast", params={"latitude": NER_LAT, "longitude": NER_LON, "hours_ahead": 12}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 12


def test_weather_historical_endpoint():
    resp = client.get(
        "/weather/historical",
        params={
            "latitude": NER_LAT,
            "longitude": NER_LON,
            "start": "2026-06-01T00:00:00Z",
            "end": "2026-06-02T00:00:00Z",
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["points"]) > 0


def test_weather_historical_rejects_bad_range():
    resp = client.get(
        "/weather/historical",
        params={
            "latitude": NER_LAT,
            "longitude": NER_LON,
            "start": "2026-06-02T00:00:00Z",
            "end": "2026-06-01T00:00:00Z",
        },
    )
    assert resp.status_code == 400


def test_environment_risk_features_endpoint_contract():
    resp = client.get(
        "/environment/risk-features", params={"latitude": NER_LAT, "longitude": NER_LON}
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["location"]["latitude"] == NER_LAT
    assert "environmental_features" in body
    assert "environmental_indicators" in body
    assert "data_quality" in body
    assert "sources" in body
    assert 0.0 <= body["data_quality"]["score"] <= 1.0
    assert "rainfall_24h_mm" in body["environmental_features"]
    assert "landslide" not in body["environmental_indicators"]  # no bogus probability field
    assert "disclaimer" in body


def test_environment_features_alias_matches_risk_features_shape():
    resp = client.get(
        "/environment/features", params={"latitude": NER_LAT, "longitude": NER_LON}
    )
    assert resp.status_code == 200
    assert "environmental_features" in resp.json()


def test_environment_risk_features_rejects_invalid_coordinates():
    resp = client.get("/environment/risk-features", params={"latitude": 999, "longitude": 88.6})
    assert resp.status_code in (400, 422)


def test_environment_batch_endpoint():
    payload = {
        "items": [
            {"latitude": NER_LAT, "longitude": NER_LON},
            {"latitude": 26.14, "longitude": 91.73},  # Guwahati, Assam
        ]
    }
    resp = client.post("/environment/batch", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["errors"] == []


def test_environment_batch_rejects_oversized_batch():
    payload = {"items": [{"latitude": NER_LAT, "longitude": NER_LON} for _ in range(51)]}
    resp = client.post("/environment/batch", json=payload)
    assert resp.status_code == 400
