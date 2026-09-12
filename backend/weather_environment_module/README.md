# Weather & Environmental Data Module

Backend module for the **AI-powered Landslide Risk Intelligence and Early Warning Platform** for India's North Eastern Region (NER) — built for a Smart India Hackathon (SIH) team.

This module owns one job: **collect, validate, clean, engineer, and serve environmental data** (rainfall, soil moisture, temperature, humidity, forecasts, antecedent rainfall, anomalies) to the platform's downstream AI / Risk Engine.

> **It does NOT predict landslides.** It reports environmental *evidence* — raw observations, derived features, rule-based indicators, and a data-quality/confidence score — for the Risk Engine to fuse with terrain, geology, satellite imagery, historical landslide records and infrastructure exposure.

---

## 1. Project overview

The overall platform pipeline is:

```
Predict → Explain → Quantify Uncertainty → Assess Impact → Recommend Action → Learn
```

This module feeds the **first stage** with a clean, quality-scored environmental feature vector for any (latitude, longitude, timestamp) in the NER: Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim, Tripura.

Design priorities: modularity, graceful failure, data provenance, uncertainty, and being easy to demo without internet access.

---

## 2. Architecture

```
                 ┌───────────────────────┐
                 │   FastAPI (app/api)   │
                 └──────────┬────────────┘
                             │
                 ┌──────────▼────────────┐
                 │ EnvironmentalService   │  orchestrates the whole request
                 └───┬───────────────┬────┘
                     │               │
          ┌──────────▼───┐   ┌───────▼────────┐
          │ WeatherService│   │ QualityService │
          │ (fallback +   │   │ (score, flags, │
          │  caching)     │   │  confidence)   │
          └───┬───────┬───┘   └────────────────┘
              │       │
     ┌────────▼─┐  ┌──▼───────────┐        ┌──────────────────┐
     │OpenMeteo │  │ IMD (stub)   │  ...    │  Demo Provider    │
     │Provider  │  │ Provider     │         │  (offline synth.) │
     └──────────┘  └──────────────┘         └──────────────────┘
              (all implement WeatherDataProvider)

                 ┌───────────────────────┐
                 │ processing/*          │  validation, cleaning,
                 │                       │  aggregation, features
                 └───────────────────────┘

                 ┌───────────────────────┐
                 │ database/ (SQLite)    │  audit trail of served
                 │                       │  observations
                 └───────────────────────┘
```

Every layer only depends on the abstraction below it (`WeatherDataProvider`, `EnvironmentalFeatures`/`EnvironmentalIndicators` schemas), so:

- a provider can be swapped or added without touching processing/API code,
- the processing/feature code can be unit-tested with plain Python lists of numbers, no network needed,
- the Risk Engine only ever needs to understand one JSON contract (`RiskFeatureResponse`), never a specific provider's format.

---

## 3. Data flow

1. **Request** — Risk Engine (or a human, via `/docs`) calls `GET /environment/risk-features?latitude=...&longitude=...`.
2. **Fetch** — `WeatherService` asks providers, in order, for current/historical/forecast weather and soil moisture, applying an in-memory TTL cache first.
3. **Fallback** — if a provider errors or is unconfigured, the next one in the chain is tried; if all fail (or `DEMO_MODE=true`), the built-in `DemoProvider` supplies clearly-flagged synthetic data. The **actual source used is always reported**, never silently swapped without a flag.
4. **Clean** — historical series are deduplicated and scanned for statistical spikes (`processing/cleaning.py`).
5. **Feature engineering** — rainfall accumulations (1h→7d), rolling intensity, Antecedent Precipitation Index, rainfall anomaly/percentile (when enough history exists), forecast accumulations, and rule-based indicator flags (`processing/features.py`).
6. **Quality scoring** — missing data, staleness, spikes, duplicates, gaps, fallback usage, and out-of-region coordinates are combined into a `data_quality.score` (0–1) plus a list of typed `quality_flags`, and an `environmental_confidence` (`services/quality_service.py`).
7. **Persist** — the response is saved to SQLite for auditability (`database/repository.py`).
8. **Respond** — the `RiskFeatureResponse` JSON contract is returned.

---

## 4. Data sources

| Purpose | Source used | Notes |
|---|---|---|
| Current weather, forecast, historical rainfall/temp/humidity | **Open-Meteo** (`api.open-meteo.com`, `archive-api.open-meteo.com`) | Free, no API key, used as the primary real provider. |
| Soil moisture (proxy) | **NASA POWER** (`power.larc.nasa.gov`) | Free, no key, coarse-resolution `GWETROOT` root-zone wetness used as a realistic, accessible proxy. |
| India-specific rainfall (authoritative) | **IMD** — adapter present, **not wired to a live endpoint** | IMD does not publish a simple public JSON API for this use case; see `app/providers/imd.py` for exactly what real institutional access would require. The adapter raises a clear `ProviderUnavailableError` so the fallback chain takes over automatically — it never invents data. |
| Offline demo | **Built-in synthetic generator** (`app/providers/demo.py`) | Deterministic per-coordinate, tells a believable "light → increasing → persistent → heavy" rainfall story for live SIH demos. Always tagged `DEMO_DATA` in the quality flags. |

Sources considered but not wired up in this prototype (left as documented extension points): MOSDAC/ISRO, GPM, ERA5-Land via Copernicus CDS, SMAP via NASA Earthdata. Open-Meteo's historical endpoint is itself ERA5/ERA5-Land-derived, so this prototype already gets ERA5-quality historical rainfall without needing separate Copernicus credentials.

---

## 5. Feature descriptions

All returned inside `environmental_features`:

| Field | Meaning |
|---|---|
| `rainfall_{1h,3h,6h,12h,24h,48h,72h,7d}_mm` | Rolling rainfall accumulation ending at the request timestamp. |
| `rainfall_intensity_mm_per_hr` | Average intensity over the last 3h. |
| `rolling_rainfall_intensity_mm_per_hr` | Average intensity over the last 6h. |
| `rainfall_acceleration_mm_per_hr2` | Short-window (3h) intensity minus long-window (12h) intensity — positive means rain is intensifying. |
| `antecedent_precipitation_index` | Decay-weighted sum of daily rainfall over the last 15 days (configurable `API_DECAY_FACTOR`, `API_LOOKBACK_DAYS`) — a classic soil-wetness proxy. |
| `rainfall_anomaly_pct` / `rainfall_percentile` | How today's 24h rainfall compares to the available historical distribution. `None` when fewer than 5 historical daily totals exist (flagged via `INSUFFICIENT_HISTORY_FOR_ANOMALY`). |
| `forecast_rainfall_{3h,6h,12h,24h,48h}_mm` | Forward-looking rainfall accumulation from the forecast provider. |
| `soil_moisture_m3m3`, `temperature_c`, `relative_humidity_pct` | Latest available environmental readings. |

`environmental_indicators` (rule-based, thresholds in `app/config.py`, **prototype defaults — calibrate locally**):

`heavy_rainfall_flag`, `extreme_accumulation_flag`, `persistent_rainfall_flag`, `high_soil_moisture_flag`, `forecast_heavy_rainfall_flag`, `antecedent_wetness_level` (`low`/`moderate`/`high`/`very_high`/`unknown`), plus free-text `notes`.

---

## 6. Installation

Requires Python 3.11+.

```bash
cd weather_environment_module
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # DEMO_MODE=true out of the box
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive Swagger UI.

---

## 7. Environment variables

See `.env.example` for the full, commented list. Nothing is required to run in demo mode. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `true` | If true, always serves synthetic (clearly flagged) data — no internet/credentials needed. |
| `IMD_API_KEY` | *(empty)* | Only needed if your team wires up real institutional IMD access in `app/providers/imd.py`. |
| `NASA_EARTHDATA_TOKEN` | *(empty)* | Only needed if you extend `soil_moisture.py` to use real SMAP data. |
| `DATABASE_URL` | `sqlite:///./data/environmental_data.db` | Swap for a PostgreSQL URL later; the repository layer is already isolated for that migration. |
| `API_DECAY_FACTOR`, `HEAVY_RAINFALL_MM_24H`, etc. | see `app/config.py` | Prototype thresholds — recalibrate against local IMD/GSI data before any real use. |

---

## 8. Demo mode

With `DEMO_MODE=true` (the default), **no internet connection or API key is needed at all**. The built-in `DemoProvider` generates a deterministic, per-coordinate synthetic rainfall series shaped like a real pre-landslide-season narrative:

```
low rainfall → increasing rainfall → persistent rainfall → high accumulation → elevated environmental concern
```

Every demo response is tagged with the `DEMO_DATA` quality flag and a `source.provider = "demo"` / `is_fallback = true`, so nobody downstream can mistake it for a live observation.

Run `python scripts/demo.py` to print full JSON responses for four NER state capitals without starting the web server.

---

## 9. API documentation

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness/readiness probe. |
| GET | `/weather/current` | Latest observation for a coordinate. |
| GET | `/weather/forecast` | Hourly forecast (`hours_ahead`, default 48). |
| GET | `/weather/historical` | Hourly history between `start` and `end` (ISO8601). |
| GET | `/environment/features` | Alias of `/environment/risk-features`. |
| **GET** | **`/environment/risk-features`** | **Primary contract endpoint** — full environmental feature vector, indicators, quality, sources. |
| POST | `/environment/batch` | Batch version of the above; accepts up to `BATCH_MAX_ITEMS` (default 50) coordinate/timestamp combinations, processed concurrently. |

Full interactive docs at `/docs` (Swagger) and `/redoc` once the server is running.

### Example request

```
GET /environment/risk-features?latitude=27.3389&longitude=88.6065
```

### Example response (abridged)

```json
{
  "location": { "latitude": 27.3389, "longitude": 88.6065 },
  "timestamp": "2026-09-12T10:00:00Z",
  "environmental_features": {
    "rainfall_24h_mm": 86.4,
    "rainfall_72h_mm": 210.7,
    "rainfall_intensity_mm_per_hr": 4.1,
    "antecedent_precipitation_index": 62.3,
    "rainfall_anomaly_pct": 38.5,
    "forecast_rainfall_24h_mm": 55.2,
    "soil_moisture_m3m3": 0.41,
    "temperature_c": 21.3,
    "relative_humidity_pct": 91.0
  },
  "environmental_indicators": {
    "heavy_rainfall_flag": false,
    "extreme_accumulation_flag": false,
    "persistent_rainfall_flag": true,
    "high_soil_moisture_flag": true,
    "forecast_heavy_rainfall_flag": false,
    "antecedent_wetness_level": "high",
    "notes": ["Rainfall has persisted at or above threshold intensity for ~14h."]
  },
  "data_quality": {
    "score": 0.82,
    "flags": ["FALLBACK_SOURCE_USED", "DEMO_DATA"],
    "data_age_minutes": 0.0,
    "environmental_confidence": 0.61
  },
  "sources": [
    { "provider": "demo", "reliability": 0.3, "is_fallback": true, "fetched_at": "2026-09-12T10:00:00Z" }
  ],
  "disclaimer": "This response contains environmental observations/features only. It is NOT a landslide prediction or probability. ..."
}
```

### Batch example

```
POST /environment/batch
{
  "items": [
    { "latitude": 27.3389, "longitude": 88.6065 },
    { "latitude": 25.5788, "longitude": 91.8933 }
  ]
}
```

Returns `{"results": [...], "errors": [...]}` — a partial failure in one item never blocks the others.

---

## 10. Testing

```bash
pytest -v
```

Tests cover coordinate validation, rainfall aggregation, rolling rainfall, the Antecedent Precipitation Index, rainfall anomaly/percentile, missing/invalid data handling, the quality-score engine, staleness detection, provider failure + fallback (mocked with `respx`, no real network calls), and every API endpoint including the batch endpoint. All tests run fully offline.

> **Note on this build:** the sandbox used to generate this project had no outbound network access, so dependencies (`fastapi`, `pydantic`, etc.) could not be installed and `pytest` could not be executed in that environment. Every file was syntax-checked (`python -m py_compile`) and manually traced for correctness, but please run `pip install -r requirements.txt && pytest -v` yourself as the first step after unzipping — that's the real validation pass.

---

## 11. Docker usage

```bash
docker build -t weather-environment-module .
docker run -p 8000:8000 weather-environment-module
```

or with Compose (also mounts `./data` so the SQLite file persists across restarts):

```bash
docker-compose up --build
```

The image defaults to `DEMO_MODE=true`, so it works immediately with zero configuration.

---

## 12. Integration with the AI / Risk Engine

The Risk Engine should call `GET /environment/risk-features` (or `POST /environment/batch` for many points at once) and consume exactly this contract — it never needs to know which weather provider was used underneath:

```
location                 -> { latitude, longitude }
timestamp                -> ISO8601 UTC
environmental_features   -> numeric feature vector (rainfall, API, anomaly, forecast, soil/temp/humidity)
environmental_indicators -> rule-based boolean flags + antecedent_wetness_level (prototype thresholds)
data_quality              -> { score, flags[], data_age_minutes, environmental_confidence }
sources                   -> [{ provider, reliability, is_fallback, fetched_at }]
```

This environmental vector is designed to be **one input tensor/row** the Risk Engine fuses with:

- **Terrain/geology** (slope, aspect, soil type, lithology),
- **Satellite imagery** (NDVI, land-cover change, recent slope-failure detection),
- **Historical landslide records** (base rate, recency, proximity),
- **Infrastructure/population exposure** (roads, bridges, settlements).

`environmental_confidence` is intended as a per-feature weighting signal in that fusion step — e.g. down-weighting this module's contribution when it had to fall back to demo/cached data — and must never be treated as, or confused with, the final landslide probability.

---

## 13. Limitations

- IMD integration is a documented stub, not a live connection (see §4).
- The NER boundary check is an **approximate rectangular bounding box**, not an authoritative administrative boundary; it's structured so a real GeoJSON polygon can drop in later (`processing/validation.py::is_within_ner_bbox`).
- Rainfall-anomaly/percentile requires enough historical daily totals (≥5); with sparse history it correctly returns `None` rather than guessing.
- All indicator thresholds are prototype defaults and require local calibration against real IMD/GSI landslide advisories before any operational use.
- The in-memory TTL cache is per-process and resets on restart; fine for a hackathon demo, not for multi-instance production.
- SQLite is intentionally simple for the prototype; see §14 for the PostGIS migration path.

---

## 14. Future improvements

- Wire a real IMD/AWS-ARG or gridded-rainfall integration once institutional access is available.
- Add SMAP soil moisture via NASA Earthdata for higher-resolution soil wetness.
- Replace the NER bounding box with real state boundary GeoJSON/shapefiles.
- Replace the in-memory `TTLCache` with Redis (`services/cache.py` already documents the swap — implement `get`/`set` against a `redis.Redis` client).
- Migrate `DATABASE_URL` to PostgreSQL + PostGIS for spatial queries once the platform needs multi-instance deployment.
- Add authentication/rate-limiting in front of the API once this moves beyond a hackathon prototype.

---

## 15. SIH demo instructions

1. `pip install -r requirements.txt`
2. `cp .env.example .env` (defaults already have `DEMO_MODE=true`)
3. `uvicorn app.main:app --reload`
4. Open `/docs`, call `GET /environment/risk-features` for a few NER coordinates (Gangtok `27.3389, 88.6065`, Shillong `25.5788, 91.8933`, Aizawl `23.7271, 92.7176`), and show the judges:
   - the rainfall numbers changing across the demo's "light → persistent → heavy" story arc,
   - the `data_quality` block proving the system knows when it's degraded,
   - the disclaimer proving the team understands this is *evidence*, not a landslide prediction.
5. Alternatively, run `python scripts/demo.py` for a no-server, terminal-only walkthrough.
6. Mention to the Risk Engine sub-team: they only need `GET /environment/risk-features`, and can ignore everything else in this repo.

---

## What this module deliberately does NOT do

- It does not compute a landslide probability.
- It does not claim any specific rainfall value "causes" or "guarantees" a landslide.
- It does not fabricate data when a source is unavailable — it flags `MISSING_*` / `FALLBACK_SOURCE_USED` / `DEMO_DATA` instead.
