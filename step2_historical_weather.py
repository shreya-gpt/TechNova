"""
STEP 2 — Get Historical Weather
Tool: Open-Meteo Historical (Archive) API

Pulls past weather (reanalysis-based) for training data.
Docs: https://open-meteo.com/en/docs/historical-weather-api
"""

import requests
import pandas as pd

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def get_historical_weather(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    """
    start_date / end_date format: 'YYYY-MM-DD'

    Returns hourly DataFrame with precipitation, temperature,
    humidity, pressure, soil temperature/moisture (where available).
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join([
            "precipitation",
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "soil_temperature_0_to_7cm",
            "soil_moisture_0_to_7cm",
        ]),
        "timezone": "auto",
    }

    response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"time": "timestamp"})
    df["lat"] = lat
    df["lon"] = lon
    return df


def label_landslide_days(df: pd.DataFrame, landslide_dates: list) -> pd.DataFrame:
    """
    Attach a binary 'landslide' label column by joining against a list
    of known landslide event dates (strings 'YYYY-MM-DD') for this location.
    You'll typically get this list from a disaster-records dataset
    (e.g. state disaster management authority, NASA COOLR/GLC).
    """
    landslide_dates = set(pd.to_datetime(landslide_dates).date)
    df["date"] = df["timestamp"].dt.date
    df["landslide"] = df["date"].isin(landslide_dates).astype(int)
    return df.drop(columns=["date"])


if __name__ == "__main__":
    LAT, LON = 27.33, 88.61

    hist_df = get_historical_weather(LAT, LON, "2026-06-01", "2026-06-30")

    # Example: dates you already know had reported landslides in this area
    known_landslide_dates = ["2026-06-02", "2026-06-03"]
    hist_df = label_landslide_days(hist_df, known_landslide_dates)

    print(hist_df.tail())
    hist_df.to_csv("historical_weather.csv", index=False)
    print("\nSaved -> historical_weather.csv")
