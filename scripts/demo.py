"""
Self-contained demo: OBSERVE -> DETECT -> MEASURE -> FUSE -> PREDICT -> ALERT

Generates a synthetic before/after Sentinel-2-like scene pair (and a
synthetic SAR complex pair) for a landslide-prone road segment in
Meghalaya/NER, runs the full pipeline, prints the resulting standardized
risk-indicator record, and writes a GeoJSON file the GIS dashboard could
consume directly.

No network access or satellite credentials required — run this anywhere:

    python scripts/demo.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.gis.gis_export import risk_indicators_to_geojson_feature, write_geojson_feature_collection
from src.pipeline import OpticalScenePair, SarScenePair, run_satellite_pipeline
from src.segmentation.model import UNet
from src.utils.geo_utils import AOI


def make_synthetic_optical_pair(size: int = 256, seed: int = 42):
    """
    Build a synthetic pre/post optical scene pair with a deliberately
    embedded 'disturbed patch' (simulating a landslide scar): lower NIR,
    higher red/SWIR (bare soil signature), mimicking real post-slide
    reflectance behaviour so every downstream index/model has a genuine
    signal to detect — not just random noise.
    """
    rng = np.random.default_rng(seed)

    def band(base: float, noise: float = 0.04):
        return np.clip(base + rng.normal(0, noise, (size, size)), 0, 1).astype(np.float32)

    blue_pre, green_pre, red_pre = band(0.22), band(0.28), band(0.18)
    nir_pre, swir1_pre = band(0.58), band(0.28)

    blue_post, green_post, red_post = blue_pre.copy(), green_pre.copy(), red_pre.copy()
    nir_post, swir1_post = nir_pre.copy(), swir1_pre.copy()

    # Embed an elongated "scar" shape (landslides are typically elongated
    # down-slope, not circular) using an ellipse mask.
    yy, xx = np.ogrid[:size, :size]
    cy, cx = size // 2, size // 3
    ellipse = ((yy - cy) / 60) ** 2 + ((xx - cx) / 18) ** 2 <= 1

    nir_post[ellipse] *= 0.35
    red_post[ellipse] = np.clip(red_post[ellipse] * 1.5, 0, 1)
    swir1_post[ellipse] = np.clip(swir1_post[ellipse] * 1.6, 0, 1)
    green_post[ellipse] = np.clip(green_post[ellipse] * 1.2, 0, 1)

    return OpticalScenePair(
        blue_pre=blue_pre, green_pre=green_pre, red_pre=red_pre, nir_pre=nir_pre, swir1_pre=swir1_pre,
        blue_post=blue_post, green_post=green_post, red_post=red_post, nir_post=nir_post, swir1_post=swir1_post,
    ), ellipse


def make_synthetic_sar_pair(size: int = 256, ellipse=None, seed: int = 7) -> SarScenePair:
    """
    Synthetic complex SAR pre/post pair. Inside the disturbed patch, phase is
    randomized (simulating decorrelation from a real surface change) and
    amplitude is boosted (rougher exposed soil often increases backscatter).
    """
    rng = np.random.default_rng(seed)
    amplitude_pre = np.abs(rng.normal(1.0, 0.15, (size, size)))
    phase_pre = rng.uniform(-np.pi, np.pi, (size, size))
    pre_complex = amplitude_pre * np.exp(1j * phase_pre)

    amplitude_post = amplitude_pre.copy()
    phase_post = phase_pre.copy()  # mostly coherent (unchanged ground) elsewhere

    if ellipse is not None:
        amplitude_post[ellipse] *= 1.4
        phase_post[ellipse] = rng.uniform(-np.pi, np.pi, ellipse.sum())  # decorrelated phase

    post_complex = amplitude_post * np.exp(1j * phase_post)
    return SarScenePair(pre_complex=pre_complex, post_complex=post_complex)


def main() -> None:
    print("=" * 70)
    print("OBSERVE  -> Acquiring (synthetic) Sentinel-2 + Sentinel-1 scene pair")
    print("=" * 70)

    optical, ellipse = make_synthetic_optical_pair()
    sar = make_synthetic_sar_pair(ellipse=ellipse)

    aoi = AOI(aoi_id="NER-MEG-DEMO-ROAD-07", min_lat=25.55, min_lon=91.85, max_lat=25.60, max_lon=91.90)
    lat, lon = aoi.centroid

    print("\nDETECT / MEASURE -> Running preprocessing, spectral indices, change")
    print("                     detection, U-Net segmentation, SAR/InSAR deformation...")

    model = UNet(in_channels=6)  # untrained weights for demo purposes — see src/segmentation/train.py

    print("\nFUSE -> Combining optical + SAR signals into satellite risk indicators")
    result = run_satellite_pipeline(
        aoi_id=aoi.aoi_id,
        latitude=lat,
        longitude=lon,
        observation_date=date.today(),
        optical=optical,
        sar=sar,
        segmentation_model=model,
    )

    print("\nPREDICT -> Standardized output record for the central AI Risk Engine:")
    print("-" * 70)
    print(json.dumps(result.__dict__, indent=2, default=str))

    print("\nALERT -> Explanation (would be surfaced to authorities on the dashboard):")
    for line in result.explanation:
        print(f"  • {line}")

    os.makedirs("data/processed", exist_ok=True)
    feature = risk_indicators_to_geojson_feature(result, aoi)
    out_path = write_geojson_feature_collection([feature], "data/processed/demo_risk_indicators.geojson")

    print(f"\nGIS layer written to: {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
