"""
MAIN PIPELINE — runs Steps 1-11 end to end for a list of monitored
locations, and saves the final feature table (CSV now, swap in
step6_storage.save_to_postgres later).

Usage:
    python main_pipeline.py
"""

import pandas as pd

from step1_weather_api import get_weather_data, get_rainfall_summary
from step3_rainfall_features import add_rainfall_features, add_rainfall_intensity_flags
from step4_soil_data import get_soil_data
from step5_soil_moisture import get_recent_soil_moisture
from step6_storage import save_to_csv
from step7_data_cleaning import clean_pipeline
from step9_build_dataset import build_environmental_dataset

# Add / edit your monitored locations here

LOCATIONS = [
    # Sikkim / nearby test location
    {"location_id": "gangtok_A", "lat": 27.33, "lon": 88.61},
    {"location_id": "darjeeling_B", "lat": 27.04, "lon": 88.26},

    # Arunachal Pradesh
    {"location_id": "bomdila_A", "lat": 27.2647, "lon": 92.4247},
    {"location_id": "dirang_A", "lat": 27.3601, "lon": 92.2412},
]    



def run_for_location(location_id: str, lat: float, lon: float) -> pd.DataFrame:
    print(f"\n=== Processing {location_id} ({lat}, {lon}) ===")

    weather_df = get_weather_data(lat, lon)
    weather_df = clean_pipeline(weather_df)
    weather_df = add_rainfall_features(weather_df)
    weather_df = add_rainfall_intensity_flags(weather_df)
    forecast_summary = get_rainfall_summary(weather_df)

    soil_props = pd.DataFrame([get_soil_data(lat, lon)])

    end = pd.Timestamp.now().strftime("%Y-%m-%d")
    start = (pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    soil_df = get_recent_soil_moisture(
    lat,
    lon,
    days=7
)
    final_row = build_environmental_dataset(
        weather_df, forecast_summary, soil_df, soil_props, location_id
    )
    return final_row


def main():
    all_rows = []
    for loc in LOCATIONS:
        try:
            row = run_for_location(**loc)
            all_rows.append(row)
        except Exception as e:
            print(f"[main] Failed for {loc['location_id']}: {e}")

    if not all_rows:
        print("No data collected — check network/API access.")
        return

    dataset = pd.concat(all_rows, ignore_index=True)
    print("\n=== Final environmental dataset (sent to AI/Risk Engine) ===")
    print(dataset)

    save_to_csv(dataset, "environmental_dataset.csv",
                dedup_keys=("timestamp", "lat", "lon", "location_id"))


if __name__ == "__main__":
    main()
