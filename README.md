# NER Landslide Risk Intelligence — Backend / Integration Layer

Central backend for the SIH 2026 "AI-powered Landslide Risk Intelligence and
Early Warning Platform" for the North Eastern Region (NER) of India.

This is the **integration lead's part** of a 6-person team: it does not
build the weather, GIS, satellite, risk-model, or frontend modules — it
provides the pipeline, adapter interfaces, and API that combine their
outputs into one coherent flow:

```
Weather/Environmental Module
        ↓
GIS/Terrain Module
        ↓
Satellite Module
        ↓
Historical Data
        ↓
CENTRAL INTEGRATION PIPELINE  (backend/pipeline.py)
        ↓
Risk Engine  (RiskModelProvider — prototype baseline today)
        ↓
Risk + Uncertainty + Explainability
        ↓
Impact Assessment  (ImpactProvider — rule-based today)
        ↓
Decision/Recommendation Engine
        ↓
API  (FastAPI)
        ↓
Frontend
```

## Status of the risk model

**The risk engine (`backend/services/risk_service.py`, wrapped by
`BaselineRiskModelProvider`) is a transparent, weighted-factor PROTOTYPE —
not a scientifically validated landslide model.** It exists so the full
pipeline is runnable and demoable today. All weights and thresholds are
documented and isolated in `backend/config.py` so the real model can be
swapped in later (see "How teammates plug their modules in" below).

## Architecture

```
repo-root/
├── pytest.ini              pythonpath=. so tests import `backend` from anywhere
├── conftest.py              defensive sys.path fallback
├── requirements.txt
├── README.md
├── backend/
│   ├── __init__.py           makes `backend` an importable package
│   ├── main.py                 FastAPI app + routes
│   ├── schemas.py               Pydantic data contract (shared by all modules)
│   ├── pipeline.py               run_risk_pipeline() + assemble_request_from_providers()
│   ├── config.py                  Weights, thresholds, normalization ranges (documented placeholders)
│   ├── mock_data.py                 Realistic NER example, one function per provider
│   ├── providers.py                   Active provider bindings — the ONE place to swap mocks for real modules
│   ├── data/                            feedback.json / predictions.json (local storage, git-ignored)
│   ├── adapters/
│   │   ├── base.py                       Abstract interfaces: WeatherProvider, TerrainProvider,
│   │   │                                  SatelliteProvider, InfrastructureProvider,
│   │   │                                  RiskModelProvider, ImpactProvider
│   │   └── mock_providers.py               Current (mock/baseline) implementations of each interface
│   └── services/
│       ├── risk_service.py                  Baseline risk score, uncertainty, explainability
│       ├── impact_service.py                 Rule-based infrastructure/population exposure
│       ├── decision_service.py                Rule-based advisory recommendations
│       ├── feedback_service.py                 Feedback storage, linked to prediction_id
│       └── prediction_store.py                 Stores predictions so feedback can reference them
├── tests/
│   ├── test_pipeline.py       Pipeline + API endpoint tests + repo-root import check
│   ├── test_risk_service.py    Risk engine unit tests
│   └── test_feedback.py         Feedback/prediction-linking unit tests
└── docs/
    └── data_contract.md          Full schema reference for teammates
```

Every service function takes and returns plain Pydantic objects from
`schemas.py`. Every external data source or model (weather, terrain,
satellite, infrastructure, risk model, impact model) is accessed only
through an adapter interface in `backend/adapters/base.py`. To plug in a
teammate's real module later, you implement the matching interface and
change **one line** in `backend/providers.py` — `pipeline.py` and
`main.py` never need to change.

## Install (Windows 11 + VS Code, PowerShell)

```powershell
# From the repository root
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run this once as your user
(not admin), then retry:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Run the API — from the REPOSITORY ROOT

```powershell
uvicorn backend.main:app --reload
```

Do **not** `cd backend` first — the command above is written to run from
the repo root, and that's the only way that's supported now (this is one
of the things that was fixed from the original version). The API will be
live at `http://127.0.0.1:8000`, with interactive Swagger docs at
`http://127.0.0.1:8000/docs`.

## Run the tests — from the REPOSITORY ROOT

```powershell
python -m pytest
```

Plain `pytest` (no `-m`) also works, thanks to `pythonpath = .` in
`pytest.ini`. All 27 tests should pass.

```powershell
pytest -v
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/risk/analyze` | Run the full pipeline on a submitted `RiskAnalysisRequest`; returns a `FinalRiskIntelligence` with a fresh `prediction_id` |
| GET | `/risk/example` | Run the pipeline on a built-in NER example, assembled through the provider layer |
| POST | `/feedback` | Submit field-observation feedback linked to a `prediction_id` (404 if unknown) |
| GET | `/feedback` | List all stored feedback records |

Full schema reference: `docs/data_contract.md`.

## Browser URLs to test

- `http://127.0.0.1:8000/docs` — interactive Swagger UI (try every endpoint from the browser)
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/risk/example`

## Example: POST /risk/analyze payload

```json
{
  "location": { "latitude": 25.57, "longitude": 94.10, "district": "Kohima", "state": "Nagaland" },
  "environmental": { "rainfall_24h": 90, "rainfall_72h": 160, "forecast_rainfall": 40, "soil_moisture": 55 },
  "terrain": { "slope": 25, "elevation": 1200, "geology": "moderately_weathered", "historical_landslide_density": 2 },
  "satellite": { "satellite_available": false },
  "infrastructure": { "roads": 8, "bridges": 1, "settlements": 3, "hospitals": 1, "schools": 1, "estimated_population": 2200 }
}
```

PowerShell:
```powershell
$body = @{
  location = @{ latitude = 25.57; longitude = 94.10; district = "Kohima"; state = "Nagaland" }
  environmental = @{ rainfall_24h = 90; rainfall_72h = 160; forecast_rainfall = 40; soil_moisture = 55 }
  terrain = @{ slope = 25; elevation = 1200; geology = "moderately_weathered"; historical_landslide_density = 2 }
  satellite = @{ satellite_available = $false }
  infrastructure = @{ roads = 8; bridges = 1; settlements = 3; hospitals = 1; schools = 1; estimated_population = 2200 }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri http://127.0.0.1:8000/risk/analyze -Method POST -Body $body -ContentType "application/json"
```

curl:
```bash
curl -X POST http://127.0.0.1:8000/risk/analyze \
  -H "Content-Type: application/json" \
  -d '{"location":{"latitude":25.57,"longitude":94.10,"district":"Kohima","state":"Nagaland"},"environmental":{"rainfall_24h":90,"rainfall_72h":160,"forecast_rainfall":40,"soil_moisture":55},"terrain":{"slope":25,"elevation":1200,"geology":"moderately_weathered","historical_landslide_density":2},"satellite":{"satellite_available":false},"infrastructure":{"roads":8,"bridges":1,"settlements":3,"hospitals":1,"schools":1,"estimated_population":2200}}'
```

## Example expected response (abbreviated — satellite unavailable, so uncertainty is visibly higher)

```json
{
  "prediction_id": "59c12f4c-f86e-4399-b722-107540923375",
  "location": { "latitude": 25.57, "longitude": 94.1, "district": "Kohima", "state": "Nagaland" },
  "risk": {
    "risk_score": 32.95,
    "risk_level": "MODERATE",
    "uncertainty": 0.235,
    "confidence": 0.765,
    "top_factors": ["high soil moisture/saturation", "elevated 24-hour rainfall", "steep terrain slope"],
    "factor_contributions": [
      { "factor": "soil_moisture", "label": "high soil moisture/saturation", "available": true, "normalized_value": 0.55, "weight": 0.15, "contribution": 0.0825 },
      { "factor": "satellite_surface_change", "label": "detected surface change from satellite imagery", "available": false, "normalized_value": null, "weight": 0.10, "contribution": 0.0 }
    ],
    "explanation": "Risk is MODERATE primarily because of high soil moisture/saturation, elevated 24-hour rainfall, and steep terrain slope."
  },
  "impact": { "affected_roads": 2, "affected_bridges": 1, "affected_settlements": 1, "estimated_population": 330, "impact_level": "LOW" },
  "decision": {
    "recommended_actions": [
      "Increase monitoring frequency in the affected area.",
      "Verify environmental sensor readings with a manual/field check.",
      "Share advisory with local disaster management authority for awareness.",
      "Data completeness is limited for this analysis — treat this output as an initial screening result and prioritize ground-truth verification before acting on it."
    ],
    "urgency": "ELEVATED",
    "rationale": "..."
  },
  "data_quality": {
    "completeness_score": 0.5714,
    "missing_fields": ["satellite.surface_change_score"],
    "satellite_available": false,
    "status": "DEGRADED"
  },
  "feedback_status": "PENDING"
}
```

Note the uncertainty note automatically appended to `recommended_actions`
once uncertainty crosses a threshold — this is real behavior, not
hand-written for this example.

### Example: submitting feedback for that prediction (PowerShell)

```powershell
$feedback = @{
  prediction_id = "59c12f4c-f86e-4399-b722-107540923375"   # from the response above
  observed_condition = "Field team confirmed minor soil saturation, no active movement."
  landslide_occurred = $false
  notes = "Recommend re-check after next rainfall event."
} | ConvertTo-Json

Invoke-RestMethod -Uri http://127.0.0.1:8000/feedback -Method POST -Body $feedback -ContentType "application/json"
```

Feeding an unknown/made-up `prediction_id` here returns HTTP 404.

## How your five teammates plug their modules into this architecture

Every external module has a matching abstract interface in
`backend/adapters/base.py`, a mock implementation in
`backend/adapters/mock_providers.py`, and an active binding in
`backend/providers.py`. To integrate a real module, a teammate:

1. **Weather/hydrology teammate** — writes a class implementing
   `WeatherProvider.get_environmental_data(location) -> EnvironmentalData`
   (e.g. calling a weather API/model), then in `backend/providers.py`
   changes `weather_provider = MockWeatherProvider()` to
   `weather_provider = RealWeatherProvider()`.

2. **GIS/terrain teammate** — implements `TerrainProvider` (terrain: slope,
   elevation, geology, historical density) and `InfrastructureProvider`
   (roads/bridges/settlements/population near a location), and rebinds both
   in `providers.py`. Once they also have a real risk-zone polygon, they
   additionally replace the placeholder exposure-fraction logic in
   `backend/services/impact_service.py` (marked with a `TODO`) with a real
   spatial (polygon/buffer) intersection, by implementing `ImpactProvider`
   and rebinding `impact_provider` in `providers.py`.

3. **Satellite teammate** — implements `SatelliteProvider.get_satellite_data`.
   If a pass wasn't available for a location, they just set
   `satellite_available=False` on the returned `SatelliteData` — the
   uncertainty model already reacts to that automatically (uncertainty goes
   up, confidence goes down, and the missing factor is clearly flagged in
   `factor_contributions` and `data_quality.missing_fields`).

4. **Risk-model teammate (the real ML/statistical model)** — implements
   `RiskModelProvider.calculate_risk(environmental, terrain, satellite) ->
   RiskResult`, returning the same fields the baseline does (`risk_score`,
   `risk_level`, `uncertainty`, `confidence`, `top_factors`,
   `factor_contributions`, `explanation`), then rebinds
   `risk_model_provider` in `providers.py` to their class instead of
   `BaselineRiskModelProvider`. Nothing in `pipeline.py` or `main.py`
   changes.

5. **Frontend teammate** — consumes `FinalRiskIntelligence` JSON from
   `POST /risk/analyze` / `GET /risk/example` (including `prediction_id`,
   `factor_contributions`, and `data_quality.status`), and posts to
   `/feedback` with that `prediction_id` from a field-observation form.
   Swagger UI at `/docs` is a live, always-current reference while
   building against this API.

In every case: as long as a teammate's module returns something that
validates against the matching Pydantic model in `schemas.py`, it can
replace the corresponding mock/service by changing a single binding in
`backend/providers.py` — nothing in the central pipeline or API needs to
be rewritten.
