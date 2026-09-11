"""
STEP 1 — Collect Weather Data
Tool: Open-Meteo Forecast API (free, no API key needed)

Fetches current + hourly forecast weather for a lat/lon:
rainfall, temperature, humidity, wind speed, pressure, rainfall forecast.

Docs: https://open-meteo.com/en/docs
"""

import requests
import pandas as pd

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_data(lat: float, lon: float, past_days: int = 3, forecast_days: int = 3) -> pd.DataFrame:
    """
    Fetch hourly weather data (past_days + forecast_days) for a location.

    Returns a DataFrame indexed by timestamp with columns:
    precipitation, temperature_2m, relative_humidity_2m,
    surface_pressure, wind_speed_10m
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "precipitation",
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "wind_speed_10m",
        ]),
        "past_days": past_days,      # lets us compute rolling rainfall windows
        "forecast_days": forecast_days,
        "timezone": "auto",
    }

    response = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    hourly = data["hourly"]
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"time": "timestamp"})
    df["lat"] = lat
    df["lon"] = lon
    return df


def get_rainfall_summary(df: pd.DataFrame, now: pd.Timestamp = None) -> dict:
    """
    Given the hourly dataframe from get_weather_data(), compute the
    classic rainfall accumulation snapshot for a single 'now' timestamp:
    rain_1h, rain_6h, rain_24h, rain_72h + next-24h forecast.
    """
    if now is None:
        now = pd.Timestamp.now(tz=df["timestamp"].dt.tz) if df["timestamp"].dt.tz else pd.Timestamp.now()
        # snap to nearest available hour
        now = df["timestamp"].iloc[(df["timestamp"] - now).abs().argsort()[:1]].values[0]
        now = pd.Timestamp(now)

    past = df[df["timestamp"] <= now]
    future = df[df["timestamp"] > now]

    def sum_last(hours):
        window_start = now - pd.Timedelta(hours=hours)
        return float(past[past["timestamp"] > window_start]["precipitation"].sum())

    def sum_next(hours):
        window_end = now + pd.Timedelta(hours=hours)
        return float(future[future["timestamp"] <= window_end]["precipitation"].sum())

    return {
        "timestamp": now,
        "rain_1h": sum_last(1),
        "rain_6h": sum_last(6),
        "rain_24h": sum_last(24),
        "rain_72h": sum_last(72),
        "forecast_24h": sum_next(24),
    }


if __name__ == "__main__":
    # Example: Gangtok, Sikkim (landslide-prone region)
    LAT, LON = 27.33, 88.61

    weather_df = get_weather_data(LAT, LON)
    print(weather_df.tail())

    summary = get_rainfall_summary(weather_df)
    print("\nRainfall summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    weather_df.to_csv("weather.csv", index=False)
    print("\nSaved -> weather.csv")
