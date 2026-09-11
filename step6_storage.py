"""
STEP 6 — Store the Raw / Processed Data

MVP: CSV (append-safe, dedup-safe).
Later: PostgreSQL + PostGIS (connection + upsert helper included below,
commented usage at the bottom — enable once your DB is provisioned).
"""

import os
import pandas as pd


# ---------- CSV storage (use this first) ----------

def save_to_csv(df: pd.DataFrame, path: str, dedup_keys=("timestamp", "lat", "lon")) -> None:
    """
    Append df to `path`, creating it if needed, and drop duplicate
    rows on (timestamp, lat, lon) so re-running the pipeline is safe.
    """
    if os.path.exists(path):
        existing = pd.read_csv(path, parse_dates=["timestamp"]) if "timestamp" in df.columns else pd.read_csv(path)
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df

    dedup_keys = [k for k in dedup_keys if k in combined.columns]
    if dedup_keys:
        combined = combined.drop_duplicates(subset=dedup_keys, keep="last")

    combined.to_csv(path, index=False)
    print(f"[storage] Wrote {len(combined)} rows -> {path}")


# ---------- PostgreSQL + PostGIS storage (use later) ----------

def get_postgres_engine(user="postgres", password="postgres",
                         host="localhost", port=5432, dbname="landslide_db"):
    """
    Requires: pip install sqlalchemy psycopg2-binary
    """
    from sqlalchemy import create_engine
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url)


def save_to_postgres(df: pd.DataFrame, table_name: str, engine, if_exists="append") -> None:
    """
    Writes df to a PostGIS-enabled Postgres table. For true spatial
    queries later, convert lat/lon to a geometry column, e.g.:

        CREATE EXTENSION IF NOT EXISTS postgis;
        ALTER TABLE environmental_data
            ADD COLUMN geom geometry(Point, 4326);
        UPDATE environmental_data
            SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326);
    """
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    print(f"[storage] Wrote {len(df)} rows -> postgres table '{table_name}'")


if __name__ == "__main__":
    sample = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-09-01 10:00", "2026-09-01 11:00"]),
        "lat": [27.33, 27.33],
        "lon": [88.61, 88.61],
        "rain_1h": [5, 8],
    })
    save_to_csv(sample, "environmental_raw.csv")

    # --- Later, once Postgres is set up ---
    # engine = get_postgres_engine(dbname="landslide_db")
    # save_to_postgres(sample, "environmental_data", engine)
