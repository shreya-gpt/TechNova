"""
STEP 12 — Give Data to the AI Team
Tool: FastAPI

Exposes an endpoint the AI/Risk Engine calls to get fresh, clean,
feature-engineered environmental data for a location:

    GET /environmental-data?lat=27.33&lon=88.61&location_id=gangtok_A

Run with:
    uvicorn step10_api_server:app --reload --port 8000

Then test at: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd

from step1_weather_api import get_weather_data, get_rainfall_summary
from step3_rainfall_features import add_rainfall_features, add_rainfall_intensity_flags
from step4_soil_data import get_soil_data
from step5_soil_moisture import get_recent_soil_moisture
from step7_data_cleaning import clean_pipeline
from step9_build_dataset import build_environmental_dataset

app = FastAPI(title="Weather & Environmental Data Service", version="0.1.0")


class EnvironmentalRecord(BaseModel):
    location_id: str
    lat: float
    lon: float
    timestamp: str
    rain_1h: float | None = None
    rain_6h: float | None = None
    rain_24h: float | None = None
    rain_72h: float | None = None
    forecast_24h: float | None = None
    forecast_trend: float | None = None
    soil_moisture_0_to_7cm: float | None = None
    clay: float | None = None
    sand: float | None = None
    relative_humidity_2m: float | None = None
    temperature_2m: float | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/environmental-data", response_model=EnvironmentalRecord)
def environmental_data(lat: float, lon: float, location_id: str = "unknown"):
    """
    Live pipeline call. For production, don't hit external APIs on every
    request — instead run the pipeline on a schedule (cron / Airflow)
    into Postgres, and have this endpoint just SELECT the latest row.
    This version calls the pipeline directly so it's easy to demo.
    """
    try:
        weather_df = get_weather_data(lat, lon)
        weather_df = clean_pipeline(weather_df)
        weather_df = add_rainfall_features(weather_df)
        weather_df = add_rainfall_intensity_flags(weather_df)
        forecast_summary = get_rainfall_summary(weather_df)

        soil_props = pd.DataFrame([get_soil_data(lat, lon)])
        soil_moisture_df = get_recent_soil_moisture(
            lat, lon,
            days=7
        )

        final_row = build_environmental_dataset(
            weather_df, forecast_summary, soil_moisture_df, soil_props, location_id
        )
        record = final_row.iloc[0].to_dict()

        # Add location information
        record["lat"] = lat
        record["lon"] = lon

# Convert timestamp to string
        record["timestamp"] = str(record["timestamp"])

        return record

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Pipeline failed: {e}")


# --- Example of how the AI/Risk Engine would call this from Python ---
# import requests
# resp = requests.get("http://localhost:8000/environmental-data",
#                      params={"lat": 27.33, "lon": 88.61, "location_id": "gangtok_A"})
# features = resp.json()
# risk_score = risk_model.predict(features)
