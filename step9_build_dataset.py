"""
STEP 9-11 — Rainfall Forecast Features + Final Environmental Dataset

Combines everything into the single wide table the AI/Risk Engine
consumes:

  location_id, lat, lon, timestamp,
  rain_1h..rain_72h, forecast_24h, forecast_trend,
  soil_moisture, clay, sand, silt, bdod, soc, phh2o,
  humidity, temperature, wind_speed
"""

import pandas as pd


def add_forecast_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    STEP 10 — turn 'rain_24h so far' + 'forecast_24h' into a simple,
    explainable trend signal the AI model (or a rule-based fallback)
    can use directly.
    """
    df = df.copy()
    df["forecast_trend"] = df["forecast_24h"] - df["rain_24h"]
    df["rising_risk_flag"] = (df["forecast_trend"] > 0) & (df["rain_24h"] > 50)
    return df


def build_environmental_dataset(rainfall_df: pd.DataFrame,
                                 forecast_summary: dict,
                                 soil_moisture_df: pd.DataFrame,
                                 soil_props_df: pd.DataFrame,
                                 location_id: str) -> pd.DataFrame:
    """
    Assembles STEP 11's final table for one location + timestamp
    snapshot (call this per location, per scheduled run e.g. hourly).
    """
    latest = rainfall_df.iloc[[-1]].copy()
    latest["location_id"] = location_id
    latest["forecast_24h"] = forecast_summary["forecast_24h"]

    latest = add_forecast_trend(latest)

    # attach latest soil moisture reading for this location
    if not soil_moisture_df.empty:
        sm_latest = soil_moisture_df.iloc[[-1]]
        for col in ["soil_moisture_0_to_7cm", "soil_moisture_7_to_28cm"]:
            if col in sm_latest.columns:
                latest[col] = sm_latest[col].values[0]

    # attach static soil properties for this location
    if not soil_props_df.empty:
        for col in ["clay", "sand", "silt", "bdod", "soc", "phh2o"]:
            if col in soil_props_df.columns:
                latest[col] = soil_props_df[col].values[0]

    cols_order = [
        "location_id", "lat", "lon", "timestamp",
        "rain_1h", "rain_3h", "rain_6h", "rain_12h", "rain_24h", "rain_48h", "rain_72h",
        "forecast_24h", "forecast_trend", "rising_risk_flag",
        "soil_moisture_0_to_7cm", "soil_moisture_7_to_28cm",
        "clay", "sand", "silt", "bdod", "soc", "phh2o",
        "relative_humidity_2m", "temperature_2m", "wind_speed_10m",
    ]
    cols_present = [c for c in cols_order if c in latest.columns]
    return latest[cols_present].reset_index(drop=True)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from step1_weather_api import get_weather_data, get_rainfall_summary
    from step3_rainfall_features import add_rainfall_features, add_rainfall_intensity_flags
    from step4_soil_data import get_soil_data
    from step5_soil_moisture import get_soil_moisture_openmeteo
    from step7_data_cleaning import clean_pipeline

    LAT, LON, LOCATION_ID = 27.33, 88.61, "gangtok_A"

    weather_df = get_weather_data(LAT, LON)
    weather_df = clean_pipeline(weather_df)
    weather_df = add_rainfall_features(weather_df)
    weather_df = add_rainfall_intensity_flags(weather_df)
    forecast_summary = get_rainfall_summary(weather_df)

    soil_props = pd.DataFrame([get_soil_data(LAT, LON)])
    soil_moisture_df = get_soil_moisture_openmeteo(LAT, LON, "2026-09-01", "2026-09-09")

    final_dataset = build_environmental_dataset(
        weather_df, forecast_summary, soil_moisture_df, soil_props, LOCATION_ID
    )
    print(final_dataset.T)
    final_dataset.to_csv("environmental_dataset.csv", index=False)
    print("\nSaved -> environmental_dataset.csv  (send this to the AI/Risk Engine)")
