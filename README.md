# NER Landslide Risk Intelligence — Backend / Integration Layer

Central backend for the SIH 2026 "AI-powered Landslide Risk Intelligence and
Early Warning Platform" for the North Eastern Region (NER) of India.

This is the **integration lead's part** of a 6-person team: it does not
build the weather, GIS, satellite, risk-model, or frontend modules — it
provides the pipeline and API that combines their outputs into one
coherent flow:

```
Environmental + Terrain + Satellite + Infrastructure data
        -> data quality assessment
        -> risk score (weighted baseline model)
        -> uncertainty / confidence
        -> explanation (top contributing factors)
        -> impact assessment (affected infrastructure/population)
        -> recommended actions
        -> FinalRiskIntelligence (+ feedback loop for future calibration)
```

## Status of the risk model

**The risk engine (`backend/services/risk_service.py`) is a transparent,
weighted-factor PROTOTYPE — not a scientifically validated landslide
model.** It exists so the full pipeline is runnable and demoable today.
All weights and thresholds are documented and isolated in
`backend/config.py` so the real model can be swapped in later.

## Architecture

```
backend/
├── main.py              FastAPI app + routes
├── schemas.py            Pydantic data contract (shared by all modules)
├── pipeline.py            run_risk_pipeline() — orchestrates the services
├── config.py              Weights, thresholds, normalization ranges (documented placeholders)
├── mock_data.py           Realistic NER example (used by /risk/example and tests)
├── data/
│   └── feedback.json      Local feedback/calibration-dataset storage
└── services/
    ├── risk_service.py     Risk score, uncertainty, explainability
    ├── impact_service.py    Rule-based infrastructure/population exposure
    ├── decision_service.py  Rule-based advisory recommendations
    └── feedback_service.py  Feedback storage (Prediction -> Observation -> Feedback -> Dataset)

tests/
├── test_pipeline.py       Pipeline + API endpoint tests
├── test_risk_service.py    Risk engine unit tests
└── test_feedback.py        Feedback storage unit tests

docs/
└── data_contract.md        Full schema reference for teammates

conftest.py                 Lets tests import backend/ modules directly
requirements.txt
```

Every service function takes and returns plain Pydantic objects from
`schemas.py`. To plug in a teammate's real module later, you only need to
replace the *inside* of one service file (e.g. `risk_service.calculate_risk`)
— `pipeline.py` and `main.py` never need to change.

## Install (Windows 11 + VS Code, PowerShell)

```powershell
# From the project root (ner-landslide-backend/)
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run this once as your user
(not admin), then retry:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Run the API

```powershell
cd backend
uvicorn main:app --reload
```

The API will be live at `http://127.0.0.1:8000`. Interactive docs (Swagger
UI) are automatically available at `http://127.0.0.1:8000/docs`.

## Run the tests

From the project root (not inside `backend/`):

```powershell
pytest tests/ -v
```

All 21 tests should pass. `conftest.py` at the project root makes the
`backend/` modules importable for the test files.

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/risk/analyze` | Run the full pipeline on a submitted `RiskAnalysisRequest` |
| GET | `/risk/example` | Run the pipeline on the built-in NER mock example |
| POST | `/feedback` | Submit field-observation feedback |
| GET | `/feedback` | List all stored feedback records |

Full schema reference: `docs/data_contract.md`.

## Example request

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/risk/example -Method GET | ConvertTo-Json -Depth 10
```

or with curl:

```bash
curl http://127.0.0.1:8000/risk/example
```

## Example response (abbreviated)

```json
{
  "location": {
    "latitude": 25.284,
    "longitude": 91.7273,
    "district": "East Khasi Hills",
    "state": "Meghalaya"
  },
  "risk": {
    "risk_score": 76.42,
    "risk_level": "CRITICAL",
    "uncertainty": 0.05,
    "confidence": 0.95,
    "top_factors": [
      "high soil moisture/saturation",
      "elevated 24-hour rainfall",
      "high cumulative 72-hour rainfall"
    ],
    "explanation": "Risk is CRITICAL primarily because of high soil moisture/saturation, elevated 24-hour rainfall, and high cumulative 72-hour rainfall."
  },
  "impact": {
    "affected_roads": 9,
    "affected_bridges": 3,
    "affected_settlements": 5,
    "estimated_population": 3150,
    "impact_level": "SEVERE"
  },
  "decision": {
    "recommended_actions": [
      "Conduct immediate field verification of slope stability.",
      "Activate evacuation preparedness for at-risk settlements.",
      "Assess and consider precautionary traffic restrictions on nearby roads.",
      "Initiate emergency coordination with district/state disaster response teams."
    ],
    "urgency": "IMMEDIATE",
    "rationale": "Risk level is CRITICAL (score 76.42/100, confidence 0.95). ..."
  },
  "data_quality": {
    "completeness_score": 1.0,
    "missing_fields": [],
    "satellite_available": true
  },
  "feedback_status": "PENDING"
}
```

### Example: analyzing a custom location (PowerShell)

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

### Example: submitting feedback (PowerShell)

```powershell
$feedback = @{
  prediction_id = "demo-001"
  location = @{ latitude = 25.284; longitude = 91.7273; district = "East Khasi Hills"; state = "Meghalaya" }
  predicted_risk_level = "CRITICAL"
  observed_condition = "Field team confirmed active surface cracking and minor debris flow."
  landslide_occurred = $true
  notes = "Evacuation of 2 households completed as precaution."
} | ConvertTo-Json

Invoke-RestMethod -Uri http://127.0.0.1:8000/feedback -Method POST -Body $feedback -ContentType "application/json"
```

## How teammates plug their modules in

The whole point of this layer is that nobody has to rewrite it once real
modules exist. Concretely:

- **Weather/hydrology teammate** — their module should end up producing an
  `EnvironmentalData` object (see `docs/data_contract.md`). Wherever they
  currently print/return rainfall numbers, wrap them into that model
  instead. That object slots directly into a `RiskAnalysisRequest`.

- **GIS teammate (terrain + infrastructure)** — same pattern for
  `TerrainData` and `Infrastructure`. Once they have a real risk-zone
  polygon and asset layer, `services/impact_service.py` is the *only* file
  that needs to change — replace the placeholder exposure-fraction logic
  with a real spatial intersection (the `TODO` comment marks exactly where).

- **Satellite teammate** — produces `SatelliteData`. If a pass wasn't
  available, they just set `satellite_available=False`; the uncertainty
  model already reacts to that automatically.

- **Risk-model teammate (the real ML/statistical model)** — replace the
  body of `services/risk_service.calculate_risk()` with a call into their
  model, but keep returning a `RiskResult` with the same fields
  (`risk_score`, `risk_level`, `uncertainty`, `confidence`, `top_factors`,
  `explanation`). Nothing in `pipeline.py` or `main.py` needs to change.

- **Frontend teammate** — consumes `FinalRiskIntelligence` JSON from
  `POST /risk/analyze` / `GET /risk/example`, and can post to `/feedback`
  from a field-observation form. Swagger UI at `/docs` is a live reference
  while building against this API.

In all cases: as long as a teammate's module returns something that
validates against the matching Pydantic model in `schemas.py`, it can
replace the corresponding mock/service without touching the rest of the
system.
