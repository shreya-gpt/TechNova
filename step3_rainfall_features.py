"""
STEP 3 / 9 — Create Landslide Rainfall Features

Turns a single 'precipitation' column into the multi-window features
a landslide risk model actually needs: rain_1h, rain_3h, rain_6h,
rain_12h, rain_24h, rain_48h, rain_72h (rolling sums), computed PER
LOCATION (so multiple lat/lon points don't bleed into each other).

Input: hourly DataFrame with columns [timestamp, lat, lon, precipitation]
Output: same DataFrame + rolling rainfall columns
"""

import pandas as pd

RAIN_WINDOWS_HOURS = {
    "rain_1h": 1,
    "rain_3h": 3,
    "rain_6h": 6,
    "rain_12h": 12,
    "rain_24h": 24,
    "rain_48h": 48,
    "rain_72h": 72,
}


def add_rainfall_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["lat", "lon", "timestamp"]).copy()

    def _per_location(group: pd.DataFrame) -> pd.DataFrame:
        group = group.set_index("timestamp")
        for col_name, hours in RAIN_WINDOWS_HOURS.items():
            group[col_name] = group["precipitation"].rolling(f"{hours}h", min_periods=1).sum()
        return group.reset_index()

    df = df.groupby(["lat", "lon"], group_keys=False).apply(_per_location)
    return df


def add_rainfall_intensity_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple derived risk flags used widely in landslide-triggering-rainfall
    literature (thresholds are illustrative — tune with local data / the
    AI team once you have labeled events).
    """
    df = df.copy()
    df["high_intensity_1h"] = (df["rain_1h"] >= 20).astype(int)      # short burst
    df["high_accumulation_24h"] = (df["rain_24h"] >= 100).astype(int)
    df["high_accumulation_72h"] = (df["rain_72h"] >= 200).astype(int)
    return df


if __name__ == "__main__":
    from step1_weather_api import get_weather_data

    df = get_weather_data(27.33, 88.61)
    df = add_rainfall_features(df)
    df = add_rainfall_intensity_flags(df)

    print(df[["timestamp", "precipitation", "rain_1h", "rain_6h", "rain_24h", "rain_72h"]].tail(10))
    df.to_csv("rainfall_features.csv", index=False)
    print("\nSaved -> rainfall_features.csv")
