"""
GIS integration stage.

Converts satellite detections into GIS-consumable layers for the dashboard:
  - GeoJSON: change polygons, landslide polygons, risk points (lightweight,
    web-map friendly — used directly by Leaflet/Mapbox)
  - GeoTIFF: raw probability/change rasters (for advanced GIS analysis, QGIS)
  - PostGIS: optional structured storage for querying/aggregating over time

The GIS dashboard is expected to render, per docs/architecture.md: satellite
image, detected change polygons, landslide polygons, deformation zones,
affected roads, villages, risk heatmap, observation date and model confidence.
"""
from __future__ import annotations

import json
from datetime import date
from typing import List

from src.risk_indicators.indicator_builder import SatelliteRiskIndicators
from src.utils.geo_utils import AOI, bbox_to_polygon_coords


def _json_default(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def risk_indicators_to_geojson_feature(indicators: SatelliteRiskIndicators, aoi: AOI) -> dict:
    """
    Represent one AOI's satellite risk indicators as a single GeoJSON Feature
    (polygon geometry = AOI bounding box, properties = full indicator set).
    This is the primary hand-off format to the GIS dashboard/risk heatmap.
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": bbox_to_polygon_coords(aoi),
        },
        "properties": {
            "aoi_id": indicators.aoi_id,
            "observation_date": indicators.observation_date.isoformat(),
            "change_score": indicators.change_score,
            "landslide_cv_probability": indicators.landslide_cv_probability,
            "vegetation_loss": indicators.vegetation_loss,
            "surface_displacement_mm": indicators.surface_displacement_mm,
            "water_accumulation_score": indicators.water_accumulation_score,
            "road_disruption_score": indicators.road_disruption_score,
            "confidence": indicators.confidence,
            "data_sources": indicators.data_sources,
            "explanation": indicators.explanation,
        },
    }


def write_geojson_feature_collection(
    features: List[dict], output_path: str
) -> str:
    """Write a list of GeoJSON Feature dicts as a FeatureCollection to disk."""
    collection = {"type": "FeatureCollection", "features": features}
    with open(output_path, "w") as f:
        json.dump(collection, f, indent=2, default=_json_default)
    return output_path


def change_regions_to_geojson(
    regions, aoi: AOI, pixel_resolution_m: float, image_shape: tuple
) -> dict:
    """
    Convert detected change regions (row/col centroids + pixel counts) into
    a GeoJSON FeatureCollection of approximate point/circle markers, mapping
    image-space coordinates back into the AOI's lat/lon bounding box. A
    production version would use `rasterio.transform` for exact
    pixel->geo-coordinate conversion; this linear approximation is adequate
    for hackathon-scale AOIs.
    """
    height, width = image_shape
    lat_span = aoi.max_lat - aoi.min_lat
    lon_span = aoi.max_lon - aoi.min_lon

    features = []
    for region in regions:
        row, col = region.centroid_rc
        lat = aoi.max_lat - (row / height) * lat_span
        lon = aoi.min_lon + (col / width) * lon_span
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "region_id": region.label_id,
                "pixel_count": region.pixel_count,
                "area_m2": region.pixel_count * (pixel_resolution_m ** 2),
                "mean_change_magnitude": region.mean_change_magnitude,
                "confidence": region.confidence,
            },
        })

    return {"type": "FeatureCollection", "features": features}


# ---- PostGIS (optional) ---------------------------------------------------

POSTGIS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS satellite_risk_indicators (
    id                          SERIAL PRIMARY KEY,
    aoi_id                      TEXT NOT NULL,
    observation_date            DATE NOT NULL,
    change_score                DOUBLE PRECISION,
    landslide_cv_probability    DOUBLE PRECISION,
    vegetation_loss             DOUBLE PRECISION,
    ndvi_delta                  DOUBLE PRECISION,
    ndwi_delta                  DOUBLE PRECISION,
    surface_displacement_mm     DOUBLE PRECISION,
    water_accumulation_score    DOUBLE PRECISION,
    road_disruption_score       DOUBLE PRECISION,
    confidence                  DOUBLE PRECISION,
    data_sources                TEXT[],
    explanation                 TEXT[],
    geom                        GEOMETRY(Polygon, 4326),
    created_at                  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_satellite_risk_geom ON satellite_risk_indicators USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_satellite_risk_date ON satellite_risk_indicators (observation_date);
"""


def insert_indicators_postgis_sql(indicators: SatelliteRiskIndicators, aoi: AOI) -> str:
    """
    Build a parametrized-style INSERT statement (values inlined for demo
    clarity — use a real parametrized query / psycopg2 in production to
    avoid SQL injection) for storing one record in PostGIS.
    """
    coords = bbox_to_polygon_coords(aoi)[0]
    wkt_points = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    polygon_wkt = f"POLYGON(({wkt_points}))"

    return f"""
    INSERT INTO satellite_risk_indicators (
        aoi_id, observation_date, change_score, landslide_cv_probability,
        vegetation_loss, ndvi_delta, ndwi_delta, surface_displacement_mm,
        water_accumulation_score, road_disruption_score, confidence,
        data_sources, explanation, geom
    ) VALUES (
        '{indicators.aoi_id}', '{indicators.observation_date.isoformat()}',
        {indicators.change_score}, {indicators.landslide_cv_probability},
        {indicators.vegetation_loss}, {indicators.ndvi_delta}, {indicators.ndwi_delta},
        {indicators.surface_displacement_mm}, {indicators.water_accumulation_score},
        {indicators.road_disruption_score}, {indicators.confidence},
        ARRAY{indicators.data_sources}, ARRAY{indicators.explanation},
        ST_GeomFromText('{polygon_wkt}', 4326)
    );
    """
