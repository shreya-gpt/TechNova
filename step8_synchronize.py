"""
STEP 8 — Synchronize All Data Sources

Weather (top of hour), satellite (half-hourly), soil moisture (may be
daily) all land on different timestamps. Resample everything onto a
common hourly grid per location before merging.
"""

import pandas as pd


def resample_to_hourly(df: pd.DataFrame, agg: dict) -> pd.DataFrame:
    """
    agg example: {"precipitation": "sum", "temperature_2m": "mean"}
    Resamples PER (lat, lon) group so locations don't mix.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    def _resample_group(group: pd.DataFrame) -> pd.DataFrame:
        group = group.set_index("timestamp")
        cols = {k: v for k, v in agg.items() if k in group.columns}
        resampled = group[list(cols.keys())].resample("1h").agg(cols)
        return resampled.reset_index()

    return df.groupby(["lat", "lon"], group_keys=True).apply(_resample_group).reset_index(level=[0, 1])


def merge_sources(weather_df: pd.DataFrame, soil_moisture_df: pd.DataFrame,
                   soil_props_df: pd.DataFrame) -> pd.DataFrame:
    """
    weather_df, soil_moisture_df: hourly time series (timestamp, lat, lon, ...)
    soil_props_df: static per-location properties (lat, lon, clay, sand, ...)
                   -> broadcast (left-join) onto every timestamp for that location
    """
    merged = pd.merge_asof(
        weather_df.sort_values("timestamp"),
        soil_moisture_df.sort_values("timestamp"),
        on="timestamp", by=["lat", "lon"],
        direction="nearest", tolerance=pd.Timedelta("1h"),
    )
    merged = merged.merge(soil_props_df, on=["lat", "lon"], how="left", suffixes=("", "_soilprop"))
    return merged


if __name__ == "__main__":
    weather = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-06-01 10:00", "2026-06-01 11:00"]),
        "lat": [27.33, 27.33], "lon": [88.61, 88.61],
        "precipitation": [5, 8], "temperature_2m": [22, 23],
    })
    soil_moist = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-06-01 10:30", "2026-06-01 11:30"]),
        "lat": [27.33, 27.33], "lon": [88.61, 88.61],
        "soil_moisture_0_to_7cm": [0.42, 0.45],
    })
    soil_props = pd.DataFrame({"lat": [27.33], "lon": [88.61], "clay": [24.5], "sand": [40.1]})

    result = merge_sources(weather, soil_moist, soil_props)
    print(result)
