"""
STEP 7 — Clean the Data
Tools: Pandas + NumPy

Handles: missing values, duplicate rows, invalid coordinates,
unit sanity checks, and timestamp normalization.
"""

import numpy as np
import pandas as pd


def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=["timestamp", "lat", "lon"])
    print(f"[clean] Dropped {before - len(df)} duplicate rows")
    return df


def validate_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df[df["lat"].between(-90, 90) & df["lon"].between(-180, 180)]
    print(f"[clean] Dropped {before - len(df)} rows with invalid coordinates")
    return df


def validate_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanity-check physically implausible values instead of trusting the
    source blindly. Marks them NaN so the missing-value strategy below
    handles them consistently, rather than silently dropping rows.
    """
    checks = {
        "precipitation": (0, 500),        # mm/hour, generous upper bound
        "relative_humidity_2m": (0, 100),
        "temperature_2m": (-40, 55),
        "soil_moisture_0_to_7cm": (0, 1),  # m3/m3 volumetric fraction
    }
    for col, (lo, hi) in checks.items():
        if col in df.columns:
            invalid = ~df[col].between(lo, hi) & df[col].notna()
            n_invalid = invalid.sum()
            if n_invalid:
                print(f"[clean] {col}: {n_invalid} out-of-range values -> set to NaN")
                df.loc[invalid, col] = np.nan
    return df


def handle_missing_values(df: pd.DataFrame, method: str = "interpolate") -> pd.DataFrame:
    """
    Don't blindly fillna(0) — that would fabricate "no rain" and
    quietly corrupt a landslide model. Choose deliberately:

      - 'interpolate': good for short gaps in a continuous hourly series
        (e.g. temperature, humidity, soil moisture)
      - 'ffill': good for slowly-changing soil properties
      - 'drop': safest for rainfall itself if gaps are large — better
        to have no data point than an invented rainfall value
    """
    df = df.sort_values("timestamp").copy()

    if method == "interpolate":
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].interpolate(limit=3, limit_direction="both")
    elif method == "ffill":
        df = df.ffill(limit=3)
    elif method == "drop":
        df = df.dropna()
    else:
        raise ValueError(f"Unknown method: {method}")

    remaining_na = df.isna().sum().sum()
    print(f"[clean] Remaining NaNs after '{method}': {remaining_na}")
    return df


def normalize_timestamps(df: pd.DataFrame, tz: str = "Asia/Kolkata") -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert(tz)
    return df


def clean_pipeline(df: pd.DataFrame, missing_strategy: str = "interpolate") -> pd.DataFrame:
    df = drop_duplicates(df)
    df = validate_coordinates(df)
    df = validate_ranges(df)
    df = handle_missing_values(df, method=missing_strategy)
    return df


if __name__ == "__main__":
    raw = pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2026-06-01", "2026-06-02", "2026-06-02", "2026-06-03", "2026-06-04"
        ]),
        "lat": [27.33] * 5,
        "lon": [88.61] * 5,
        "precipitation": [10, 12, 12, np.nan, 15],
        "relative_humidity_2m": [78, 91, 91, 94, 65],
    })
    cleaned = clean_pipeline(raw)
    print(cleaned)
