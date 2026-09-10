# Data Contract

This document describes the shared data contract defined in `backend/schemas.py`.
Every teammate's module (weather, GIS, satellite, risk-model, frontend) should
produce or consume data matching these shapes so it can be plugged into the
central pipeline without changes elsewhere.

## Input models

### Location
| field | type | notes |
|---|---|---|
| latitude | float | -90 to 90 |
| longitude | float | -180 to 180 |
| district | str | |
| state | str | |

### EnvironmentalData (weather/hydrology module)
| field | type | required | notes |
|---|---|---|---|
| rainfall_24h | float | yes | mm, last 24h |
| rainfall_72h | float | no | mm, last 72h |
| forecast_rainfall | float | no | mm, next 24h forecast |
| soil_moisture | float | no | % saturation, 0-100 |

### TerrainData (GIS module)
| field | type | required | notes |
|---|---|---|---|
| slope | float | yes | degrees, 0-90 |
| elevation | float | no | meters |
| geology | str | no | one of: `stable_rock`, `moderately_weathered`, `highly_weathered`, `weak_sedimentary_or_fractured` (unrecognized values are treated as neutral/unknown) |
| historical_landslide_density | float | no | events per sq km (placeholder scale) |

### SatelliteData (remote sensing module)
| field | type | required | notes |
|---|---|---|---|
| satellite_available | bool | yes | whether a usable pass exists |
| surface_change_score | float | no | 0-1 normalized |
| vegetation_indicator | float | no | 0-1 normalized (e.g. from NDVI) |

### Infrastructure (GIS asset inventory)
| field | type | default |
|---|---|---|
| roads, bridges, settlements, hospitals, schools | int | 0 |
| estimated_population | int | 0 |

### RiskAnalysisRequest
Combines `location`, `environmental`, `terrain`, `satellite`, `infrastructure`.
This is the body of `POST /risk/analyze`.

## Output models

### RiskResult
`risk_score` (0-100), `risk_level` (LOW/MODERATE/HIGH/CRITICAL), `uncertainty`
(0-1), `confidence` (always `1 - uncertainty`), `top_factors` (list of
human-readable strings), `explanation` (one sentence).

### ImpactResult
`affected_roads`, `affected_bridges`, `affected_settlements`,
`estimated_population`, `impact_level` (NEGLIGIBLE/LOW/MODERATE/SEVERE).

### DecisionResult
`recommended_actions` (list of advisory strings — never autonomous
commands), `urgency` (ROUTINE/ELEVATED/URGENT/IMMEDIATE), `rationale`.

### DataQuality
`completeness_score` (0-1), `missing_fields` (list of dotted field names),
`satellite_available` (bool).

### FinalRiskIntelligence
The full response of `POST /risk/analyze` and `GET /risk/example`:
`location`, `input_data` (the original request, echoed back), `risk`,
`impact`, `decision`, `timestamp`, `data_quality`, `feedback_status`.

## Feedback models

### FeedbackSubmission
`prediction_id` (optional), `location`, `predicted_risk_level`,
`observed_condition` (free text), `landslide_occurred` (bool), `notes`
(optional). Body of `POST /feedback`.

### FeedbackRecord
`FeedbackSubmission` plus `feedback_id` and `received_at`, as returned by
`POST /feedback` and listed by `GET /feedback`.

## Integration guidance for teammates

Each teammate's real module should ultimately produce an instance of the
relevant input model above (e.g. the weather module returns an
`EnvironmentalData`), or a dict that validates against it. Nothing else
in the pipeline needs to know whether that data came from a live API, a
sensor feed, or `mock_data.py`.
