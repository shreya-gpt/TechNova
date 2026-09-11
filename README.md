# Weather & Environmental Data Pipeline — SIH Landslide Risk Project

Implements the full workflow: **Weather APIs → Rainfall/Forecast →
Soil Data → Clean → Feature Engineer → Store → Serve to AI/Risk Engine.**

## File map (matches your workflow steps)

| File | Step | What it does |
|---|---|---|
| `step1_weather_api.py` | 1 | Open-Meteo current + forecast weather, rainfall summary |
| `step2_historical_weather.py` | 2 | Open-Meteo Historical (Archive) API for training data |
| `step3_rainfall_features.py` | 3, 9 | Rolling rainfall windows (1h–72h) + intensity flags |
| `step4_soil_data.py` | 4 | SoilGrids soil properties (REST, with COG fallback) |
| `step5_soil_moisture.py` | 5 | Soil moisture via Open-Meteo ERA5-Land (SMAP stub for later) |
| `step6_storage.py` | 6 | CSV storage now, PostgreSQL/PostGIS helper for later |
| `step7_data_cleaning.py` | 7 | Missing values, duplicates, invalid coords, range checks |
| `step8_synchronize.py` | 8 | Resample multi-source data onto a common hourly grid |
| `step9_build_dataset.py` | 9–11 | Forecast trend + final wide feature table |
| `step10_api_server.py` | 12 | FastAPI endpoint the AI/Risk Engine calls |
| `main_pipeline.py` | all | Orchestrates every step for a list of locations |

## Setup

```bash
pip install -r requirements.txt
```

## Run the full pipeline (CSV output)

```bash
python main_pipeline.py
```

Produces `environmental_dataset.csv` — one row per location with all
rainfall windows, forecast trend, soil moisture, and soil properties.
This is the file/table you hand to the AI team.

## Run the API for the AI team to call live

```bash
uvicorn step10_api_server:app --reload --port 8000
```

Then:

```bash
curl "http://localhost:8000/environmental-data?lat=27.33&lon=88.61&location_id=gangtok_A"
```

Open `http://localhost:8000/docs` for interactive Swagger docs.

## Suggested build order (matches your mini-projects)

1. `step1_weather_api.py` — get it printing rainfall numbers for one location.
2. `step2_historical_weather.py` — pull a month of history, eyeball it in Jupyter.
3. `step3_rainfall_features.py` — verify rolling windows against hand-calculated numbers.
4. `step7_data_cleaning.py` + `step8_synchronize.py` — before adding more sources.
5. `step4_soil_data.py` + `step5_soil_moisture.py` — add soil once rainfall pipeline is solid.
6. `step9_build_dataset.py` → `main_pipeline.py` → `step10_api_server.py` — wire it all together.
7. Swap `step6_storage.save_to_csv` for `save_to_postgres` once your DB is up.

## Notes

- No API keys needed for Open-Meteo (forecast + historical + soil moisture).
- SoilGrids REST can be flaky — the fallback reads GeoTIFFs directly via `rasterio`.
- NASA SMAP and GPM/IMERG both require a free NASA Earthdata login
  (`earthaccess` library) — treat these as Phase 2, per your own priority table.
- Missing-value strategy is deliberately NOT "fill with 0" for rainfall —
  see the comments in `step7_data_cleaning.py` for why.
