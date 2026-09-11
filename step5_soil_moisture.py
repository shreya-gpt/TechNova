"""
STEP 5 — Collect Soil Moisture

Option A: Open-Meteo ERA5-Land soil moisture
Recommended for MVP.

Option B: NASA SMAP
Advanced / Phase 2.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def get_soil_moisture_openmeteo(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str
) -> pd.DataFrame:

    """
    Collect hourly soil moisture from Open-Meteo.

    Soil moisture is returned at:
        0–7 cm
        7–28 cm
        28–100 cm

    Unit:
        m³/m³ volumetric water content
    """

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,

        "hourly": ",".join([
            "soil_moisture_0_to_7cm",
            "soil_moisture_7_to_28cm",
            "soil_moisture_28_to_100cm",
        ]),

        "timezone": "auto",
    }

    print(
        f"[soil] Requesting soil moisture "
        f"for ({lat}, {lon}) "
        f"from {start_date} to {end_date}"
    )

    response = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if "hourly" not in data:
        raise ValueError(
            "Open-Meteo response does not contain hourly data."
        )

    df = pd.DataFrame(data["hourly"])

    # Convert time to timestamp
    df["time"] = pd.to_datetime(df["time"])

    # Rename time column
    df = df.rename(columns={
        "time": "timestamp"
    })

    # Add location information
    df["lat"] = lat
    df["lon"] = lon

    print(
        f"[soil] Collected {len(df)} hourly soil-moisture records"
    )

    return df


def get_recent_soil_moisture(lat: float, lon: float, days: int = 7):
    """
    Automatically calculate a safe historical date range.

    Example:
        If today is 2026-09-11

        start_date = 2026-09-04
        end_date   = 2026-09-10

    This avoids requesting today's incomplete archive data.
    """

    today = datetime.now().date()

    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)

    start_date = start_date.strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")

    return get_soil_moisture_openmeteo(
        lat,
        lon,
        start_date,
        end_date
    )


def get_soil_moisture_smap(lat: float, lon: float, date: str):
    """
    NASA SMAP integration — Phase 2.

    Requires NASA Earthdata account and earthaccess.
    """

    raise NotImplementedError(
        "SMAP integration is a Phase-2 item. "
        "Use Open-Meteo soil moisture for the MVP."
    )


# ---------------------------------------------------------
# TEST
# ---------------------------------------------------------

if __name__ == "__main__":

    LAT = 27.33
    LON = 88.61

    moisture_df = get_recent_soil_moisture(
        LAT,
        LON,
        days=7
    )

    print("\nSoil Moisture Data:")
    print(moisture_df.tail())

    moisture_df.to_csv(
        "soil_moisture.csv",
        index=False
    )

    print("\nSaved -> soil_moisture.csv")