"""
CLI entry point to run the satellite pipeline over real (downloaded/cached)
GeoTIFF rasters, as opposed to scripts/demo.py's synthetic data.

Usage:
    python scripts/run_pipeline.py \\
        --pre-tif data/raw/aoi1_pre.tif --post-tif data/raw/aoi1_post.tif \\
        --aoi-id NER-MEG-0142 --min-lat 25.55 --min-lon 91.85 \\
        --max-lat 25.60 --max-lon 91.90 --output data/processed/aoi1_risk.geojson

Expects each GeoTIFF to contain bands in the order:
    [Blue, Green, Red, NIR, SWIR1] (matching config.yaml sentinel2.bands
    minus SWIR2, which is optional and unused by the MVP feature set).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.gis.gis_export import risk_indicators_to_geojson_feature, write_geojson_feature_collection
from src.pipeline import OpticalScenePair, run_satellite_pipeline
from src.preprocessing.registration import register_stack
from src.segmentation.model import load_model
from src.utils.geo_utils import AOI


def load_bands(path: str):
    """Load a 5-band [Blue, Green, Red, NIR, SWIR1] GeoTIFF via rasterio."""
    import rasterio

    with rasterio.open(path) as src:
        bands = src.read()  # shape (bands, H, W)
    return [bands[i].astype("float32") / 10000.0 for i in range(bands.shape[0])]  # Sentinel-2 SR scale


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the satellite CV pipeline over real GeoTIFF scenes")
    parser.add_argument("--pre-tif", required=True)
    parser.add_argument("--post-tif", required=True)
    parser.add_argument("--aoi-id", required=True)
    parser.add_argument("--min-lat", type=float, required=True)
    parser.add_argument("--min-lon", type=float, required=True)
    parser.add_argument("--max-lat", type=float, required=True)
    parser.add_argument("--max-lon", type=float, required=True)
    parser.add_argument("--checkpoint", default="data/models/unet_landslide.pt")
    parser.add_argument("--in-channels", type=int, default=6)
    parser.add_argument("--output", default="data/processed/risk_indicators.geojson")
    args = parser.parse_args()

    blue_pre, green_pre, red_pre, nir_pre, swir1_pre = load_bands(args.pre_tif)
    post_bands = load_bands(args.post_tif)

    # Co-register the post scene onto the pre scene (using NIR as the
    # registration reference band) before any feature extraction.
    aligned_post = register_stack(nir_pre, post_bands)
    blue_post, green_post, red_post, nir_post, swir1_post = aligned_post

    optical = OpticalScenePair(
        blue_pre=blue_pre, green_pre=green_pre, red_pre=red_pre, nir_pre=nir_pre, swir1_pre=swir1_pre,
        blue_post=blue_post, green_post=green_post, red_post=red_post, nir_post=nir_post, swir1_post=swir1_post,
    )

    model = load_model(args.checkpoint, in_channels=args.in_channels)

    aoi = AOI(
        aoi_id=args.aoi_id, min_lat=args.min_lat, min_lon=args.min_lon,
        max_lat=args.max_lat, max_lon=args.max_lon,
    )
    lat, lon = aoi.centroid

    result = run_satellite_pipeline(
        aoi_id=args.aoi_id,
        latitude=lat,
        longitude=lon,
        observation_date=date.today(),
        optical=optical,
        sar=None,
        segmentation_model=model,
    )

    print("Satellite risk indicators:")
    for key, value in result.__dict__.items():
        print(f"  {key}: {value}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    feature = risk_indicators_to_geojson_feature(result, aoi)
    out_path = write_geojson_feature_collection([feature], args.output)
    print(f"\nWrote GeoJSON to {out_path}")


if __name__ == "__main__":
    main()
